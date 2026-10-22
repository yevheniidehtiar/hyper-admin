"""Shared state plus permission, primary-key and relation helpers."""

import functools
import logging
import os
from collections.abc import Callable, Generator
from contextlib import contextmanager
from types import SimpleNamespace
from typing import TYPE_CHECKING, Any, cast

from fastapi import HTTPException, Request
from fastapi.templating import Jinja2Templates

if TYPE_CHECKING:
    from jinja2 import FileSystemLoader


from hyperadmin.adapters import SQLAlchemyAdapter, SQLModelAdapter
from hyperadmin.core.actions import ActionDef
from hyperadmin.core.adapters import (
    queryset_scope,
)
from hyperadmin.core.choices import SelectFieldMeta
from hyperadmin.core.discovery import build_filter_metadata
from hyperadmin.core.fields import classify_field
from hyperadmin.core.inlines import InlineModelSpec
from hyperadmin.core.options import AdminOptions
from hyperadmin.core.panels import PanelDef, resolve_panels
from hyperadmin.core.primary_key import InvalidPrimaryKey, PrimaryKeyInfo
from hyperadmin.core.registry import site
from hyperadmin.core.sensitive import (
    is_sensitive,
    is_text_annotation,
    sensitive_field_names,
    sensitive_overrides_scope,
)
from hyperadmin.views.forms import (
    InlineFormset,
)
from hyperadmin.views.template_filters import TIMEZONE_GLOBAL, request_tz
from hyperadmin.views.urls import admin_url_for

logger = logging.getLogger(__name__)


class DynamicModelViewBase:
    """Shared state plus permission, primary-key and relation helpers."""

    def __init__(  # noqa: PLR0913, PLR0917
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
        debug: bool = False,
    ):
        self.adapter = adapter
        # ``settings.debug``: list_view re-raises database errors instead of
        # rendering the list-error banner (BYOA SDD D.2).
        self.debug = debug
        self.model = adapter.model
        self.pk: PrimaryKeyInfo = adapter.pk
        self.options = options
        self.templates = templates
        self.app_label = app_label
        self.form_include = form_include
        self.form_create_exclude = form_create_exclude or []
        self.column_list = column_list or [self.pk.attr, "__str__"]
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
        # Detail-page panels (docs/specs/detail-panels.md): ``options.panels``
        # merged with the admin's ``@panel`` methods, slugs checked for
        # collisions and permission codenames filled in — so a duplicate slug
        # fails here, at registration, not on the first request. Without an
        # admin instance (a view built directly) only ``options.panels`` apply.
        panel_source = (
            admin_instance if admin_instance is not None else SimpleNamespace(options=options)
        )
        self.panels: list[PanelDef] = resolve_panels(panel_source, self.model)
        self._panel_map: dict[str, PanelDef] = {p.slug: p for p in self.panels}

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
        with (
            queryset_scope(request, self._queryset_filter_for),
            sensitive_overrides_scope(self._sensitive_overrides_for),
        ):
            yield

    def _sensitive_overrides_for(self, model: Any) -> Any:
        """Return ``AdminOptions.sensitive_fields`` of the admin registered for ``model``."""
        options = self.options if model is self.model else None
        if options is None:
            options = getattr(self._admin_for_model(model), "options", None)
        return getattr(options, "sensitive_fields", None) or None

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

    def _resolve_pk(self, item_id: Any) -> Any:
        """Parse a raw ``item_id`` into this model's typed key, or raise 404."""
        try:
            return self.pk.parse(item_id)
        except InvalidPrimaryKey as exc:
            raise HTTPException(status_code=404, detail="Item not found") from exc

    def _form_pk_kwargs(self, *, create: bool) -> dict[str, Any]:
        """``PydanticForm`` pk options: a natural (non-generated) key is an input on create only."""
        return {"pk_attr": self.pk.attr, "pk_editable": create and not self.pk.generated}

    @staticmethod
    def _stored_values(item: Any) -> dict[str, Any]:
        """The stored field values of ``item`` (``model_dump()``, else ``__dict__``)."""
        initial_func = getattr(item, "model_dump", None)
        return cast(
            "dict[str, Any]",
            initial_func() if callable(initial_func) else dict(getattr(item, "__dict__", {})),
        )

    def _form_datetime_kwargs(self, request: Request) -> dict[str, Any]:
        """``PydanticForm`` datetime options: the request's display timezone and column kinds."""
        default_tz = self.templates.env.globals.get(TIMEZONE_GLOBAL)
        return {
            "timezone": request_tz(request, default_tz),
            "datetime_kind": self.adapter.datetime_kind,
        }

    def _inline_formset(self, spec: InlineModelSpec, **kwargs: Any) -> InlineFormset:
        """Build a formset that parses submitted child keys with the inline model's own codec."""
        return InlineFormset(spec=spec, pk=self.adapter.for_model(spec.model).pk, **kwargs)

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
            if isinstance(f, str)
            and f in allowed
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

    @functools.cached_property
    def _opaque_sensitive_fields(self) -> list[str]:
        """Sensitive fields that cannot be write-only inputs (booleans, enums, numbers...).

        A blank text input can mean "keep the stored value"; a checkbox or a
        select cannot, so these fields are left out of the edit form entirely
        and always keep their stored value on update.
        """
        model_fields = self.model.model_fields
        return sorted(
            name
            for name in self._sensitive_fields
            if name in model_fields and not is_text_annotation(model_fields[name].annotation)
        )

    def _keep_stored_secrets(self, data: dict[str, Any], existing: Any) -> None:
        """Write-only semantics for sensitive fields on update.

        An empty text input keeps the stored value. A non-text sensitive field
        is not on the edit form, so its stored value is always kept.
        """
        opaque = set(self._opaque_sensitive_fields)
        for name in self._sensitive_fields:
            if name not in self.model.model_fields:
                continue
            if name in opaque or data.get(name) in (None, ""):
                data[name] = getattr(existing, name, None)

    def _filterable_fields(self) -> set[str]:
        """Fields a URL ``filter_<name>`` may target: ``list_filter`` strings, never sensitive.

        Explicit :class:`FilterDef` entries read their own querystring keys
        (see :meth:`_explicit_filters`) and are not part of this set.
        """
        model_fields = getattr(self.model, "model_fields", {})
        return {
            f
            for f in (getattr(self.options, "list_filter", None) or [])
            if isinstance(f, str) and f in model_fields and f not in self._sensitive_fields
        }

    def _sortable_fields(self) -> set[str]:
        """Fields ``sort_by`` may target: displayed, real, non-sensitive model fields."""
        model_fields = getattr(self.model, "model_fields", {})
        return {
            f for f in self.column_list if f in model_fields and f not in self._sensitive_fields
        }

    def _default_sort_field(self) -> str:
        """The first non-sensitive model field (the pk attribute when there is none)."""
        model_fields = getattr(self.model, "model_fields", {})
        return next((f for f in model_fields if f not in self._sensitive_fields), self.pk.attr)

    def _get_file_fields(self) -> set[str]:
        """Return the set of field names backed by FileType/ImageType columns."""
        from hyperadmin.core.uploads import FileFieldMeta  # noqa: PLC0415

        result: set[str] = set()
        for name, fi in self.model.model_fields.items():
            meta = classify_field(fi, self.model)
            if isinstance(meta, FileFieldMeta):
                result.add(name)
        return result

    def _list_path(self, request: Request) -> str:
        """The list URL's path for this request (``root_path`` and mount prefix included)."""
        return admin_url_for(request, f"{self._model_name_lower}-list").path
