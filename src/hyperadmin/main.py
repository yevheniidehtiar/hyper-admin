from fastapi import APIRouter, FastAPI

from hyperadmin.core.registry import site
from hyperadmin.db import create_db_and_tables
from hyperadmin.discover import discover_admin_modules
from hyperadmin.views import ModelView


class Admin:
    """The main Admin class that holds the admin interface."""

    def __init__(self, app: FastAPI, discover_apps: list[str] | None = None):
        self.app = app
        self.router = APIRouter()
        create_db_and_tables()
        if discover_apps:
            discover_admin_modules(discover_apps)

        self._register_views()

    def _register_views(self):
        """Registers the views from the site registry."""
        for model, admin_class in site._registry.items():
            if admin_class:
                self.register(admin_class)

    def register(self, model_view_class: type[ModelView]):
        """Registers a ModelView class with the admin interface."""
        view_instance = model_view_class()
        self.router.include_router(view_instance.router, tags=[view_instance.model.__name__])

    def mount(self, path: str):
        """
        Mounts the admin interface on the FastAPI application.
        """
        self.app.include_router(self.router, prefix=path, tags=["HyperAdmin"])
