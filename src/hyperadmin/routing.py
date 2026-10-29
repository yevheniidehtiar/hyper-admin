"""This module will contain the dynamic routing engine for HyperAdmin."""

import logging
from datetime import timezone as dt_timezone
from datetime import tzinfo
from typing import TYPE_CHECKING, Any
from urllib.parse import quote

from fastapi import APIRouter, Request
from fastapi.routing import APIRoute
from fastapi.templating import Jinja2Templates
from sqlmodel import SQLModel
from starlette.convertors import CONVERTOR_TYPES, Convertor, register_url_convertor

from hyperadmin.core.actions import ActionDef, collect_actions
from hyperadmin.core.display import get_field_label
from hyperadmin.core.introspection import infer_list_display, infer_list_filter, infer_search_fields
from hyperadmin.core.options import AdminOptions
from hyperadmin.realtime.emitting import EventEmittingAdapter, notifications_enabled
from hyperadmin.views.dynamic import DynamicModelView
from hyperadmin.views.route import make_admin_route_class
from hyperadmin.views.template_filters import register_template_filters

if TYPE_CHECKING:
    from hyperadmin.core.adapters import SessionFactory
    from hyperadmin.realtime.config import RealtimeSettings
    from hyperadmin.realtime.emitting import RealtimeEmitter

logger = logging.getLogger(__name__)


class HyperAdminPkConvertor(Convertor[str]):
    """Starlette path convertor for natural (non-int, non-UUID) primary keys.

    Registered once, at import time, as ``hyperadmin_pk`` (BYOA SDD A.5). Its
    regex is permissive — like Starlette's built-in ``str`` convertor — but
    unlike that convertor, ``to_string`` percent-encodes the value, so a key
    containing reserved URL characters (a space, a ``?``, ...) still round-trips
    through ``url_for``.
    """

    regex = "[^/]+"

    def convert(self, value: str) -> str:
        """Return the path segment unchanged; it arrives already percent-decoded."""
        return value

    def to_string(self, value: Any) -> str:
        """Percent-encode ``value`` for use in a URL path segment.

        ``to_string`` runs once per row inside ``components/table.html`` (one
        ``url_for`` call per action link). An exception raised here aborts the
        *entire* list page render for *every* row, not just the row whose key
        is malformed — so a single bad natural key stored earlier (``""``, a
        value containing ``"/"``, ...) would turn into a persistent 500 on
        every future visit to that model's list page, for every admin user.
        This was reported and verified against this behaviour when it used to
        raise on an empty string or a ``"/"`` (BYOA SDD A.5 Decision Log).

        So instead of rejecting those values, this always stringifies and
        percent-encodes: ``/`` becomes ``%2F`` because it is not in ``safe``,
        and ``""`` stays ``""``. Either produces a link that is a dead 404 on
        its own row — never one that crashes the page. ``None`` is handled
        the same way (stringifying to the literal ``"None"``), rather than
        raising, for the same reason: a view or template passing a ``None``
        key is exactly the kind of single-row mistake this must not let take
        the whole list page down with it.
        """
        return quote(str(value), safe="-._~!$&'()*+,;=:@")


if "hyperadmin_pk" not in CONVERTOR_TYPES:
    register_url_convertor("hyperadmin_pk", HyperAdminPkConvertor())


def _extract_column_names(raw: list[Any] | None, model: type | None = None) -> list[str] | None:
    """Extract field name strings from a list of SQLAlchemy column attributes or properties."""
    if not raw:
        return None
    names: list[str] = []
    for col in raw:
        if hasattr(col, "key"):
            names.append(col.key)
        elif isinstance(col, property) and model:
            # Resolve @property descriptors by scanning the model's MRO
            resolved = False
            for cls in model.__mro__:
                for attr_name, attr_val in vars(cls).items():
                    if attr_val is col:
                        names.append(attr_name)
                        resolved = True
                        break
                if resolved:
                    break
            if not resolved:
                names.append(str(col))
        elif isinstance(col, str):
            names.append(col)
        else:
            names.append(str(col))
    return names


