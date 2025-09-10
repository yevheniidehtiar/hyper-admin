from fastapi import APIRouter, FastAPI

from hyperadmin.core.model import ModelAdmin
from hyperadmin.core.registry import site
from hyperadmin.db import create_db_and_tables, engine
from hyperadmin.discover import discover_admin_modules


class Admin:
    """The main Admin class that holds the admin interface."""

    def __init__(
        self, app: FastAPI, discover_apps: list[str] | None = None, create_tables: bool = True
    ):
        self.app = app
        self.router = APIRouter()
        self.engine = engine

        if create_tables:

            @app.on_event("startup")
            async def startup_event():
                await create_db_and_tables()

        if discover_apps:
            discover_admin_modules(discover_apps)

        self._register_views()

    def _register_views(self):
        """Registers the views from the site registry."""
        for model_admin in site._registry.values():
            self.register(model_admin)

    def register(self, model_admin: ModelAdmin):
        """Registers a ModelAdmin instance with the admin interface."""
        adapter = model_admin.adapter_class(model=model_admin.model, engine=self.engine)
        view_instance = model_admin.view_class(adapter=adapter)
        self.router.include_router(view_instance.router, tags=[view_instance.model.__name__])

    def mount(self, path: str):
        """
        Mounts the admin interface on the FastAPI application.
        """
        self.app.include_router(self.router, prefix=path, tags=["HyperAdmin"])
