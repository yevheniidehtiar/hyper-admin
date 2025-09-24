import os
from typing import cast

from fastapi import HTTPException, Query, Request
from fastapi.templating import Jinja2Templates
from jinja2 import FileSystemLoader
from starlette.responses import RedirectResponse, Response

from hyperadmin.adapters import SQLAlchemyAdapter, SQLModelAdapter
from hyperadmin.core.options import AdminOptions
from hyperadmin.core.registry import site
from hyperadmin.discover import app_label_var
from hyperadmin.views.forms import PydanticForm
from hyperadmin.views.htmx import HtmxTemplateResponse


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
    def __init__(
        self,
        adapter: SQLAlchemyAdapter | SQLModelAdapter,
        options: AdminOptions,
        templates: Jinja2Templates,
        app_label: str | None,
    ):
        self.adapter = adapter
        self.model = adapter.model
        self.options = options
        self.templates = templates
        self.app_label = app_label

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
                loader = cast(FileSystemLoader, self.templates.env.loader)
                for search_path in loader.searchpath:
                    full_path = os.path.join(search_path, template_path)
                    if os.path.exists(full_path):
                        return template_path

        return f"{view_name}.html"

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
                page=page, page_size=page_size, search=search if search else None, order_by=order_by
            )

            # Calculate pagination info
            import math

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

        context = {
            "request": request,
            "model_name": self.model.__name__,
            "fields": list(self.model.model_fields.keys()),
            "items": items,
            "pagination": pagination,
            "search_query": search,
            "sort_by": sort_by,
            "sort_direction": sort_direction,
        }

        # Use table template for HTMX requests, full layout for regular requests
        template_name = (
            "components/table.html"
            if request.headers.get("hx-request")
            else self._get_template_name("list")
        )
        return self.templates.TemplateResponse(template_name, context)

    async def detail_view(self, request: Request, item_id: int):
        """
        Renders the detail view for a single item.
        Assumes the model has an 'id' field.
        """
        item = await self.adapter.get(pk=item_id)

        if not item:
            raise HTTPException(status_code=404, detail="Item not found")

        context = {
            "request": request,
            "item_name": f"{self.model.__name__} #{getattr(item, 'id', 'N/A')}",
            "item": item.model_dump(),
        }
        template_name = self._get_template_name("detail")
        return self.templates.TemplateResponse(template_name, context)

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
        # Build a Pydantic-backed form abstraction for templates
        form = PydanticForm(self.model, initial=values or {})
        if errors:
            # Bind raw values and attach errors to fields
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
        form_data = await request.form()
        data = dict(form_data)

        # Use PydanticForm for consistent binding/validation
        form = PydanticForm(self.model)
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

            item_id = getattr(new_item, "id", None)
            if item_id:
                redirect_url = request.url_for(
                    f"{self.model.__name__.lower()}-detail", item_id=item_id
                )
            else:
                redirect_url = request.url_for(f"{self.model.__name__.lower()}-list")

            if "hx-request" in request.headers:
                return Response(status_code=200, headers={"HX-Redirect": str(redirect_url)})

            return RedirectResponse(url=redirect_url, status_code=303)

        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Internal Server Error: {e}")

    async def update_form_view(self, request: Request, item_id: int):
        """Renders the update form."""
        item = await self.adapter.get(pk=item_id)
        if not item:
            raise HTTPException(status_code=404, detail="Item not found")

        # Prefill form with existing item's values (assumes Pydantic/SQLModel with model_dump)
        initial = getattr(item, "model_dump", None)
        initial_values = initial() if callable(initial) else getattr(item, "__dict__", {})
        form = PydanticForm(self.model, initial=initial_values)
        context = {
            "request": request,
            "model_name": self.model.__name__,
            "item": item,
            "form": form,
            # Legacy keys for compatibility
            "fields": list(self.model.model_fields.keys()),
        }
        template_name = self._get_template_name("update")
        return HtmxTemplateResponse(self.templates).render(
            template_name=template_name,
            context=context,
            request=request,
            block="form_body",
        )

    async def update_view(self, request: Request, item_id: int):
        """Handles form submission for updating an item."""
        form_data = await request.form()
        await self.adapter.update(pk=item_id, data=dict(form_data))
        return RedirectResponse(url=f"/admin/{self.model.__name__.lower()}", status_code=303)

    async def delete_action(self, request: Request, item_id: int):
        """Deletes an item."""
        item = await self.adapter.get(pk=item_id)
        if not item:
            raise HTTPException(status_code=404, detail="Item not found")

        return RedirectResponse(url=f"/admin/{self.model.__name__.lower()}", status_code=303)


async def admin_dashboard(request: Request, templates: Jinja2Templates):
    """Renders the main admin dashboard page."""
    context = {"request": request}
    return templates.TemplateResponse("dashboard.html", context)