def create_admin_router(  # noqa: PLR0912, PLR0913, PLR0915, PLR0917
    model: type[SQLModel],
    admin_class: Any,
    admin_instance: Any,
    options: AdminOptions,
    engine: Any,
    templates: Jinja2Templates,
    form_include: list[str] | None = None,
    form_create_exclude: list[str] | None = None,
    column_list: list[str] | None = None,
    permission_checker: Any = None,
    actions: list[ActionDef] | None = None,
    search_fields: list[str] | None = None,
    field_labels: dict[str, str] | None = None,
    storage: Any = None,
    admin_lookup: Any = None,
    route_class: type[APIRoute] = APIRoute,
    session_factory: "SessionFactory | None" = None,
    debug: bool = False,
    realtime_emitter: "RealtimeEmitter | None" = None,
    realtime_settings: "RealtimeSettings | None" = None,
) -> APIRouter:
    """Creates an APIRouter for a given model with the specified admin options."""
    router = APIRouter(route_class=route_class)
    # session_factory is forwarded only when set, so a third-party adapter_class
    # that still uses the pre-0.5.8, engine-only __init__(self, model, engine)
    # signature keeps working under an engine-only Admin (it never sees an
    # unexpected session_factory keyword).
    adapter_kwargs: dict[str, Any] = {"engine": engine}
    if session_factory is not None:
        adapter_kwargs["session_factory"] = session_factory
    adapter: Any = admin_instance.adapter_class(model, **adapter_kwargs)
    if realtime_emitter is None:
        if options.realtime_notifications is True:
            logger.info(
                "%s sets realtime_notifications=True but realtime is disabled; ignoring",
                model.__name__,
            )
    elif realtime_settings is not None and notifications_enabled(options, realtime_settings):
        adapter = EventEmittingAdapter(adapter, realtime_emitter)
    pk = adapter.pk

    # Composite keys (BYOA SDD A.5 point 4): item-scoped routes are never
    # registered, because the adapter's get/update/delete raise
    # NotImplementedError for them (A.3). Forcing these options off — rather
    # than only skipping route registration below — also stops
    # `components/table.html` from calling `url_for` on a route that was
    # never registered, which would otherwise fail the list page with a 500
    # (NoMatchFound).
    if pk.composite:
        logger.warning("%s has a composite primary key; registering list-only", model.__name__)
        options = options.model_copy(
            update={
                "can_detail": False,
                "can_edit": False,
                "can_delete": False,
                "can_create": False,
                "list_editable": [],
                "inlines": [],
            }
        )
        actions = []
        storage = None

    view = DynamicModelView(
        adapter=adapter,
        options=options,
        templates=templates,
        app_label=admin_class.app_label,
        form_include=form_include,
        form_create_exclude=form_create_exclude,
        column_list=column_list,
        permission_checker=permission_checker,
        actions=actions,
        admin_instance=admin_instance,
        search_fields=search_fields,
        field_labels=field_labels,
        storage=storage,
        admin_lookup=admin_lookup,
        debug=debug,
    )
    model_name = model.__name__.lower()

    prefix = f"/{model_name}"
    # Int keys keep `{item_id:int}` byte-for-byte; UUID keys use Starlette's
    # built-in `uuid` convertor, so a malformed UUID never matches the route
    # and 404s before any view runs; every other key kind uses the
    # `hyperadmin_pk` convertor registered above.
    item_segment = f"{{item_id:{pk.path_convertor}}}"

    # --- Literal (fixed-segment) routes, registered first --------------
    #
    # Starlette uses the first full match, so for a non-int, non-UUID key
    # (whose convertor matches any non-slash segment) these fixed words must
    # be registered *before* the `/{item_id}` routes below, or a request for
    # e.g. `/{model}/create-popup` would be swallowed by `/{model}/{item_id}`
    # with `item_id="create-popup"` (BYOA SDD A.5 point 3).

    if options.can_list:
        router.add_api_route(
            prefix,
            view.list_view,
            methods=["GET"],
            name=f"{model_name}-list",
        )

    if options.can_create:
        router.add_api_route(
            prefix,
            view.create_view,
            methods=["POST"],
            name=f"{model_name}-create",
        )
        router.add_api_route(
            f"{prefix}/create",
            view.create_form_view,
            methods=["GET"],
            name=f"{model_name}-create-form",
        )
        router.add_api_route(
            f"{prefix}/create-popup",
            view.create_popup_view,
            methods=["GET", "POST"],
            name=f"{model_name}-create-popup",
        )

    router.add_api_route(
        f"{prefix}/choices/{{field_name}}",
        view.choices_view,
        methods=["GET"],
        name=f"{model_name}-choices",
    )

    if options.saved_views_enabled and options.can_list:
        # Per-user saved views (docs/specs/filter-library.md): list, save and
        # delete the current user's named filter sets for this model.
        router.add_api_route(
            f"{prefix}/saved-views",
            view.saved_views_list,
            methods=["GET"],
            name=f"{model_name}-saved-views",
        )
        router.add_api_route(
            f"{prefix}/saved-views",
            view.saved_view_create,
            methods=["POST"],
            name=f"{model_name}-saved-view-create",
        )
        router.add_api_route(
            f"{prefix}/saved-views/{{view_id:int}}",
            view.saved_view_delete,
            methods=["DELETE"],
            name=f"{model_name}-saved-view-delete",
        )

    if options.inlines:
        router.add_api_route(
            f"{prefix}/inline/{{inline_prefix}}/add-row",
            view.inline_add_row_view,
            methods=["GET"],
            name=f"{model_name}-inline-add-row",
        )

    if actions and any(a.bulk for a in actions):
        router.add_api_route(
            f"{prefix}/actions/{{action_name}}/bulk",
            view.run_bulk_action,
            methods=["POST"],
            name=f"{model_name}-bulk-action",
        )
        router.add_api_route(
            f"{prefix}/actions/{{action_name}}/bulk/confirm",
            view.confirm_bulk_action,
            methods=["POST"],
            name=f"{model_name}-bulk-action-confirm",
        )

    if storage:
        router.add_api_route(
            f"{prefix}/upload/{{field_name}}",
            view.upload_file_view,
            methods=["POST"],
            name=f"{model_name}-upload",
        )

    # --- Item-scoped (`/{item_id}`) routes, registered last -------------

    if options.can_detail:
        router.add_api_route(
            f"{prefix}/{item_segment}",
            view.detail_view,
            methods=["GET"],
            name=f"{model_name}-detail",
        )
        if view.panels:
            # Detail-page panels (docs/specs/detail-panels.md): the lazy-loaded
            # fragment and, for streaming handlers, the bytes behind its frame.
            router.add_api_route(
                f"{prefix}/{item_segment}/panels/{{slug}}",
                view.render_panel_view,
                methods=["GET"],
                name=f"{model_name}-panel",
            )
            router.add_api_route(
                f"{prefix}/{item_segment}/panels/{{slug}}/stream",
                view.stream_panel_view,
                methods=["GET"],
                name=f"{model_name}-panel-stream",
            )

    if options.can_edit:
        router.add_api_route(
            f"{prefix}/{item_segment}",
            view.update_view,
            methods=["PUT"],
            name=f"{model_name}-update",
        )
        router.add_api_route(
            f"{prefix}/{item_segment}/edit",
            view.update_form_view,
            methods=["GET"],
            name=f"{model_name}-update-form",
        )

        if options.list_editable:
            router.add_api_route(
                f"{prefix}/{item_segment}/inline/{{field:str}}",
                view.inline_edit_form_view,
                methods=["GET"],
                name=f"{model_name}-inline-edit-form",
            )
            router.add_api_route(
                f"{prefix}/{item_segment}/inline/{{field:str}}",
                view.inline_save_view,
                methods=["POST"],
                name=f"{model_name}-inline-save",
            )

    if options.can_delete:
        router.add_api_route(
            f"{prefix}/{item_segment}",
            view.delete_action,
            methods=["DELETE"],
            name=f"{model_name}-delete",
        )

    if actions:
        router.add_api_route(
            f"{prefix}/{item_segment}/action/{{action_name}}",
            view.run_action,
            methods=["POST"],
            name=f"{model_name}-action",
        )

    if storage:
        # Per-record file download behind view, queryset and object checks
        # (BYOA SDD C.5); replaces the public `/uploads` static mount.
        router.add_api_route(
            f"{prefix}/{item_segment}/file/{{field_name}}",
            view.download_file_view,
            methods=["GET"],
            name=f"{model_name}-file",
        )
        router.add_api_route(
            f"{prefix}/{item_segment}/file/{{field_name}}",
            view.delete_file_view,
            methods=["DELETE"],
            name=f"{model_name}-delete-file",
        )

    return router


