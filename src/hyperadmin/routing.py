"""This module will contain the dynamic routing engine for HyperAdmin."""

from typing import Any

from fastapi import APIRouter
from sqlmodel import SQLModel

from hyperadmin.core.options import AdminOptions
from hyperadmin.views.dynamic import DynamicModelView


def create_admin_router(
    model: type[SQLModel],
    admin_instance: Any,
    options: AdminOptions,
    engine: Any,
) -> APIRouter:
    """
    Creates an APIRouter for a given model with the specified admin options.

    Args:
        model: The SQLModel class.
        admin_instance: The admin instance for the model.
        options: The AdminOptions for the model.
        engine: The database engine.

    Returns:
        An APIRouter instance with the generated routes.
    """
    router = APIRouter()
    view = DynamicModelView(
        adapter=admin_instance.adapter_class(model, engine=engine),
        options=options,
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
    def __init__(self, engine: Any):
        self.engine = engine
        self.routers: list[APIRouter] = []

    def generate_routes(self) -> None:
        """Generates the routes for the registered models."""
        from hyperadmin.core.registry import site

        self.routers = []
        for model, admin_instance in site._registry.items():
            options = getattr(admin_instance, "options", AdminOptions())
            router = create_admin_router(
                model=model,
                admin_instance=admin_instance,
                options=options,
                engine=self.engine,
            )
            self.routers.append(router)

    def get_routers(self) -> list[APIRouter]:
        """Returns the list of generated APIRouters."""
        return self.routers
