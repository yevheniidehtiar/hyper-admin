"""This module will contain the dynamic routing engine for HyperAdmin."""

from typing import Any

from fastapi import APIRouter, Request
from fastapi.templating import Jinja2Templates
from sqlmodel import SQLModel

from hyperadmin.core.actions import ActionDef, collect_actions
from hyperadmin.core.display import get_field_label
from hyperadmin.core.introspection import infer_list_display, infer_list_filter, infer_search_fields
from hyperadmin.core.options import AdminOptions
from hyperadmin.views.dynamic import DynamicModelView


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


def create_admin_router(  # noqa: PLR0913
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
) -> APIRouter:
    """Creates an APIRouter for a given model with the specified admin options."""
    router = APIRouter()
    view = DynamicModelView(
        adapter=admin_instance.adapter_class(model, engine=engine),
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
    )
    model_name = model.__name__.lower()

    prefix = f"/{model_name}"

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

    if options.can_detail:
        router.add_api_route(
            f"{prefix}/{{item_id:int}}",
            view.detail_view,
            methods=["GET"],
            name=f"{model_name}-detail",
        )

    if options.can_edit:
        router.add_api_route(
            f"{prefix}/{{item_id:int}}",
            view.update_view,
            methods=["PUT"],
            name=f"{model_name}-update",
        )
        router.add_api_route(
            f"{prefix}/{{item_id:int}}/edit",
            view.update_form_view,
            methods=["GET"],
            name=f"{model_name}-update-form",
        )

    if options.can_delete:
        router.add_api_route(
            f"{prefix}/{{item_id:int}}",
            view.delete_action,
            methods=["DELETE"],
            name=f"{model_name}-delete",
        )

    router.add_api_route(
        f"{prefix}/choices/{{field_name}}",
        view.choices_view,
        methods=["GET"],
        name=f"{model_name}-choices",
    )

    if options.inlines:
        router.add_api_route(
            f"{prefix}/inline/{{inline_prefix}}/add-row",
            view.inline_add_row_view,
            methods=["GET"],
            name=f"{model_name}-inline-add-row",
        )

    if actions:
        router.add_api_route(
            f"{prefix}/{{item_id:int}}/action/{{action_name}}",
            view.run_action,
            methods=["POST"],
            name=f"{model_name}-action",
        )

    if storage:
        router.add_api_route(
            f"{prefix}/upload/{{field_name}}",
            view.upload_file_view,
            methods=["POST"],
            name=f"{model_name}-upload",
        )
        router.add_api_route(
            f"{prefix}/{{item_id:int}}/file/{{field_name}}",
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
                resolved_columns = infer_list_display(model)
            except Exception:
                resolved_columns = None

    resolved_search: list[str] | None = None
    if options.search_fields is not None:
        resolved_search = options.search_fields
    else:
        try:
            resolved_search = infer_search_fields(model)
        except Exception:
            resolved_search = None

    if options.list_filter is None:
        try:
            options = options.model_copy(update={"list_filter": infer_list_filter(model)})
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
    """

    def __init__(
        self,
        engine: Any,
        templates: Jinja2Templates,
        permission_checker: Any = None,
        storage: Any = None,
    ):
        self.engine = engine
        self.permission_checker = permission_checker
        self.storage = storage
        # Enable global whitespace trimming
        templates.env.trim_blocks = True
        templates.env.lstrip_blocks = True
        self.templates = templates
        self.routers: list[APIRouter] = []

    def generate_routes(self) -> None:
        """Generates the routes for the registered models."""
        from hyperadmin.core.registry import site

        self.routers = []
        nav_items: list[dict[str, str]] = []

        # Add the main admin dashboard route
        dashboard_router = APIRouter()
        dashboard_router.add_api_route(
            "/",
            self.get_admin_dashboard_view(),
            methods=["GET"],
            name="admin-dashboard",
        )
        self.routers.append(dashboard_router)

        for model, admin_class in site._registry.items():
            admin_instance = admin_class(model)
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
            )
            self.routers.append(router)

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