def _resolve_smart_defaults(
    model: type[SQLModel],
    options: AdminOptions,
    column_list: list[str] | None,
) -> tuple[list[str] | None, list[str] | None, AdminOptions, dict[str, str]]:
    """Resolve smart defaults for display, search, filter, and labels.

    Returns (column_list, search_fields, options, field_labels).
    """
    resolved_columns = column_list
    if not resolved_columns:
        if options.list_display is not None:
            resolved_columns = options.list_display or None
        else:
            try:
                resolved_columns = infer_list_display(model, options.sensitive_fields)
            except Exception:
                resolved_columns = None

    resolved_search: list[str] | None = None
    if options.search_fields is not None:
        resolved_search = options.search_fields
    else:
        try:
            resolved_search = infer_search_fields(model, options.sensitive_fields)
        except Exception:
            resolved_search = None

    if options.list_filter is None:
        try:
            options = options.model_copy(
                update={"list_filter": infer_list_filter(model, options.sensitive_fields)}
            )
        except Exception:
            options = options.model_copy(update={"list_filter": []})

    field_labels: dict[str, str] = {}
    if resolved_columns:
        field_labels = {f: get_field_label(f) for f in resolved_columns if f != "__str__"}

    return resolved_columns, resolved_search, options, field_labels


class HyperAdminRouter:
    """Generates and owns all FastAPI routers for HyperAdmin.

    Called internally by ``Admin.mount()``. Iterates ``SiteRegistry`` and
    calls ``create_admin_router`` for each registered model.

    Args:
        engine: The async SQLAlchemy engine passed to every adapter.
        templates: The shared ``Jinja2Templates`` instance used across all views.
        timezone: The admin's configured display timezone (``settings.tzinfo``),
            registered as the ``ha_display``/``ha_datetime_input`` fallback
            (BYOA SDD A.9). Defaults to UTC.
        datetime_format: The admin's configured ``settings.datetime_format``,
            registered as the ``ha_display`` format string (BYOA SDD A.7).
        session_factory: A host-provided session factory forwarded to every
            adapter alongside (or instead of) ``engine``.
        debug: The admin's ``settings.debug``. List views re-raise database
            errors instead of rendering the list-error banner (BYOA SDD D.2).
        route_class: The admin's ``HyperAdminRoute`` (``views/route.py``), set
            on every generated router. Defaults to one bound to ``templates``.

    The timezone and datetime format reach the view layer by living on the
    shared Jinja environment (as the ``hyperadmin_timezone`` /
    ``hyperadmin_datetime_format`` globals ``register_template_filters``
    sets), not as a constructor argument the view classes read — every view
    renders through this one environment, so there is nothing else to wire.
    """

    def __init__(  # noqa: PLR0913
        self,
        engine: Any,
        templates: Jinja2Templates,
        permission_checker: Any = None,
        storage: Any = None,
        timezone: tzinfo | None = None,
        datetime_format: str = "%Y-%m-%d %H:%M:%S",
        session_factory: "SessionFactory | None" = None,
        *,
        debug: bool = False,
        route_class: type[APIRoute] | None = None,
        realtime_emitter: "RealtimeEmitter | None" = None,
        realtime_settings: "RealtimeSettings | None" = None,
    ):
        self.engine = engine
        self.debug = debug
        # The admin's own HyperAdminRoute (auth bridge, CSRF), or a default one
        # bound to these templates when the router is used on its own.
        self.route_class = route_class or make_admin_route_class(templates)
        self.permission_checker = permission_checker
        self.storage = storage
        self.session_factory = session_factory
        self.realtime_emitter = realtime_emitter
        self.realtime_settings = realtime_settings
        self.notification_models: set[str] = set()
        # Enable global whitespace trimming
        templates.env.trim_blocks = True
        templates.env.lstrip_blocks = True
        register_template_filters(
            templates.env,
            default_timezone=timezone or dt_timezone.utc,
            datetime_format=datetime_format,
        )
        self.templates = templates
        self.routers: list[APIRouter] = []

    def generate_routes(self) -> None:
        """Generates the routes for the registered models."""
        from hyperadmin.core.registry import site

        self.routers = []
        # model -> ModelAdmin instance, shared by every view so cross-model
        # lookups (choices target get_queryset) use the registered admin.
        admin_instances: dict[Any, Any] = {}
        nav_items: list[dict[str, str]] = []
        route_class = self.route_class

        # Add the main admin dashboard route
        dashboard_router = APIRouter(route_class=route_class)
        dashboard_router.add_api_route(
            "/",
            self.get_admin_dashboard_view(),
            methods=["GET"],
            name="admin-dashboard",
        )
        self.routers.append(dashboard_router)

        for model, admin_class in site._registry.items():
            admin_instance = admin_class(model)
            admin_instances[model] = admin_instance
            # Prioritize options set on admin_class, then fall back to defaults
            options = getattr(admin_class, "options", None) or AdminOptions()
            # If admin_class has list_filter set directly (legacy or class-style)
            if hasattr(admin_class, "list_filter") and options.list_filter is None:
                class_filter = getattr(admin_class, "list_filter", None)
                if class_filter:
                    options.list_filter = class_filter

            form_include = _extract_column_names(getattr(admin_class, "form_columns", None), model)
            form_create_exclude = _extract_column_names(
                getattr(admin_class, "form_create_exclude", None), model
            )
            column_list = _extract_column_names(
                getattr(admin_class, "column_list", None) or getattr(admin_class, "list", None),
                model,
            )

            resolved_column_list, resolved_search_fields, options, field_labels = (
                _resolve_smart_defaults(model, options, column_list)
            )

            actions = collect_actions(admin_class)

            router = create_admin_router(
                model=model,
                admin_class=admin_class,
                admin_instance=admin_instance,
                options=options,
                engine=self.engine,
                templates=self.templates,
                form_include=form_include,
                form_create_exclude=form_create_exclude,
                column_list=resolved_column_list,
                permission_checker=self.permission_checker,
                actions=actions,
                search_fields=resolved_search_fields,
                field_labels=field_labels,
                storage=self.storage,
                admin_lookup=admin_instances.get,
                route_class=route_class,
                session_factory=self.session_factory,
                debug=self.debug,
                realtime_emitter=self.realtime_emitter,
                realtime_settings=self.realtime_settings,
            )
            self.routers.append(router)
            if (
                self.realtime_emitter is not None
                and self.realtime_settings is not None
                and notifications_enabled(options, self.realtime_settings)
            ):
                self.notification_models.add(model.__name__.lower())

            model_name = model.__name__
            # Resolve nav label: prefer verbose_name_plural / verbose_name
            # (which may be LazyProxy instances) over the legacy name_plural /
            # name attributes.  Do NOT call str() here — lazy strings must
            # remain lazy so they render in the request locale at template time.
            legacy_name_plural = getattr(admin_class, "name_plural", None)
            if legacy_name_plural:
                nav_name = legacy_name_plural
            elif hasattr(admin_class, "get_verbose_name_plural"):
                nav_name = admin_class.get_verbose_name_plural(model)
            else:
                nav_name = getattr(admin_class, "name", model_name) + "s"
            nav_items.append(
                {
                    "name": nav_name,
                    "url": f"/{model_name.lower()}",
                    "icon": getattr(admin_class, "icon", ""),
                    # The sidebar hides the entry from users without this permission.
                    "permission": f"view_{model_name.lower()}",
                }
            )

        self.templates.env.globals["nav_items"] = nav_items

    def get_admin_dashboard_view(self):
        from hyperadmin.views.dynamic import admin_dashboard

        async def admin_dashboard_view(request: Request):
            return await admin_dashboard(request, self.templates)

        return admin_dashboard_view

    def get_routers(self) -> list[APIRouter]:
        """Returns the list of generated APIRouters."""
        return self.routers
