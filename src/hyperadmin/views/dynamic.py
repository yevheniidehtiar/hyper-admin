import logging
import math
import os
import re
from collections.abc import Generator
from contextlib import contextmanager
from typing import TYPE_CHECKING, Any, Union, cast, get_args, get_origin

from fastapi import HTTPException, Query, Request
from fastapi.templating import Jinja2Templates
from pydantic import ValidationError
from sqlalchemy.exc import IntegrityError
from starlette.responses import RedirectResponse, Response

if TYPE_CHECKING:
    from jinja2 import FileSystemLoader

from starlette.datastructures import UploadFile as StarletteUpload

from hyperadmin.adapters import SQLAlchemyAdapter, SQLModelAdapter
from hyperadmin.core.actions import ActionDef
from hyperadmin.core.bulk_results import BulkRowResult, BulkRowStatus
from hyperadmin.core.choices import ChoiceItem, SelectFieldMeta
from hyperadmin.core.discovery import build_filter_metadata
from hyperadmin.core.display import get_display_name
from hyperadmin.core.fields import classify_field
from hyperadmin.core.options import AdminOptions
from hyperadmin.core.registry import site
from hyperadmin.discover import app_label_var
from hyperadmin.views.forms import (
    CheckboxInput,
    FileInputWidget,
    HtmxWidget,
    InlineFormset,
    MultiSelectWidget,
    PydanticForm,
    RelationMultiSelectWidget,
    RelationSelectWidget,
)
from hyperadmin.views.htmx import HtmxTemplateResponse

logger = logging.getLogger(__name__)

