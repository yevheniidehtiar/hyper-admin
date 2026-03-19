"""This module will contain the dynamic routing engine for HyperAdmin."""

from typing import Any

from fastapi import APIRouter, Request
from fastapi.templating import Jinja2Templates
from sqlmodel import SQLModel

from hyperadmin.core.options import AdminOptions
from hyperadmin.views.dynamic import DynamicModelView


def create_admin_router(
    model: type[SQLModel],
    admin_class: Any,
    admin_instance: Any,
    options: AdminOptions,
    engine: Any,
    templates: Jinja2Templates,
) -> APIRouter:
    """
    Creates an APIRouter for a given model with the specified admin options.

    Args:
        model: The SQLModel class.
        admin_class: The admin class for the model.
        admin_instance: The admin instance for the model.
        options: The AdminOptions for the model.
        engine: The database engine.
        templates: The Jinja2Templates instance.

    Returns:
        An APIRouter instance with the generated routes.
    """
    router = APIRouter()
    view = DynamicModelView(
        adapter=admin_instance.adapter_class(model, engine=engine),
        options=options,
        templates=templates,
        app_label=admin_class.app_label,
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

    return router


class HyperAdminRouter:
    """Generates and owns all FastAPI routers for HyperAdmin.

    Called internally by ``Admin.mount()``. Iterates ``SiteRegistry`` and
    calls ``create_admin_router`` for each registered model.

    Args:
        engine: The async SQLAlchemy engine passed to every adapter.
        templates: The shared ``Jinja2Templates`` instance used across all views.
    """

    def __init__(self, engine: Any, templates: Jinja2Templates):
        self.engine = engine
        # Enable global whitespace trimming
        templates.env.trim_blocks = True
        templates.env.lstrip_blocks = True
        self.templates = templates
        self.routers: list[APIRouter] = []

    def generate_routes(self) -> None:
        """Generates the routes for the registered models."""
        from hyperadmin.core.registry import site

        self.routers = []

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
            options = getattr(admin_instance, "options", AdminOptions())
            router = create_admin_router(
                model=model,
                admin_class=admin_class,
                admin_instance=admin_instance,
                options=options,
                engine=self.engine,
                templates=self.templates,
            )
            self.routers.append(router)

    def get_admin_dashboard_view(self):
        from hyperadmin.views.dynamic import admin_dashboard

        async def admin_dashboard_view(request: Request):
            return await admin_dashboard(request, self.templates)

        return admin_dashboard_view

    def get_routers(self) -> list[APIRouter]:
        """Returns the list of generated APIRouters."""
        return self.routers
