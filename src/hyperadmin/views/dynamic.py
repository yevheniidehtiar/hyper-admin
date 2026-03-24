import logging
import math
import os
import re
from typing import TYPE_CHECKING, Any, Union, cast, get_args, get_origin

from fastapi import HTTPException, Query, Request
from fastapi.templating import Jinja2Templates
from sqlalchemy.exc import IntegrityError
from starlette.responses import RedirectResponse, Response

if TYPE_CHECKING:
    from jinja2 import FileSystemLoader

from hyperadmin.adapters import SQLAlchemyAdapter, SQLModelAdapter
from hyperadmin.core.discovery import build_filter_metadata
from hyperadmin.core.display import get_display_name
from hyperadmin.core.options import AdminOptions
from hyperadmin.core.registry import site
from hyperadmin.discover import app_label_var
from hyperadmin.views.forms import CheckboxInput, PydanticForm
from hyperadmin.views.htmx import HtmxTemplateResponse

logger = logging.getLogger(__name__)


def _integrity_error_to_field_errors(exc: IntegrityError) -> dict[str, str]:
    """Parse an IntegrityError into {field_name: message} for form display."""
    msg = str(exc.orig) if exc.orig else str(exc)
    # SQLite: "UNIQUE constraint failed: users.username"  # noqa: ERA001
    match = re.search(r"UNIQUE constraint failed:\s*\S+\.(\w+)", msg)
    if match:
        field = match.group(1)
        return {field: f"{field.replace('_', ' ').title()} already exists."}
    # PostgreSQL: 'duplicate key ... unique constraint "users_username_key"'  # noqa: ERA001
    match = re.search(r'duplicate key value violates unique constraint "(\w+)"', msg)
    if match:
        constraint = match.group(1)
        # Try to extract field name from constraint name (e.g. "users_username_key" → "username")
        parts = constraint.rsplit("_key", 1)[0].split("_", 1)
        field = parts[1] if len(parts) > 1 else parts[0]
        return {field: f"{field.replace('_', ' ').title()} already exists."}
    return {"__all__": "A record with these values already exists."}


class ModelView:
    def __init__(self, model):
        self.model = model

    def __init_subclass__(cls, **kwargs):
        model = kwargs.pop("model", None)
        super().__init_subclass__(**kwargs)
        if model:
            cls.model = model
            app_label = app_label_var.get()
            site.register(model, admin_class=cls, app_label=app_label)


