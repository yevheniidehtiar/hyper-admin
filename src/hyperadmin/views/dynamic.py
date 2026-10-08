import functools
import logging
import math
import os
import re
import uuid
from collections.abc import Awaitable, Callable, Generator
from contextlib import contextmanager
from http import HTTPStatus
from pathlib import PurePosixPath
from typing import TYPE_CHECKING, Any, TypeVar, Union, cast, get_args, get_origin

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
from hyperadmin.core.adapters import InlineRowNotOwned, queryset_scope
from hyperadmin.core.bulk_results import BulkRowResult, BulkRowStatus
from hyperadmin.core.choices import ChoiceItem, SelectFieldMeta
from hyperadmin.core.discovery import build_filter_metadata
from hyperadmin.core.display import get_display_name
from hyperadmin.core.fields import classify_field
from hyperadmin.core.options import AdminOptions
from hyperadmin.core.registry import site
from hyperadmin.core.sensitive import is_sensitive, sensitive_field_names
from hyperadmin.core.storage_paths import resolve_storage_path, storage_root
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

_HandlerT = TypeVar("_HandlerT", bound=Callable[..., Awaitable[Any]])


def _request_scoped(handler: _HandlerT) -> _HandlerT:
    """Run a ``DynamicModelView`` handler inside its request's queryset scope.

    Every adapter call the handler makes (``get``, ``list``, ``update``,
    ``get_choices``, ...) therefore applies the registered ``get_queryset`` row
    filters of the request being served, and never another request's.
    """

    @functools.wraps(handler)
    async def wrapper(self: "DynamicModelView", request: Request, *args: Any, **kwargs: Any) -> Any:
        with self._request_queryset_filter(request):
            return await handler(self, request, *args, **kwargs)

    return cast("_HandlerT", wrapper)


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
        admin_lookup: Callable[[Any], Any] | None = None,
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
        self._admin_lookup = admin_lookup
        self._fallback_admins: dict[Any, Any] = {}
        # Expose the live adapter on the admin instance so action handlers can use self.adapter
        if admin_instance is not None:
            admin_instance.adapter = self.adapter

    async def _has_permission(self, request: Request, codename: str) -> bool:
        """Return whether the request's user holds ``codename`` (always true without auth)."""
        if self.permission_checker is None:
            return True
        user = getattr(request.state, "user", None)
        if user is None:
            raise HTTPException(status_code=403, detail="Authentication required")
        return bool(await self.permission_checker.has_permission(user, codename))

    async def _check_permission(
        self, request: Request, action: str, *, model_name: str | None = None
    ) -> None:
        """Raise 403 if the user lacks the required permission.

        ``model_name`` defaults to this view's model; pass another lowercase model
        name to check a related model (choices target, inline model).

        Does nothing when ``permission_checker`` is ``None`` (auth disabled).
        """
        codename = f"{action}_{model_name or self._model_name_lower}"
        if not await self._has_permission(request, codename):
            raise HTTPException(status_code=403, detail="Permission denied")

    async def _check_any_permission(self, request: Request, actions: tuple[str, ...]) -> None:
        """Raise 403 unless the user holds at least one of ``actions`` on this model."""
        for action in actions:
            if await self._has_permission(request, f"{action}_{self._model_name_lower}"):
                return
        raise HTTPException(status_code=403, detail="Permission denied")

    def _admin_for_model(self, model: Any) -> Any:
        """Return the registered ``ModelAdmin`` instance for ``model`` (or ``None``)."""
        if model is self.model:
            return self._admin_instance
        if self._admin_lookup is not None:
            return self._admin_lookup(model)
        if model not in self._fallback_admins:
            admin_class = site._registry.get(model)
            self._fallback_admins[model] = admin_class(model) if admin_class else None
        return self._fallback_admins[model]

    def _is_registered(self, model: Any) -> bool:
        """Return whether ``model`` has its own registered admin (and thus permission rows)."""
        return model is self.model or self._admin_for_model(model) is not None

    async def _may_view_related(self, request: Request, target_model: Any) -> bool:
        """Return whether rows of ``target_model`` may be disclosed to the request's user.

        Single gate for every path that embeds related rows: the choices
        endpoint, list-page FK filters and the create/edit relation widgets.
        A registered target needs ``view_<target>``. An unregistered target has
        no permission rows that could ever be granted, so it falls back to the
        source model's permission, which every caller has already checked.
        """
        if target_model is None or not self._is_registered(target_model):
            return True
        return await self._has_permission(request, f"view_{target_model.__name__.lower()}")

    def _relation_target_for_field(self, name: str) -> Any:
        """Return the target class of the relation rendered for field ``name`` (or ``None``)."""
        rel_name = self._fk_to_relation().get(name) or name
        return self._relation_targets().get(rel_name)

    def _queryset_filter_for(self, model: Any) -> Callable[[Any], dict[str, Any]] | None:
        """Return the ``get_queryset`` callable that scopes rows of ``model``."""
        get_queryset = getattr(self._admin_for_model(model), "get_queryset", None)
        if get_queryset is None:
            return None

        def _filter(req: Any) -> dict[str, Any]:
            result = get_queryset(req)
            return result if isinstance(result, dict) else {}

        return _filter

    @contextmanager
    def _request_queryset_filter(self, request: Request) -> Generator[None, None, None]:
        """Activate this request's row scoping for every adapter call made inside the block.

        Composes :meth:`hyperadmin.core.model.ModelAdmin.get_queryset` of this view's
        model (and of related models, for the choices endpoint) into a
        request-scoped :func:`hyperadmin.core.adapters.queryset_scope`. The scope is
        held in a ``ContextVar``, never on the shared adapter instance, so
        concurrent requests cannot observe each other's filters.
        """
        with queryset_scope(request, self._queryset_filter_for):
            yield

    def _fk_to_relation(self) -> dict[str, str]:
        """Map each FK column on the model to the name of its ORM relationship."""
        fk_to_rel: dict[str, str] = {}
        inspector = getattr(self.adapter, "inspector", None)
        if inspector:
            for rel in inspector.relationships:
                for col in getattr(rel, "local_columns", []):
                    col_key = getattr(col, "key", None) or getattr(col, "name", None)
                    if col_key:
                        fk_to_rel[col_key] = rel.key
        return fk_to_rel

    def _declared_cascade_keys(self, rel_name: str) -> set[str]:
        """Return the parent-field names a relation widget declares it depends on.

        Sources: ``SelectFieldMeta.dependent_on``, ``AdminOptions.dependent_fields``
        and ``AdminOptions.relation_filters``, keyed by the FK column (or the
        relationship name) that renders the ``rel_name`` widget. Sensitive names
        are never accepted.
        """
        fk_to_rel = self._fk_to_relation()
        owners = {name for name, rel in fk_to_rel.items() if rel == rel_name} | {rel_name}
        dependent_fields = getattr(self.options, "dependent_fields", None) or {}
        relation_filters = getattr(self.options, "relation_filters", None) or {}
        model_fields = getattr(self.model, "model_fields", {})
        keys: set[str] = set()
        for name in owners:
            if dependent_fields.get(name):
                keys.add(dependent_fields[name])
            dependency = relation_filters.get(name)
            if dependency is not None:
                keys.add(dependency.depends_on)
            field_info = model_fields.get(name)
            if field_info is not None:
                meta = classify_field(field_info, self.model)
                if isinstance(meta, SelectFieldMeta) and meta.dependent_on:
                    keys.add(meta.dependent_on)
        return {k for k in keys if k not in self._sensitive_fields and not is_sensitive(k)}

    def _relation_targets(self) -> dict[str, Any]:
        """Map each ORM relationship name on the model to its target class (or ``None``)."""
        inspector = getattr(self.adapter, "inspector", None)
        if not inspector:
            return {}
        return {
            rel.key: getattr(getattr(rel, "mapper", None), "class_", None)
            for rel in inspector.relationships
        }

    async def _get_or_404(self, item_id: Any) -> Any:
        """Load ``item_id`` under the active queryset scope or raise 404."""
        item = await self.adapter.get(pk=item_id)
        if not item:
            raise HTTPException(status_code=404, detail="Item not found")
        return item

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

    async def _get_filter_metadata(self, request: Request) -> list[dict[str, Any]]:
        """Introspects list_filter fields to build metadata for filter UI.

        A relation filter lists rows of the target model, so it is only built
        when the user may view that model (see :meth:`_may_view_related`).
        """
        allowed = self._filterable_fields()
        fields = [
            f
            for f in (self.options.list_filter or [])
            if f in allowed
            and await self._may_view_related(request, self._relation_target_for_field(f))
        ]
        return await build_filter_metadata(self.model, fields, self.adapter)

    @functools.cached_property
    def _sensitive_fields(self) -> frozenset[str]:
        """Names of the model's sensitive fields (see :mod:`hyperadmin.core.sensitive`)."""
        overrides = getattr(self.options, "sensitive_fields", None) or None
        return frozenset(sensitive_field_names(self.model, overrides))

    def _without_sensitive(self, values: dict[str, Any]) -> dict[str, Any]:
        """Return ``values`` without sensitive keys (detail page, form initial values)."""
        return {k: v for k, v in values.items() if k not in self._sensitive_fields}

    def _keep_stored_secrets(self, data: dict[str, Any], existing: Any) -> None:
        """Write-only semantics: an empty sensitive input keeps the stored value."""
        for name in self._sensitive_fields:
            if name in self.model.model_fields and data.get(name) in (None, ""):
                data[name] = getattr(existing, name, None)

    def _filterable_fields(self) -> set[str]:
        """Fields a URL ``filter_<name>`` may target: ``list_filter`` minus sensitive fields."""
        model_fields = getattr(self.model, "model_fields", {})
        return {
            f
            for f in (getattr(self.options, "list_filter", None) or [])
            if f in model_fields and f not in self._sensitive_fields
        }

    def _sortable_fields(self) -> set[str]:
        """Fields ``sort_by`` may target: displayed, real, non-sensitive model fields."""
        model_fields = getattr(self.model, "model_fields", {})
        return {
            f for f in self.column_list if f in model_fields and f not in self._sensitive_fields
        }

    def _default_sort_field(self) -> str:
        """The first non-sensitive model field (``id`` when there is none)."""
        model_fields = getattr(self.model, "model_fields", {})
        return next((f for f in model_fields if f not in self._sensitive_fields), "id")

    def _get_file_fields(self) -> set[str]:
        """Return the set of field names backed by FileType/ImageType columns."""
        from hyperadmin.core.uploads import FileFieldMeta  # noqa: PLC0415

        result: set[str] = set()
        for name, fi in self.model.model_fields.items():
            meta = classify_field(fi, self.model)
            if isinstance(meta, FileFieldMeta):
                result.add(name)
        return result

    @_request_scoped
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

        # Parse filters from query params. Only whitelisted (list_filter),
        # non-sensitive model fields are honoured; anything else is ignored so
        # the URL cannot become an equality oracle on arbitrary columns.
        allowed_filters = self._filterable_fields()
        active_filters: dict[str, str] = {}
        filters_to_apply: dict[str, Any] = {}
        for key, value in request.query_params.items():
            if key.startswith("filter_") and value:
                field_name = key[7:]
                if field_name not in allowed_filters:
                    logger.debug("Ignoring filter on non-whitelisted field %r", field_name)
                    continue
                active_filters[field_name] = value

                # Type conversion for bool
                ann = self.model.model_fields[field_name].annotation
                if ann is bool or (get_origin(ann) is Union and bool in get_args(ann)):
                    filters_to_apply[field_name] = value.lower() == "true"
                else:
                    filters_to_apply[field_name] = value

        # sort_by is whitelisted against the sortable displayed columns. An
        # unknown or sensitive value falls back to the default sort.
        if sort_by and sort_by not in self._sortable_fields():
            logger.debug("Ignoring sort on non-sortable field %r", sort_by)
            sort_by = ""
            sort_direction = "asc"
        if not sort_by:
            sort_by = self._default_sort_field()

        # Format order_by for adapter (use negative prefix for descending)
        order_by = f"-{sort_by}" if sort_direction == "desc" else sort_by

        try:
            # The handler runs inside the request's queryset scope, so
            # ModelAdmin.get_queryset(request) is merged into the WHERE clause.
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
        filter_metadata = (
            await self._get_filter_metadata(request) if self.options.list_filter else []
        )

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

    @_request_scoped
    async def detail_view(self, request: Request, item_id: int):
        """
        Renders the detail view for a single item.
        Assumes the model has an 'id' field.
        """
        await self._check_permission(request, "view")
        item = await self._get_or_404(item_id)

        await self._check_object_permission(request, item, "view")

        file_fields = self._get_file_fields()
        item_data = self._without_sensitive(item.model_dump())
        for fname in file_fields - self._sensitive_fields:
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
        request: Request | None = None,
    ) -> dict[str, HtmxWidget]:
        """Return a widget override dict for relation fields detected by classify_field().

        For each field in *field_names* that resolves to a relation, this method
        either pre-fetches choices (preload=True) or creates a lazy HTMX widget
        (preload=False) pointing at the choices endpoint for that field.

        When the user may not view the target model, no target row is fetched:
        the widget only carries the currently selected key(s), labelled
        ``"<Model> (<pk>)"``, so saving the form keeps the stored value.
        """
        widgets: dict[str, HtmxWidget] = {}
        sv = selected_values or {}
        dependent_fields: dict[str, str] = getattr(self.options, "dependent_fields", {})

        # FK-column → relationship-name mapping so that country_id → "country"
        # for get_choices() and the HTMX URL.
        fk_to_rel = self._fk_to_relation()

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
            target = self._relation_target_for_field(name)
            if request is not None and not await self._may_view_related(request, target):
                choices = self._opaque_selected_choices(target, sv.get(name))
            elif meta.preload:
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

    @staticmethod
    def _opaque_selected_choices(target: Any, current: Any) -> list[ChoiceItem]:
        """Choices for the selected key(s) only, labelled without reading the target row."""
        if current in (None, ""):
            return []
        values = current if isinstance(current, (list, tuple, set)) else [current]
        target_name = getattr(target, "__name__", "Item")
        return [
            ChoiceItem(value=str(v), label=f"{target_name} ({v})", selected=True)
            for v in values
            if v not in (None, "")
        ]

    @_request_scoped
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
            request=request, field_names=create_include or [], selected_values=values
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

    @_request_scoped
    async def create_view(self, request: Request):
        """Handles form submission for creating a new item."""
        await self._check_permission(request, "add")
        form_data = await request.form()

        # Use PydanticForm for consistent binding/validation
        create_include = self.form_include
        if create_include and self.form_create_exclude:
            create_include = [f for f in create_include if f not in self.form_create_exclude]
        relation_widgets = await self._build_relation_widgets(
            request=request,
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

        # A new parent owns no children yet: any submitted child pk is foreign.
        await self._authorize_inline_rows(request, inline_valid_data, parent_pk=None)

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

    @_request_scoped
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
        item = await self._get_or_404(item_id)
        await self._check_object_permission(request, item, "change")

        initial_func = getattr(item, "model_dump", None)
        initial_values = cast(
            "dict[str, Any]",
            initial_func() if callable(initial_func) else getattr(item, "__dict__", {}),
        )

        # Override with re-submitted values on validation failure
        if values:
            initial_values.update(values)

        # Sensitive fields are write-only: never render their stored value.
        initial_values = self._without_sensitive(initial_values)
        if values:
            values = self._without_sensitive(values)

        relation_widgets = await self._build_relation_widgets(
            request=request, field_names=self.form_include or [], selected_values=initial_values
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

    @_request_scoped
    async def update_view(self, request: Request, item_id: int):
        """Handles form submission for updating an item."""
        await self._check_permission(request, "change")
        existing = await self._get_or_404(item_id)
        await self._check_object_permission(request, existing, "change")
        form_data = await request.form()

        relation_widgets = await self._build_relation_widgets(
            request=request,
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
        self._keep_stored_secrets(data, existing)

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

        # Ownership and inline-model permissions are checked before any write.
        await self._authorize_inline_rows(request, inline_valid_data, parent_pk=item_id)

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
            try:
                await self.adapter.save_inline_rows(formset.spec, rows, parent_pk)
            except InlineRowNotOwned as exc:
                raise HTTPException(status_code=404, detail="Inline row not found") from exc

    async def _authorize_inline_rows(
        self,
        request: Request,
        inline_valid_data: list[tuple[InlineFormset, list[dict]]],
        parent_pk: Any,
    ) -> None:
        """Reject foreign child rows (404) and rows the user may not write (403).

        Runs before any write. A submitted ``<prefix>-<i>-pk`` is never trusted
        on its own: it must be an existing child of ``parent_pk`` (``None`` for a
        parent being created, which owns no rows). Each row also needs the
        inline model's own ``add`` / ``change`` / ``delete`` permission when that
        model is registered (see :meth:`_is_registered`).
        """
        for formset, rows in inline_valid_data:
            try:
                await self.adapter.ensure_inline_rows_owned(formset.spec, rows, parent_pk)
            except InlineRowNotOwned as exc:
                raise HTTPException(status_code=404, detail="Inline row not found") from exc
            if not self._is_registered(formset.spec.model):
                # An unregistered inline model has no permission rows that could
                # ever be granted: the parent's add/change check (made by the
                # calling handler) governs its rows.
                continue
            needed: set[str] = set()
            for row in rows:
                if row.get("_delete"):
                    needed.add("delete")
                elif row.get("_pk") is not None:
                    needed.add("change")
                else:
                    needed.add("add")
            for verb in sorted(needed):
                await self._check_permission(request, verb, model_name=formset.spec.model_name)

    @_request_scoped
    async def inline_add_row_view(
        self,
        request: Request,
        inline_prefix: str,
        index: int = 0,
    ) -> Response:
        """HTMX endpoint: returns a single inline row HTML fragment.

        GET /{model_name}/inline/{inline_prefix}/add-row?index=N
        """
        await self._check_any_permission(request, ("add", "change"))
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

    @_request_scoped
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

        Only the cascade keys declared for this relation's widget (``dependent_on``,
        ``AdminOptions.dependent_fields`` / ``relation_filters``) are forwarded as
        equality filters to ``adapter.get_choices()``; any other query parameter
        is ignored, so the endpoint is not an equality oracle on the target model.
        The target model's admin ``get_queryset`` applies through the request scope.
        """
        await self._check_permission(request, "view")
        if limit > _MAX_CHOICES_LIMIT:
            raise HTTPException(
                status_code=400, detail=f"limit {limit} exceeds maximum of {_MAX_CHOICES_LIMIT}"
            )

        # Validate that field_name is a known relation on this model
        targets = self._relation_targets()
        if field_name not in targets:
            raise HTTPException(status_code=404, detail=f"Unknown relation field: {field_name!r}")

        # Listing related rows discloses the target model: require view on it too.
        if not await self._may_view_related(request, targets[field_name]):
            raise HTTPException(status_code=403, detail="Permission denied")

        # Forward only the declared cascade keys (e.g. country_id=1)
        declared = self._declared_cascade_keys(field_name)
        extra_filters = {k: v for k, v in request.query_params.items() if k in declared}
        ignored = set(request.query_params) - declared - {"q", "limit", "offset"}
        if ignored:
            logger.debug("Ignoring undeclared choices parameters %s", sorted(ignored))

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

    @_request_scoped
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
        relation_widgets = await self._build_relation_widgets(
            field_names=create_include or [], request=request
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

    @_request_scoped
    async def upload_file_view(
        self,
        request: Request,
        field_name: str,
    ) -> Response:
        """Accept a file upload and store it via the configured storage.

        ``POST /{model}/upload/{field_name}``

        Requires ``add`` or ``change`` on the model, and ``field_name`` must be a
        file field (404 otherwise).

        The client-supplied name is never used as a path: only its sanitised
        basename is kept, a fresh name is generated so an existing file is never
        overwritten, and the target must resolve inside the storage root.

        Returns a JSON response with the stored name, relative to the storage root.
        """
        await self._check_any_permission(request, ("add", "change"))
        if field_name not in self._get_file_fields():
            raise HTTPException(status_code=404, detail=f"Unknown file field: {field_name!r}")
        if not self.storage:
            raise HTTPException(
                status_code=400,
                detail="File uploads not configured",
            )
        form_data = await request.form()
        upload = form_data.get("file")
        if not isinstance(upload, StarletteUpload) or not upload.filename:
            raise HTTPException(status_code=400, detail="No file provided")
        name = self._new_upload_name(upload.filename)
        if storage_root(self.storage) is not None:
            target = resolve_storage_path(self.storage, name)
            if target is None or target.exists():
                raise HTTPException(status_code=400, detail="Invalid file name")
        self.storage.write(upload.file, name)
        from starlette.responses import JSONResponse  # noqa: PLC0415

        return JSONResponse({"filename": name})

    def _new_upload_name(self, client_name: str) -> str:
        """Return a fresh, root-level storage name derived from ``client_name``.

        Directory parts are dropped, the basename is sanitised, and a random
        prefix makes the name unique so an upload never replaces a stored file.
        """
        basename = PurePosixPath(client_name.replace("\\", "/")).name
        get_name = getattr(self.storage, "get_name", None)
        safe = str(get_name(basename)) if callable(get_name) else basename
        safe = PurePosixPath(safe.replace("\\", "/")).name.lstrip(".")
        return f"{uuid.uuid4().hex}-{safe}" if safe else uuid.uuid4().hex

    @_request_scoped
    async def delete_file_view(
        self,
        request: Request,
        item_id: int,
        field_name: str,
    ) -> Response:
        """Delete a file from storage and clear the field on the record.

        ``DELETE /{model}/{item_id}/file/{field_name}``

        ``field_name`` must be a file field (404 otherwise), and the file is
        removed only when its path resolves inside the storage root.
        """
        await self._check_permission(request, "change")
        if field_name not in self._get_file_fields():
            raise HTTPException(status_code=404, detail=f"Unknown file field: {field_name!r}")
        item = await self._get_or_404(item_id)
        await self._check_object_permission(request, item, "change")
        path = self._stored_file_path(getattr(item, field_name, None))
        if path is not None:
            self._remove_files([str(path)])
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
        paths: list[str] = []
        for name in sorted(self._get_file_fields()):
            path = self._stored_file_path(getattr(item, name, None))
            if path is not None:
                paths.append(str(path))
        return paths

    def _stored_file_path(self, value: Any) -> Any:
        """Resolve a file column value to a path inside the storage root, or ``None``."""
        if not value or not self.storage:
            return None
        name = value.name if hasattr(value, "name") else str(value)
        return resolve_storage_path(self.storage, name)

    @staticmethod
    def _remove_files(paths: list[str]) -> None:
        """Remove regular files from disk, ignoring missing ones.

        Paths must come from :func:`resolve_storage_path` (storage-root contained).
        """
        for path in paths:
            if os.path.isfile(path):
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

    @_request_scoped
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
        await self._check_permission(request, "change")
        if not self._is_inline_editable(field):
            raise HTTPException(status_code=403, detail="Field not editable")

        item = await self._get_or_404(item_id)
        await self._check_object_permission(request, item, "change")

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

    @_request_scoped
    async def inline_save_view(self, request: Request, item_id: int, field: str):
        """Validates and persists a single field for ``item_id``."""
        await self._check_permission(request, "change")
        if not self._is_inline_editable(field):
            raise HTTPException(status_code=403, detail="Field not editable")

        item = await self._get_or_404(item_id)
        await self._check_object_permission(request, item, "change")

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

    @_request_scoped
    async def delete_action(self, request: Request, item_id: int):
        """Deletes an item."""
        await self._check_permission(request, "delete")
        item = await self._get_or_404(item_id)

        await self._check_object_permission(request, item, "delete")

        file_paths = self._collect_file_paths(item)
        await self.adapter.delete(pk=item_id)
        self._remove_files(file_paths)

        redirect_url = request.url_for(f"{self.model.__name__.lower()}-list")

        if "hx-request" in request.headers:
            return Response(status_code=200, headers={"HX-Redirect": str(redirect_url)})

        return RedirectResponse(url=redirect_url, status_code=303)

    @_request_scoped
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
        # Load under the queryset scope (404 for hidden rows) and re-check per object.
        item = await self._get_or_404(item_id)
        await self._check_object_permission(request, item, f"action_{action_name}")

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
            # Per-value tolerance: silently skip any id that isn't an integer.
            try:
                parsed.append(int(value))
            except (TypeError, ValueError):  # noqa: PERF203
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
                status: BulkRowStatus = (
                    "forbidden" if exc.status_code == HTTPStatus.FORBIDDEN else "failed"
                )
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

    @_request_scoped
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

    @_request_scoped
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
        payload = {key: value for key, value in form.items() if key != "ids"}
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
