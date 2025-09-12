"""This module will contain the dynamic routing engine for HyperAdmin."""

from fastapi import APIRouter
from fastapi.templating import Jinja2Templates


class HyperAdminRouter:
    def __init__(self, engine, templates: Jinja2Templates):
        self.router = APIRouter()
        self.engine = engine
        self.templates = templates

    def generate_routes(self):
        """Generates the routes for the registered models."""
        from hyperadmin.core.registry import site
        from hyperadmin.views.dynamic import DynamicModelView

        for model, admin_class in site._registry.items():
            admin_instance = admin_class(model)
            view = DynamicModelView(
                adapter=admin_instance.adapter_class(model, engine=self.engine),
                templates=self.templates,
                app_label=admin_class.app_label,
            )
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