_MAX_CHOICES_LIMIT = 200


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

    def __init__(  # noqa: PLR0913
        self,
        adapter: SQLAlchemyAdapter | SQLModelAdapter,
        options: AdminOptions,
        templates: Jinja2Templates,
        app_label: str | None,
        form_include: list[str] | None = None,
        form_create_exclude: list[str] | None = None,
        column_list: list[str] | None = None,
        permission_checker: Any = None,
        actions: list[ActionDef] | None = None,
        admin_instance: Any = None,
        search_fields: list[str] | None = None,
        field_labels: dict[str, str] | None = None,
        storage: Any = None,
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
        self.actions: list[ActionDef] = actions or []
        self._action_map: dict[str, ActionDef] = {a.name: a for a in self.actions}
        self._admin_instance = admin_instance
        self.search_fields = search_fields
        self.field_labels = field_labels or {}
        self.storage = storage
        # Expose the live adapter on the admin instance so action handlers can use self.adapter
        if admin_instance is not None:
            admin_instance.adapter = self.adapter

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

    @contextmanager
    def _request_queryset_filter(self, request: Request) -> Generator[None, None, None]:
        """Register the per-request queryset filter on the adapter for the duration of a view.

        Composes :meth:`hyperadmin.core.model.ModelAdmin.get_queryset` (when an admin
        instance is wired) into the adapter's ``set_queryset_filter`` seam so that
        ``adapter.list()`` and ``adapter.get()`` apply ModelAdmin-defined row-level
        filters before any view-layer filters.

        The previous filter (if any) is restored on exit so that a long-lived adapter
        cannot leak filters across requests.
        """
        admin_instance = self._admin_instance
        previous_filter = getattr(self.adapter, "_queryset_filter", None)

        def _filter_for_request(req: Request | None) -> dict[str, Any]:
            if admin_instance is None:
                return {}
            get_queryset = getattr(admin_instance, "get_queryset", None)
            if get_queryset is None:
                return {}
            result = get_queryset(req if req is not None else request)
            return result if isinstance(result, dict) else {}

        self.adapter.set_queryset_filter(_filter_for_request)
        try:
            yield
        finally:
            self.adapter._queryset_filter = previous_filter

    async def _check_object_permission(self, request: Request, obj: Any, action: str) -> None:
        """Raise 403 if ``obj`` fails the configured object-level permission check.

        Does nothing when ``options.object_permission_checker`` is ``None``
        (backward compatible — model-level :class:`PermissionChecker` enforcement
        remains the only authz layer in that case).

        Args:
            request: The active request — its ``state.user`` is forwarded to the
                checker.
            obj: The object the user is attempting to act on.
            action: One of ``"view"``, ``"add"``, ``"change"``, ``"delete"`` (or a
                custom codename understood by the checker).
        """
        checker = getattr(self.options, "object_permission_checker", None)
        if checker is None:
            return
        user = getattr(request.state, "user", None)
        if user is None:
            raise HTTPException(status_code=403, detail="Authentication required")
        if not await checker.has_object_permission(user, obj, action):
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
        return await build_filter_metadata(self.model, self.options.list_filter or [], self.adapter)

    def _get_file_fields(self) -> set[str]:
        """Return the set of field names backed by FileType/ImageType columns."""
        from hyperadmin.core.uploads import FileFieldMeta  # noqa: PLC0415

        result: set[str] = set()
        for name, fi in self.model.model_fields.items():
            meta = classify_field(fi, self.model)
            if isinstance(meta, FileFieldMeta):
                result.add(name)
        return result

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
            # Use adapter's list method, scoped to the per-request queryset filter
            # so that ModelAdmin.get_queryset(request) is merged into the WHERE clause.
            with self._request_queryset_filter(request):
                items, total_items = await self.adapter.list(
                    page=page,
                    page_size=page_size,
                    search=search or None,
                    filters=filters_to_apply,
                    order_by=order_by,
                    search_fields=self.search_fields,
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
        file_fields = self._get_file_fields()
        rows = []
        for item in items:
            row: dict[str, Any] = {}
            for field in display_fields:
                if field == "__str__":
                    row[field] = get_display_name(item)
                else:
                    val = getattr(item, field, None)
                    if field in file_fields and val is not None:
                        val = val.name if hasattr(val, "name") else str(val)
                    row[field] = val
            row["id"] = getattr(item, "id", None)
            rows.append(row)

        # Get filter metadata if list_filter is configured
        filter_metadata = await self._get_filter_metadata() if self.options.list_filter else []

        context = {
            "request": request,
            "model_name": self.model.__name__,
            "fields": display_fields,
            "field_labels": self.field_labels,
            "items": rows,
            "pagination": pagination,
            "search_query": search,
            "sort_by": sort_by,
            "sort_direction": sort_direction,
            "filter_metadata": filter_metadata,
            "active_filters": active_filters,
            "can_create": self.options.can_create,
            "can_edit": self.options.can_edit,
            "can_delete": self.options.can_delete,
            "can_detail": self.options.can_detail,
            "file_fields": file_fields,
            "options": self.options,
            "list_editable": list(self.options.list_editable or []),
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
        with self._request_queryset_filter(request):
            item = await self.adapter.get(pk=item_id)

        if not item:
            raise HTTPException(status_code=404, detail="Item not found")

        await self._check_object_permission(request, item, "view")

        file_fields = self._get_file_fields()
        item_data = item.model_dump()
        for fname in file_fields:
            val = getattr(item, fname, None)
            if val is not None:
                item_data[fname] = val.name if hasattr(val, "name") else str(val)

        context = {
            "request": request,
            "item_name": get_display_name(item),
            "item": item_data,
            "field_labels": self.field_labels,
            "actions": self.actions,
            "model_name_lower": self._model_name_lower,
            "file_fields": file_fields,
        }
        template_name = self._get_template_name("detail")
        return self.templates.TemplateResponse(request, template_name, context)

    def _build_inline_formsets(
        self,
        existing_data: dict[str, list[Any]] | None = None,
        request: Request | None = None,
    ) -> list[InlineFormset]:
        """Build ``InlineFormset`` instances for each configured inline spec.

        Args:
            existing_data: Mapping of inline prefix to list of existing related
                model instances (used in update views).
            request: The current HTTP request, used to resolve the ``add_row_url``
                for each inline via ``request.url_for``.
        """
        formsets: list[InlineFormset] = []
        existing = existing_data or {}
        for spec in getattr(self.options, "inlines", []):
            add_row_url = ""
            if request is not None:
                route_name = f"{self._model_name_lower}-inline-add-row"
                try:
                    add_row_url = str(request.url_for(route_name, inline_prefix=spec.model_name))
                except Exception:
                    add_row_url = ""
            formset = InlineFormset(spec=spec, add_row_url=add_row_url)
            instances = existing.get(formset.prefix, [])
            if instances:
                formset.populate_from_instances(instances)
            else:
                formset.build_empty_rows()
            formsets.append(formset)
        return formsets

    async def _build_relation_widgets(
        self,
        field_names: list[str],
        selected_values: dict[str, Any] | None = None,
    ) -> dict[str, HtmxWidget]:
        """Return a widget override dict for relation fields detected by classify_field().

        For each field in *field_names* that resolves to a relation, this method
        either pre-fetches choices (preload=True) or creates a lazy HTMX widget
        (preload=False) pointing at the choices endpoint for that field.
        """
        widgets: dict[str, HtmxWidget] = {}
        sv = selected_values or {}
        dependent_fields: dict[str, str] = getattr(self.options, "dependent_fields", {})

        # Pre-build FK-column → relationship-name mapping via the adapter's inspector
        # so that country_id → "country" for get_choices() and the HTMX URL.
        fk_to_rel: dict[str, str] = {}
        inspector = getattr(self.adapter, "inspector", None)
        if inspector:
            for rel in inspector.relationships:
                for col in rel.local_columns:
                    col_key = getattr(col, "key", None) or getattr(col, "name", None)
                    if col_key:
                        fk_to_rel[col_key] = rel.key

        for name, field_info in self.model.model_fields.items():
            if field_names and name not in field_names:
                continue
            raw_meta = classify_field(field_info, self.model)
            if not isinstance(raw_meta, SelectFieldMeta):
                continue
            if raw_meta.choices_source != "relation":
                continue
            meta = raw_meta
            # Resolve FK column name to relationship name (e.g. country_id → country)
            rel_name: str = fk_to_rel.get(name) or name
            choices_url = f"/{self._model_name_lower}/choices/{rel_name}"
            dependent_on = meta.dependent_on or dependent_fields.get(name)
            choices: list[ChoiceItem]
            if meta.preload:
                raw_choices = await self.adapter.get_choices(rel_name)
                current = str(sv.get(name, ""))
                choices = [
                    ChoiceItem(value=c["value"], label=c["label"], selected=c["value"] == current)
                    for c in raw_choices
                ]
            else:
                choices = []
            if meta.multiple:
                widgets[name] = RelationMultiSelectWidget(
                    choices_url=choices_url,
                    choices=choices,
                    preload=meta.preload,
                    dependent_on=dependent_on,
                )
            else:
                widgets[name] = RelationSelectWidget(
                    choices_url=choices_url,
                    choices=choices,
                    preload=meta.preload,
                    dependent_on=dependent_on,
                )
        return widgets

    async def create_form_view(
        self,
        request: Request,
        values: dict | None = None,
        errors: dict | None = None,
        status_code: int = 200,
        inline_formsets: list[InlineFormset] | None = None,
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
        relation_widgets = await self._build_relation_widgets(
            field_names=create_include or [], selected_values=values
        )
        form = PydanticForm(
            self.model,
            widgets=relation_widgets,
            include=create_include,
            exclude=self.form_create_exclude,
            initial=values or {},
            fieldsets=getattr(self.options, "fieldsets", None) or None,
            form_layout=getattr(self.options, "form_layout", None),
            form_fields=getattr(self.options, "form_fields", None) or None,
        )
        if errors:
            form.bind(values or {})
            norm_errors = {k: (v if isinstance(v, list) else [v]) for k, v in errors.items()}
            form.errors = norm_errors
            for f in form.fields:
                f.errors = norm_errors.get(f.name)

        # Build inline formsets if not provided (e.g. on first render)
        inlines_cfg = getattr(self.options, "inlines", [])
        if inline_formsets is None and inlines_cfg:
            inline_formsets = self._build_inline_formsets(request=request)

        context = {
            "request": request,
            "model_name": self.model.__name__,
            "form": form,
            "values": values or {},
            "errors": errors or {},
            "inline_formsets": inline_formsets or [],
        }
        template_name = self._get_template_name("create")
        return HtmxTemplateResponse(self.templates).render(
            template_name=template_name,
            context=context,
            request=request,
            block="form_body",
            status_code=status_code,
        )

    @staticmethod
    def _extract_form_data(
        form_data: Any,
        form: PydanticForm,
    ) -> dict[str, Any]:
        """Build a data dict from submitted form data, handling multi-value fields.

        For ``MultiSelectWidget`` and ``RelationMultiSelectWidget`` fields, uses
        ``getlist()`` to capture all submitted values.  Absent multiselect fields
        are set to an empty list (mirrors the checkbox-absent pattern).

        ``FileInputWidget`` fields are handled specially: ``UploadFile`` objects
        are kept as-is so that SQLAlchemy's ``FileType``/``ImageType``
        ``process_bind_param`` can write them to storage.  Empty file inputs
        (no file selected) are removed from the dict to avoid overwriting
        existing values.
        """
        data: dict[str, Any] = dict(form_data)
        for field in form.fields:
            is_multi = isinstance(field.widget, (MultiSelectWidget, RelationMultiSelectWidget))
            is_checkbox = isinstance(field.widget, CheckboxInput)
            is_file = isinstance(field.widget, FileInputWidget)
            if is_file:
                upload = form_data.get(field.name)
                if isinstance(upload, StarletteUpload) and upload.filename:
                    data[field.name] = upload
                else:
                    data.pop(field.name, None)
            elif is_multi:
                data[field.name] = form_data.getlist(field.name)
            elif is_checkbox and field.name not in data:
                data[field.name] = False
        return data

    @staticmethod
    def _pop_file_uploads(
        data: dict[str, Any],
        form: PydanticForm,
    ) -> dict[str, Any]:
        """Remove ``UploadFile`` values from *data* so Pydantic validation
        does not choke on non-string file objects.

        Returns a dict of ``{field_name: UploadFile}`` that must be merged
        back into the adapter data after validation succeeds.
        """
        uploads: dict[str, Any] = {}
        for field in form.fields:
            if isinstance(field.widget, FileInputWidget) and field.name in data:
                val = data.pop(field.name)
                if isinstance(val, StarletteUpload):
                    uploads[field.name] = val
        return uploads

    async def create_view(self, request: Request):
        """Handles form submission for creating a new item."""
        await self._check_permission(request, "add")
        form_data = await request.form()

        # Use PydanticForm for consistent binding/validation
        create_include = self.form_include
        if create_include and self.form_create_exclude:
            create_include = [f for f in create_include if f not in self.form_create_exclude]
        relation_widgets = await self._build_relation_widgets(
            field_names=create_include or [],
        )
        form = PydanticForm(
            self.model,
            widgets=relation_widgets,
            include=create_include,
            exclude=self.form_create_exclude,
            fieldsets=getattr(self.options, "fieldsets", None) or None,
            form_layout=getattr(self.options, "form_layout", None),
            form_fields=getattr(self.options, "form_fields", None) or None,
        )
        data = self._extract_form_data(form_data, form)
        file_uploads = self._pop_file_uploads(data, form)
        form.bind(data)
        instance, errs = form.validate(data)

        # Build inline formsets and extract/validate their data
        inline_formsets: list[InlineFormset] = []
        inline_valid_data: list[tuple[InlineFormset, list[dict]]] = []
        has_inline_errors = False
        for spec in getattr(self.options, "inlines", []):
            formset = InlineFormset(spec=spec)
            rows_data = formset.extract_submitted_data(form_data)
            valid_rows, row_errors = formset.validate_rows(rows_data)
            if row_errors:
                has_inline_errors = True
                formset.rebuild_from_submitted(form_data)
            inline_formsets.append(formset)
            inline_valid_data.append((formset, valid_rows))

        if errs or has_inline_errors:
            legacy_errs = {k: v[0] for k, v in errs.items() if v} if errs else {}
            # Rebuild inline formsets from submitted data for re-rendering
            for formset in inline_formsets:
                if not formset.errors:
                    formset.rebuild_from_submitted(form_data)
            return await self.create_form_view(
                request,
                values=data,
                errors=legacy_errs,
                status_code=422,
                inline_formsets=inline_formsets,
            )

        if not instance:
            return await self.create_form_view(
                request,
                values=data,
                errors=errs,
                status_code=422,
                inline_formsets=inline_formsets,
            )

        try:
            create_data = instance.model_dump()
            create_data.update(file_uploads)
            new_item = await self.adapter.create(data=create_data)
        except IntegrityError as exc:
            logger.exception("IntegrityError during create")
            field_errors = _integrity_error_to_field_errors(exc)
            return await self.create_form_view(
                request, values=data, errors=field_errors, status_code=422
            )

        # Save inline rows with the parent PK
        parent_pk = getattr(new_item, "id", None)
        if parent_pk:
            await self._save_inline_rows(inline_valid_data, parent_pk)

        item_id = parent_pk
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
        inline_formsets: list[InlineFormset] | None = None,
    ):
        """Renders the update form, optionally pre-filled with submitted values and errors."""
        await self._check_permission(request, "change")
        with self._request_queryset_filter(request):
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

        relation_widgets = await self._build_relation_widgets(
            field_names=self.form_include or [], selected_values=initial_values
        )
        form = PydanticForm(
            self.model,
            widgets=relation_widgets,
            include=self.form_include,
            initial=initial_values,
            fieldsets=getattr(self.options, "fieldsets", None) or None,
            form_layout=getattr(self.options, "form_layout", None),
            form_fields=getattr(self.options, "form_fields", None) or None,
        )

        if errors:
            form.bind(values or {})
            norm_errors = {k: (v if isinstance(v, list) else [v]) for k, v in errors.items()}
            form.errors = norm_errors
            for f in form.fields:
                f.errors = norm_errors.get(f.name)

        # Build inline formsets from existing related data if not provided
        inlines_cfg = getattr(self.options, "inlines", [])
        if inline_formsets is None and inlines_cfg:
            existing_data: dict[str, list[Any]] = {}
            for spec in getattr(self.options, "inlines", []):
                prefix = spec.model_name
                related = await self.adapter.get_related(pk=item_id, field=spec.relationship_name)
                if related:
                    existing_data[prefix] = list(related)
            inline_formsets = self._build_inline_formsets(existing_data, request=request)

        context = {
            "request": request,
            "model_name": self.model.__name__,
            "item": item,
            "form": form,
            "values": values or initial_values,
            "errors": errors or {},
            "inline_formsets": inline_formsets or [],
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
        with self._request_queryset_filter(request):
            existing = await self.adapter.get(pk=item_id)
        if not existing:
            raise HTTPException(status_code=404, detail="Item not found")
        await self._check_object_permission(request, existing, "change")
        form_data = await request.form()

        relation_widgets = await self._build_relation_widgets(
            field_names=self.form_include or [],
        )
        form = PydanticForm(
            self.model,
            widgets=relation_widgets,
            include=self.form_include,
            fieldsets=getattr(self.options, "fieldsets", None) or None,
            form_layout=getattr(self.options, "form_layout", None),
            form_fields=getattr(self.options, "form_fields", None) or None,
        )
        data = self._extract_form_data(form_data, form)
        file_uploads = self._pop_file_uploads(data, form)

        form.bind(data)
        instance, errs = form.validate(data)

        # Build inline formsets and extract/validate their data
        inline_formsets: list[InlineFormset] = []
        inline_valid_data: list[tuple[InlineFormset, list[dict]]] = []
        has_inline_errors = False
        for spec in getattr(self.options, "inlines", []):
            formset = InlineFormset(spec=spec)
            rows_data = formset.extract_submitted_data(form_data)
            valid_rows, row_errors = formset.validate_rows(rows_data, parent_pk=item_id)
            if row_errors:
                has_inline_errors = True
                formset.rebuild_from_submitted(form_data)
            inline_formsets.append(formset)
            inline_valid_data.append((formset, valid_rows))

        if errs or has_inline_errors:
            legacy_errs = {k: v[0] for k, v in errs.items() if v} if errs else {}
            for formset in inline_formsets:
                if not formset.errors:
                    formset.rebuild_from_submitted(form_data)
            return await self.update_form_view(
                request,
                item_id=item_id,
                values=data,
                errors=legacy_errs,
                status_code=422,
                inline_formsets=inline_formsets,
            )

        if not instance:
            return await self.update_form_view(
                request, item_id=item_id, values=data, errors={}, status_code=422
            )

        # exclude_none: id is not submitted by the form and must not overwrite the PK
        try:
            update_data = instance.model_dump(exclude_none=True)
            update_data.update(file_uploads)
            await self.adapter.update(pk=item_id, data=update_data)
        except IntegrityError as exc:
            logger.exception("IntegrityError during update")
            field_errors = _integrity_error_to_field_errors(exc)
            return await self.update_form_view(
                request, item_id=item_id, values=data, errors=field_errors, status_code=422
            )

        # Save inline rows
        await self._save_inline_rows(inline_valid_data, item_id)

        redirect_url = request.url_for(f"{self.model.__name__.lower()}-list")

        if "hx-request" in request.headers:
            return Response(status_code=200, headers={"HX-Redirect": str(redirect_url)})

        return RedirectResponse(url=redirect_url, status_code=303)

    async def _save_inline_rows(
        self,
        inline_valid_data: list[tuple[InlineFormset, list[dict]]],
        parent_pk: int,
    ) -> None:
        """Persist validated inline rows — create, update, or delete as needed."""
        for formset, rows in inline_valid_data:
            await self.adapter.save_inline_rows(formset.spec, rows, parent_pk)

    async def inline_add_row_view(
        self,
        request: Request,
        inline_prefix: str,
        index: int = 0,
    ) -> Response:
        """HTMX endpoint: returns a single inline row HTML fragment.

        GET /{model_name}/inline/{inline_prefix}/add-row?index=N
        """
        spec = None
        for s in getattr(self.options, "inlines", []):
            if s.model_name == inline_prefix:
                spec = s
                break
        if spec is None:
            raise HTTPException(status_code=404, detail=f"Unknown inline: {inline_prefix!r}")

        formset = InlineFormset(spec=spec)
        row = formset._build_row(index)
        context = {"request": request, "row": row, "inline": formset}
        template = self.templates.get_template("components/inline_row.html")
        html = template.render(context)
        return Response(content=html, media_type="text/html")

    async def choices_view(
        self,
        request: Request,
        field_name: str,
        q: str = "",
        limit: int = 50,
        offset: int = 0,
    ) -> Response:
        """HTMX endpoint: returns an HTML `<option>` fragment for a relation field.

        GET /{model_name}/choices/{field_name}?q=&limit=50&offset=0[&{parent_field}={value}]

        Extra query parameters (beyond q/limit/offset) are forwarded as equality filters
        to ``adapter.get_choices()`` to support cascading selects.
        """
        await self._check_permission(request, "view")
        if limit > _MAX_CHOICES_LIMIT:
            raise HTTPException(
                status_code=400, detail=f"limit {limit} exceeds maximum of {_MAX_CHOICES_LIMIT}"
            )

        # Validate that field_name is a known relation on this model
        inspector = getattr(self.adapter, "inspector", None)
        known_fields = {rel.key for rel in inspector.relationships} if inspector else set()
        if field_name not in known_fields:
            raise HTTPException(status_code=404, detail=f"Unknown relation field: {field_name!r}")

        # Forward any extra query params as cascading filters (e.g. country_id=1)
        reserved = {"q", "limit", "offset"}
        extra_filters = {k: v for k, v in request.query_params.items() if k not in reserved}

        choices = await self.adapter.get_choices(
            field_name, q=q, limit=limit, offset=offset, **extra_filters
        )
        context = {"request": request, "choices": choices}
        template = self.templates.get_template("widgets/choices_options.html")
        html = template.render(context)
        return Response(content=html, media_type="text/html")

    def _resolve_relation_label(self, instance: Any, target_field: str) -> str:
        """Render the option label for ``instance`` per ``AdminOptions.relation_display``.

        Falls back to ``str(instance)`` when no template / callable is configured
        or when rendering raises. The view never crashes a popup response over a
        cosmetic label.
        """
        relation_display = getattr(self.options, "relation_display", None) or {}
        template = relation_display.get(target_field)
        if template is None:
            return str(instance)
        if callable(template):
            try:
                return str(template(instance))
            except Exception:
                logger.warning(
                    "relation_display callable for %r raised; falling back to str()",
                    target_field,
                )
                return str(instance)
        try:
            return template.format(
                **{name: getattr(instance, name, "") for name in instance.model_fields}
            )
        except Exception:
            logger.warning(
                "relation_display template %r raised; falling back to str()", target_field
            )
            return str(instance)

    async def create_popup_view(self, request: Request) -> Response:
        """Inline-create endpoint for FK/M2M autocomplete widgets.

        GET  /{model}/create-popup?target=<field>
            Renders the popup form fragment for the modal.
        POST /{model}/create-popup
            Creates the row. On success returns 200 with an empty body and an
            ``HX-Trigger`` header carrying
            ``{"hyperadminPopupCreated": {"target": <field>, "id": <pk>, "label": <display>}}``
            so the parent widget can insert the new option and close the modal.

        Validation failures keep the modal open by re-rendering the form
        fragment with field-level errors. Permission failures propagate through
        :meth:`_check_permission`.
        """
        await self._check_permission(request, "add")

        if request.method == "GET":
            target = request.query_params.get("target")
            if not target:
                raise HTTPException(status_code=400, detail="target query param required")
            return self._render_popup_form(request, target=target)

        form_data = await request.form()
        target_value = form_data.get("target")
        if not target_value or not isinstance(target_value, str):
            raise HTTPException(status_code=400, detail="target form field required")
        target = target_value

        create_include = self.form_include
        if create_include and self.form_create_exclude:
            create_include = [f for f in create_include if f not in self.form_create_exclude]
        relation_widgets = await self._build_relation_widgets(field_names=create_include or [])
        form = PydanticForm(
            self.model,
            widgets=relation_widgets,
            include=create_include,
            exclude=self.form_create_exclude,
            fieldsets=getattr(self.options, "fieldsets", None) or None,
            form_layout=getattr(self.options, "form_layout", None),
            form_fields=getattr(self.options, "form_fields", None) or None,
        )
        data = self._extract_form_data(form_data, form)
        data.pop("target", None)
        file_uploads = self._pop_file_uploads(data, form)
        form.bind(data)
        instance, errs = form.validate(data)

        if errs or not instance:
            legacy_errs = {k: v[0] for k, v in (errs or {}).items() if v}
            return self._render_popup_form(
                request, target=str(target), values=data, errors=legacy_errs, status_code=200
            )

        try:
            create_data = instance.model_dump()
            create_data.update(file_uploads)
            new_item = await self.adapter.create(data=create_data)
        except IntegrityError as exc:
            logger.exception("IntegrityError during popup create")
            field_errors = _integrity_error_to_field_errors(exc)
            return self._render_popup_form(
                request,
                target=str(target),
                values=data,
                errors=field_errors,
                status_code=200,
            )

        new_pk = getattr(new_item, "id", None)
        label = self._resolve_relation_label(new_item, str(target))
        payload = {
            "hyperadminPopupCreated": {
                "target": str(target),
                "id": new_pk,
                "label": label,
            }
        }
        import json as _json  # noqa: PLC0415

        return Response(
            content="",
            status_code=200,
            headers={"HX-Trigger": _json.dumps(payload)},
        )

    def _render_popup_form(
        self,
        request: Request,
        target: str,
        values: dict[str, Any] | None = None,
        errors: dict[str, str] | None = None,
        status_code: int = 200,
    ) -> Response:
        """Render the popup-form fragment used both for initial GET and error re-renders."""
        create_include = self.form_include
        if create_include and self.form_create_exclude:
            create_include = [f for f in create_include if f not in self.form_create_exclude]
        form = PydanticForm(
            self.model,
            include=create_include,
            exclude=self.form_create_exclude,
            initial=values or {},
            fieldsets=getattr(self.options, "fieldsets", None) or None,
            form_layout=getattr(self.options, "form_layout", None),
            form_fields=getattr(self.options, "form_fields", None) or None,
        )
        if errors:
            form.bind(values or {})
            norm = {k: [v] for k, v in errors.items()}
            form.errors = norm
            for fld in form.fields:
                fld.errors = norm.get(fld.name)
        context = {
            "request": request,
            "model_name": self.model.__name__,
            "form": form,
            "target": target,
            "values": values or {},
            "errors": errors or {},
            "post_url": request.url_for(f"{self._model_name_lower}-create-popup"),
        }
        return self.templates.TemplateResponse(
            request,
            "widgets/popup_form.html",
            context,
            status_code=status_code,
        )

    async def upload_file_view(
        self,
        request: Request,
        field_name: str,  # noqa: ARG002 — path param required by route
    ) -> Response:
        """Accept a file upload and store it via the configured storage.

        ``POST /{model}/upload/{field_name}``

        Returns a JSON response with the stored filename.
        """
        await self._check_permission(request, "add")
        if not self.storage:
            raise HTTPException(
                status_code=400,
                detail="File uploads not configured",
            )
        form_data = await request.form()
        upload = form_data.get("file")
        if not isinstance(upload, StarletteUpload) or not upload.filename:
            raise HTTPException(status_code=400, detail="No file provided")
        filename = self.storage.write(upload.file, upload.filename)
        from starlette.responses import JSONResponse  # noqa: PLC0415

        return JSONResponse({"filename": filename})

    async def delete_file_view(
        self,
        request: Request,
        item_id: int,
        field_name: str,
    ) -> Response:
        """Delete a file from storage and clear the field on the record.

        ``DELETE /{model}/{item_id}/file/{field_name}``
        """
        await self._check_permission(request, "change")
        item = await self.adapter.get(pk=item_id)
        if not item:
            raise HTTPException(status_code=404, detail="Item not found")
        val = getattr(item, field_name, None)
        if val and self.storage:
            fname = val.name if hasattr(val, "name") else str(val)
            path = self.storage.get_path(fname)
            if os.path.exists(path):  # noqa: ASYNC240 — sync I/O acceptable for local file cleanup
                os.remove(path)
        await self.adapter.update(pk=item_id, data={field_name: None})
        if "hx-request" in request.headers:
            return Response(
                status_code=200,
                headers={"HX-Trigger": "fileDeleted"},
            )
        return Response(status_code=204)

    def _collect_file_paths(self, item: Any) -> list[str]:
        """Return disk paths of all files attached to *item*.

        The paths are collected **before** the DB row is deleted so that
        ``ImageType.process_result_value`` (which opens the file) is not
        called after the file has already been removed.
        """
        if not self.storage:
            return []
        from hyperadmin.core.uploads import FileFieldMeta  # noqa: PLC0415

        paths: list[str] = []
        for name, fi in self.model.model_fields.items():
            meta = classify_field(fi, self.model)
            if not isinstance(meta, FileFieldMeta):
                continue
            val = getattr(item, name, None)
            if not val:
                continue
            fname = val.name if hasattr(val, "name") else str(val)
            paths.append(self.storage.get_path(fname))
        return paths

    @staticmethod
    def _remove_files(paths: list[str]) -> None:
        """Remove files from disk, ignoring missing ones."""
        for path in paths:
            if os.path.exists(path):
                os.remove(path)

    def _is_inline_editable(self, field: str) -> bool:
        """Return True if ``field`` is in the list_editable allow-list and on the schema.

        The primary key (``id``) is never editable inline.
        """
        if field == "id":
            return False
        if field not in self.model.model_fields:
            return False
        return field in (self.options.list_editable or [])

    async def inline_edit_form_view(
        self,
        request: Request,
        item_id: int,
        field: str,
        cancel: int = Query(0),
    ):
        """Renders the inline editor fragment for a single editable cell.

        ``?cancel=1`` returns the static cell instead — used by the Cancel
        button in the editor to restore the read-only view without hitting
        a separate endpoint.
        """
        if not self._is_inline_editable(field):
            raise HTTPException(status_code=403, detail="Field not editable")

        item = await self.adapter.get(pk=item_id)
        if not item:
            raise HTTPException(status_code=404, detail="Item not found")

        if cancel:
            context = {
                "request": request,
                "model_name": self.model.__name__,
                "item": item,
                "field": field,
                "saved": False,
            }
            return self.templates.TemplateResponse(request, "components/inline_cell.html", context)

        # Build a single-field form so we reuse widget selection + validation
        form = PydanticForm(self.model, include=[field], initial={field: getattr(item, field)})
        form_field = next((f for f in form.fields if f.name == field), None)
        if form_field is None:
            # Field is not exposed by PydanticForm (e.g. auto-now / id) — treat as not editable
            raise HTTPException(status_code=403, detail="Field not editable")

        context = {
            "request": request,
            "model_name": self.model.__name__,
            "item": item,
            "field": field,
            "form_field": form_field,
            "form": form,
        }
        return self.templates.TemplateResponse(request, "components/inline_editor.html", context)

    async def inline_save_view(self, request: Request, item_id: int, field: str):
        """Validates and persists a single field for ``item_id``."""
        if not self._is_inline_editable(field):
            raise HTTPException(status_code=403, detail="Field not editable")

        item = await self.adapter.get(pk=item_id)
        if not item:
            raise HTTPException(status_code=404, detail="Item not found")

        form_data = await request.form()
        raw_value: Any = form_data.get(field)

        # Reuse the full-model PydanticForm to keep validation rules consistent
        # with the per-row update form. We seed it with the current row dump
        # and only override the edited field — ensures min_length/required etc.
        # apply identically.
        current = item.model_dump() if hasattr(item, "model_dump") else dict(item.__dict__)
        merged = dict(current)
        merged[field] = raw_value

        form = PydanticForm(self.model)
        form_field = next((f for f in form.fields if f.name == field), None)
        if form_field is None:
            raise HTTPException(status_code=403, detail="Field not editable")

        # Unchecked checkbox semantics: bool fields with no value submitted → False
        if isinstance(form_field.widget, CheckboxInput) and field not in form_data:
            merged[field] = False

        instance, errs = form.validate(merged)
        field_errors = errs.get(field) if errs else None
        if field_errors:
            error_form_field = next((f for f in form.fields if f.name == field), None)
            if error_form_field is not None:
                error_form_field.value = raw_value
                error_form_field.errors = field_errors
            context = {
                "request": request,
                "model_name": self.model.__name__,
                "item": item,
                "field": field,
                "form_field": error_form_field,
                "errors": field_errors,
                "current_value": getattr(item, field),
            }
            return self.templates.TemplateResponse(
                request, "components/inline_cell_error.html", context, status_code=422
            )

        if not instance:
            # Validation failed for a *different* field; we still reject the save.
            return self.templates.TemplateResponse(
                request,
                "components/inline_cell_error.html",
                {
                    "request": request,
                    "model_name": self.model.__name__,
                    "item": item,
                    "field": field,
                    "form_field": form_field,
                    "errors": ["Invalid value"],
                    "current_value": getattr(item, field),
                },
                status_code=422,
            )

        # Persist only the edited field — exclude_unset would also work, but
        # we know precisely what changed.
        new_value = getattr(instance, field)
        await self.adapter.update(pk=item_id, data={field: new_value})

        # Re-fetch to get the canonical stored value (e.g. type coercion)
        refreshed = await self.adapter.get(pk=item_id)
        context = {
            "request": request,
            "model_name": self.model.__name__,
            "item": refreshed,
            "field": field,
            "options": self.options,
            "saved": True,
        }
        # Announce save via aria-live region using an HX-Trigger event.
        # OOB swaps are avoided here because they don't compose cleanly when
        # the primary swap target is a single <td> element.
        response = self.templates.TemplateResponse(request, "components/inline_cell.html", context)
        response.headers["HX-Trigger-After-Swap"] = (
            '{"hyperadmin:cell-saved": {"field": "' + field + '"}}'
        )
        return response

    async def delete_action(self, request: Request, item_id: int):
        """Deletes an item."""
        await self._check_permission(request, "delete")
        with self._request_queryset_filter(request):
            item = await self.adapter.get(pk=item_id)
        if not item:
            raise HTTPException(status_code=404, detail="Item not found")

        await self._check_object_permission(request, item, "delete")

        file_paths = self._collect_file_paths(item)
        await self.adapter.delete(pk=item_id)
        self._remove_files(file_paths)

        redirect_url = request.url_for(f"{self.model.__name__.lower()}-list")

        if "hx-request" in request.headers:
            return Response(status_code=200, headers={"HX-Redirect": str(redirect_url)})

        return RedirectResponse(url=redirect_url, status_code=303)

    async def run_action(self, request: Request, item_id: int, action_name: str) -> Response:
        """Dispatch a custom action registered via ``@action`` on the ModelAdmin.

        POST /{model_name}/{item_id}/action/{action_name}

        Returns an HTMX redirect to the model list on success, or delegates to the
        handler's return value when it returns a :class:`starlette.responses.Response`.
        """
        action_def = self._action_map.get(action_name)
        if action_def is None:
            raise HTTPException(status_code=404, detail=f"Action '{action_name}' not found")

        await self._check_permission(request, f"action_{action_name}")

        result = await action_def.handler(self._admin_instance, request, item_id)

        if isinstance(result, Response):
            return result

        redirect_url = request.url_for(f"{self._model_name_lower}-list")
        if "hx-request" in request.headers:
            return Response(status_code=200, headers={"HX-Redirect": str(redirect_url)})
        return RedirectResponse(url=redirect_url, status_code=303)

    def _resolve_bulk_action(self, action_name: str) -> ActionDef:
        """Return the bulk ``ActionDef`` for ``action_name`` or raise 404."""
        action_def = self._action_map.get(action_name)
        if action_def is None or not action_def.bulk:
            raise HTTPException(status_code=404, detail=f"Bulk action '{action_name}' not found")
        return action_def

    @staticmethod
    def _parse_ids(form: Any) -> list[int]:
        """Parse the ``ids`` multi-valued form field into a list of ints.

        Silently drops entries that aren't parseable as integers — those would
        not match any row anyway.
        """
        raw = form.getlist("ids") if hasattr(form, "getlist") else []
        parsed: list[int] = []
        for value in raw:
            try:
                parsed.append(int(value))
            except (TypeError, ValueError):
                continue
        return parsed

    async def _execute_bulk(
        self,
        request: Request,
        action_def: ActionDef,
        ids: list[int],
        params: Any | None,
    ) -> list[BulkRowResult]:
        """Run ``action_def.handler`` over ``ids`` with per-row outcome capture.

        Each row is wrapped in object-permission re-check + exception capture so
        a single failure cannot abort the whole bulk run.
        """
        outcomes: list[BulkRowResult] = []
        permission_codename = f"action_{action_def.name}"
        for item_id in ids:
            try:
                item = await self.adapter.get(pk=item_id)
            except Exception as exc:
                outcomes.append(BulkRowResult(id=item_id, status="failed", detail=str(exc)))
                continue
            if item is None:
                outcomes.append(BulkRowResult(id=item_id, status="failed", detail="not found"))
                continue
            try:
                await self._check_object_permission(request, item, permission_codename)
            except HTTPException as exc:
                outcomes.append(
                    BulkRowResult(id=item_id, status="forbidden", detail=str(exc.detail))
                )
                continue
            try:
                await action_def.handler(self._admin_instance, request, item_id, params=params)
            except HTTPException as exc:
                status: BulkRowStatus = "forbidden" if exc.status_code == 403 else "failed"
                outcomes.append(BulkRowResult(id=item_id, status=status, detail=str(exc.detail)))
            except Exception as exc:
                logger.warning(
                    "Bulk action %r failed on row %s: %s",
                    action_def.name,
                    item_id,
                    exc,
                )
                outcomes.append(BulkRowResult(id=item_id, status="failed", detail=str(exc)))
            else:
                outcomes.append(BulkRowResult(id=item_id, status="ok", detail=None))
        return outcomes

    def _render_bulk_result(
        self,
        request: Request,
        action_def: ActionDef,
        outcomes: list[BulkRowResult],
    ) -> Response:
        """Render the per-row result page (or HTMX fragment)."""
        context = {
            "request": request,
            "action": action_def,
            "outcomes": outcomes,
            "model_name": self._model_name_lower,
            "bulk_endpoint_url": request.url_for(
                f"{self._model_name_lower}-bulk-action", action_name=action_def.name
            ),
            "failed_ids": [o.id for o in outcomes if o.status != "ok"],
        }
        return self.templates.TemplateResponse(request, "components/bulk_result.html", context)

    def _render_bulk_form(
        self,
        request: Request,
        action_def: ActionDef,
        ids: list[int],
        errors: dict[str, list[str]] | None = None,
    ) -> Response:
        """Render the Pydantic-derived parameter form before bulk execution."""
        form_model = action_def.form
        fields: list[dict[str, Any]] = []
        if form_model is not None:
            for name, info in form_model.model_fields.items():
                fields.append(
                    {
                        "name": name,
                        "label": info.title or name.replace("_", " ").capitalize(),
                        "required": info.is_required,
                        "input_type": "number" if info.annotation is int else "text",
                        "errors": (errors or {}).get(name, []),
                    }
                )
        context = {
            "request": request,
            "action": action_def,
            "ids": ids,
            "fields": fields,
            "model_name": self._model_name_lower,
            "confirm_url": request.url_for(
                f"{self._model_name_lower}-bulk-action-confirm",
                action_name=action_def.name,
            ),
        }
        return self.templates.TemplateResponse(request, "components/bulk_form.html", context)

    async def run_bulk_action(self, request: Request, action_name: str) -> Response:
        """Entry point for bulk actions.

        ``POST /{model}/actions/{name}/bulk``

        - When the action declares a Pydantic ``form``, this endpoint renders the
          parameter-collection form with the selected ids preserved.
        - Otherwise it executes the handler per row and renders the per-row
          result page.
        """
        action_def = self._resolve_bulk_action(action_name)
        await self._check_permission(request, f"action_{action_name}")

        form = await request.form()
        ids = self._parse_ids(form)

        if action_def.requires_selection and not ids:
            raise HTTPException(status_code=400, detail="Selection required")

        if action_def.form is not None:
            return self._render_bulk_form(request, action_def, ids)

        outcomes = await self._execute_bulk(request, action_def, ids, params=None)
        return self._render_bulk_result(request, action_def, outcomes)

    async def confirm_bulk_action(self, request: Request, action_name: str) -> Response:
        """Validate the Pydantic param form and execute the bulk handler.

        ``POST /{model}/actions/{name}/bulk/confirm``
        """
        action_def = self._resolve_bulk_action(action_name)
        await self._check_permission(request, f"action_{action_name}")

        if action_def.form is None:
            raise HTTPException(
                status_code=404, detail=f"Bulk action '{action_name}' has no confirm step"
            )

        form = await request.form()
        ids = self._parse_ids(form)

        if action_def.requires_selection and not ids:
            raise HTTPException(status_code=400, detail="Selection required")

        form_model = action_def.form
        payload = {key: value for key, value in form.items() if key not in {"ids"}}
        try:
            params = form_model(**payload)
        except ValidationError as exc:
            errors: dict[str, list[str]] = {}
            for err in exc.errors():
                loc = err.get("loc") or ("__all__",)
                field = str(loc[0])
                errors.setdefault(field, []).append(str(err.get("msg", "invalid")))
            return self._render_bulk_form(request, action_def, ids, errors=errors)

        outcomes = await self._execute_bulk(request, action_def, ids, params=params)
        return self._render_bulk_result(request, action_def, outcomes)


async def admin_dashboard(request: Request, templates: Jinja2Templates):
    """Renders the main admin dashboard page."""
    context = {"request": request}
    return templates.TemplateResponse(request, "dashboard.html", context)
