"""This module will contain the dynamic routing engine for HyperAdmin."""

from fastapi import APIRouter


class HyperAdminRouter:
    def __init__(self, engine):
        self.router = APIRouter()
        self.engine = engine

    def generate_routes(self):
        """Generates the routes for the registered models."""
        from hyperadmin.core.registry import site
        from hyperadmin.views.dynamic import DynamicModelView

        for model, admin_instance in site._registry.items():
            view = DynamicModelView(adapter=admin_instance.adapter_class(model, engine=self.engine))
            model_name = model.__name__.lower()
            self.router.add_api_route(
                f"/{model_name}",
                view.list_view,
                methods=["GET"],
                name=f"{model_name}-list",
            )
            self.router.add_api_route(
                f"/{model_name}",
                view.create_view,
                methods=["POST"],
                name=f"{model_name}-create",
            )
            self.router.add_api_route(
                f"/{model_name}/create",
                view.create_form_view,
                methods=["GET"],
                name=f"{model_name}-create-form",
            )
            self.router.add_api_route(
                f"/{model_name}/{{item_id}}",
                view.detail_view,
                methods=["GET"],
                name=f"{model_name}-detail",
            )
            self.router.add_api_route(
                f"/{model_name}/{{item_id}}",
                view.update_view,
                methods=["PUT"],
                name=f"{model_name}-update",
            )
            self.router.add_api_route(
                f"/{model_name}/{{item_id}}/edit",
                view.update_form_view,
                methods=["GET"],
                name=f"{model_name}-update-form",
            )
            self.router.add_api_route(
                f"/{model_name}/{{item_id}}",
                view.delete_action,
                methods=["DELETE"],
                name=f"{model_name}-delete",
            )