class DynamicModelView:
    """View handler that serves all CRUD endpoints for a registered model.

    One instance is created per model by ``HyperAdminRouter``. It delegates
    all database operations to its ``adapter`` and renders Jinja2 templates
    resolved through the template-search hierarchy.
    """

    def __init__(
        self,
        adapter: SQLAlchemyAdapter | SQLModelAdapter,
        options: AdminOptions,
        templates: Jinja2Templates,
        app_label: str | None,
        form_include: list[str] | None = None,
        form_create_exclude: list[str] | None = None,
        column_list: list[str] | None = None,
        permission_checker: Any = None,
    ):
        self.adapter = adapter
        self.model = adapter.model
        self.options = options
        self.templates = templates
        self.app_label = app_label
        self.form_include = form_include
        self.form_create_exclude = form_create_exclude or []
        self.column_list = column_list or ["id", "__str__"]
        self.permission_checker = permission_checker
        self._model_name_lower = self.model.__name__.lower()

    async def _check_permission(self, request: Request, action: str) -> None:
        """Raise 403 if the user lacks the required permission.

        Does nothing when ``permission_checker`` is ``None`` (auth disabled).
        """
        if self.permission_checker is None:
            return
        user = getattr(request.state, "user", None)
        if user is None:
            raise HTTPException(status_code=403, detail="Authentication required")
        codename = f"{action}_{self._model_name_lower}"
        if not await self.permission_checker.has_permission(user, codename):
            raise HTTPException(status_code=403, detail="Permission denied")

    def _get_template_name(self, view_name: str) -> str:
        model_name = self.model.__name__.lower()

        potential_templates = []
        if self.app_label:
            potential_templates.extend(
                [
                    f"{self.app_label}/{model_name}/{view_name}.html",
                    f"{self.app_label}/{model_name}/default.html",
                    f"{self.app_label}/{view_name}.html",
                    f"{self.app_label}/default.html",
                ]
            )
        potential_templates.extend(
            [
                f"{view_name}.html",
                "default.html",
            ]
        )

        for template_path in potential_templates:
            if self.templates.env.loader:
                # Cast to FileSystemLoader to access the searchpath attribute
                loader = cast("FileSystemLoader", self.templates.env.loader)
                for search_path in loader.searchpath:
                    full_path = os.path.join(search_path, template_path)
                    if os.path.exists(full_path):
                        return template_path

        return f"{view_name}.html"

    async def _get_filter_metadata(self) -> list[dict[str, Any]]:
        """Introspects list_filter fields to build metadata for filter UI."""
        return await build_filter_metadata(self.model, self.options.list_filter, self.adapter)

    async def list_view(
        self,
        request: Request,
        page: int = Query(1, ge=1),
        page_size: int = Query(10, ge=1, le=100),
        search: str = Query(""),
        sort_by: str = Query(None),
        sort_direction: str = Query("asc", pattern="^(asc|desc)$"),
    ):
        """Renders the list view for the model with pagination, sorting, and filtering."""
        await self._check_permission(request, "view")

        # Parse filters from query params
        active_filters: dict[str, str] = {}
        filters_to_apply: dict[str, Any] = {}
        for key, value in request.query_params.items():
            if key.startswith("filter_") and value:
                field_name = key[7:]
                active_filters[field_name] = value

                # Type conversion for bool
                if field_name in self.model.model_fields:
                    ann = self.model.model_fields[field_name].annotation
                    if ann is bool or (get_origin(ann) is Union and bool in get_args(ann)):
                        filters_to_apply[field_name] = value.lower() == "true"
                    else:
                        filters_to_apply[field_name] = value

        # Get default sort column if none specified
        if not sort_by:
            sort_by = (
                next(iter(self.model.model_fields.keys())) if self.model.model_fields else "id"
            )

        # Format order_by for adapter (use negative prefix for descending)
        order_by = f"-{sort_by}" if sort_direction == "desc" else sort_by

        try:
            # Use adapter's list method
            items, total_items = await self.adapter.list(
                page=page,
                page_size=page_size,
                search=search or None,
                filters=filters_to_apply,
                order_by=order_by,
            )

            # Calculate pagination info
            total_pages = math.ceil(total_items / page_size) if page_size > 0 else 0
            start_index = (page - 1) * page_size + 1 if total_items > 0 else 0
            end_index = min(page * page_size, total_items)

            pagination = {
                "page": page,
                "page_size": page_size,
                "total_items": total_items,
                "total_pages": total_pages,
                "start_index": start_index,
                "end_index": end_index,
            }

        except Exception:
            # Handle errors gracefully
            items = []
            pagination = {
                "page": 1,
                "page_size": page_size,
                "total_items": 0,
                "total_pages": 0,
                "start_index": 0,
                "end_index": 0,
            }
            # In a real application, you might want to log this error
            # For now, we'll just show empty results

        # Convert items to row dicts using column_list
        display_fields = self.column_list
        rows = []
        for item in items:
            row: dict[str, Any] = {}
            for field in display_fields:
                if field == "__str__":
                    row[field] = get_display_name(item)
                else:
                    row[field] = getattr(item, field, None)
            row["id"] = getattr(item, "id", None)
            rows.append(row)

        # Get filter metadata if list_filter is configured
        filter_metadata = await self._get_filter_metadata() if self.options.list_filter else []

        context = {
            "request": request,
            "model_name": self.model.__name__,
            "fields": display_fields,
            "items": rows,
            "pagination": pagination,
            "search_query": search,
            "sort_by": sort_by,
            "sort_direction": sort_direction,
            "filter_metadata": filter_metadata,
            "active_filters": active_filters,
        }

        # Use table template for HTMX requests, full layout for regular requests
        template_name = (
            "components/table.html"
            if request.headers.get("hx-request")
            else self._get_template_name("list")
        )
        return self.templates.TemplateResponse(request, template_name, context)

    async def detail_view(self, request: Request, item_id: int):
        """
        Renders the detail view for a single item.
        Assumes the model has an 'id' field.
        """
        await self._check_permission(request, "view")
        item = await self.adapter.get(pk=item_id)

        if not item:
            raise HTTPException(status_code=404, detail="Item not found")

        context = {
            "request": request,
            "item_name": get_display_name(item),
            "item": item.model_dump(),
        }
        template_name = self._get_template_name("detail")
        return self.templates.TemplateResponse(request, template_name, context)

    async def create_form_view(
        self,
        request: Request,
        values: dict | None = None,
        errors: dict | None = None,
        status_code: int = 200,
    ):
        """Renders the create form.

        For HTMX requests, only the inner form body is returned to prevent nesting the full page
        into the target container.
        """
        await self._check_permission(request, "add")
        # Build a Pydantic-backed form abstraction for templates
        # Create forms exclude form_create_exclude fields (e.g. updated_at)
        create_include = self.form_include
        if create_include and self.form_create_exclude:
            create_include = [f for f in create_include if f not in self.form_create_exclude]
        form = PydanticForm(
            self.model,
            include=create_include,
            exclude=self.form_create_exclude,
            initial=values or {},
        )
        if errors:
            form.bind(values or {})
            norm_errors = {k: (v if isinstance(v, list) else [v]) for k, v in errors.items()}
            form.errors = norm_errors
            for f in form.fields:
                f.errors = norm_errors.get(f.name)

        context = {
            "request": request,
            "model_name": self.model.__name__,
            "form": form,
            "values": values or {},
            "errors": errors or {},
        }
        template_name = self._get_template_name("create")
        return HtmxTemplateResponse(self.templates).render(
            template_name=template_name,
            context=context,
            request=request,
            block="form_body",
            status_code=status_code,
        )

    async def create_view(self, request: Request):
        """Handles form submission for creating a new item."""
        await self._check_permission(request, "add")
        form_data = await request.form()
        data = dict(form_data)

        # Use PydanticForm for consistent binding/validation
        create_include = self.form_include
        if create_include and self.form_create_exclude:
            create_include = [f for f in create_include if f not in self.form_create_exclude]
        form = PydanticForm(self.model, include=create_include, exclude=self.form_create_exclude)
        form.bind(data)
        instance, errs = form.validate(data)

        if errs:
            legacy_errs = {k: v[0] for k, v in errs.items() if v}
            return await self.create_form_view(
                request,
                values=data,
                errors=legacy_errs,
                status_code=422,
            )

        if not instance:
            return await self.create_form_view(
                request,
                values=data,
                errors=errs,
                status_code=422,
            )

        try:
            new_item = await self.adapter.create(data=instance.model_dump())
        except IntegrityError as exc:
            logger.exception("IntegrityError during create")
            field_errors = _integrity_error_to_field_errors(exc)
            return await self.create_form_view(
                request, values=data, errors=field_errors, status_code=422
            )

        item_id = getattr(new_item, "id", None)
        if item_id:
            redirect_url = request.url_for(f"{self.model.__name__.lower()}-detail", item_id=item_id)
        else:
            redirect_url = request.url_for(f"{self.model.__name__.lower()}-list")

        if "hx-request" in request.headers:
            return Response(status_code=200, headers={"HX-Redirect": str(redirect_url)})

        return RedirectResponse(url=redirect_url, status_code=303)

    async def update_form_view(
        self,
        request: Request,
        item_id: int,
        values: dict | None = None,
        errors: dict | None = None,
        status_code: int = 200,
    ):
        """Renders the update form, optionally pre-filled with submitted values and errors."""
        await self._check_permission(request, "change")
        item = await self.adapter.get(pk=item_id)
        if not item:
            raise HTTPException(status_code=404, detail="Item not found")

        initial_func = getattr(item, "model_dump", None)
        initial_values = cast(
            "dict[str, Any]",
            initial_func() if callable(initial_func) else getattr(item, "__dict__", {}),
        )

        # Override with re-submitted values on validation failure
        if values:
            initial_values.update(values)

        form = PydanticForm(self.model, include=self.form_include, initial=initial_values)

        if errors:
            form.bind(values or {})
            norm_errors = {k: (v if isinstance(v, list) else [v]) for k, v in errors.items()}
            form.errors = norm_errors
            for f in form.fields:
                f.errors = norm_errors.get(f.name)

        context = {
            "request": request,
            "model_name": self.model.__name__,
            "item": item,
            "form": form,
            "values": values or initial_values,
            "errors": errors or {},
            # Legacy keys for compatibility
            "fields": list(self.model.model_fields.keys()),
        }
        template_name = self._get_template_name("update")
        return HtmxTemplateResponse(self.templates).render(
            template_name=template_name,
            context=context,
            request=request,
            block="form_body",
            status_code=status_code,
        )

    async def update_view(self, request: Request, item_id: int):
        """Handles form submission for updating an item."""
        await self._check_permission(request, "change")
        form_data = await request.form()
        data: dict[str, Any] = dict(form_data)

        form = PydanticForm(self.model, include=self.form_include)

        # Unchecked checkboxes are absent from form data — inject False before validation
        for field in form.fields:
            if isinstance(field.widget, CheckboxInput) and field.name not in data:
                data[field.name] = False

        form.bind(data)
        instance, errs = form.validate(data)

        if errs:
            legacy_errs = {k: v[0] for k, v in errs.items() if v}
            return await self.update_form_view(
                request, item_id=item_id, values=data, errors=legacy_errs, status_code=422
            )

        if not instance:
            return await self.update_form_view(
                request, item_id=item_id, values=data, errors={}, status_code=422
            )

        # exclude_none: id is not submitted by the form and must not overwrite the PK
        try:
            await self.adapter.update(pk=item_id, data=instance.model_dump(exclude_none=True))
        except IntegrityError as exc:
            logger.exception("IntegrityError during update")
            field_errors = _integrity_error_to_field_errors(exc)
            return await self.update_form_view(
                request, item_id=item_id, values=data, errors=field_errors, status_code=422
            )

        redirect_url = request.url_for(f"{self.model.__name__.lower()}-list")

        if "hx-request" in request.headers:
            return Response(status_code=200, headers={"HX-Redirect": str(redirect_url)})

        return RedirectResponse(url=redirect_url, status_code=303)

    async def delete_action(self, request: Request, item_id: int):
        """Deletes an item."""
        await self._check_permission(request, "delete")
        item = await self.adapter.get(pk=item_id)
        if not item:
            raise HTTPException(status_code=404, detail="Item not found")

        await self.adapter.delete(pk=item_id)

        redirect_url = request.url_for(f"{self.model.__name__.lower()}-list")

        if "hx-request" in request.headers:
            return Response(status_code=200, headers={"HX-Redirect": str(redirect_url)})

        return RedirectResponse(url=redirect_url, status_code=303)


async def admin_dashboard(request: Request, templates: Jinja2Templates):
    """Renders the main admin dashboard page."""
    context = {"request": request}
    return templates.TemplateResponse(request, "dashboard.html", context)
