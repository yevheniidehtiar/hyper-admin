import os
from fastapi import APIRouter, FastAPI
from fastapi.templating import Jinja2Templates

from hyperadmin.db import create_db_and_tables, engine
from hyperadmin.discover import discover_admin_modules

template_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "templates")


class Admin:
    """The main Admin class that holds the admin interface."""

    def __init__(
        self,
        app: FastAPI,
        discover_apps: list[str] | None = None,
        create_tables: bool = True,
        template_dirs: list[str] | None = None,
    ):
        self.app = app
        self.router = APIRouter()
        self.engine = engine
        self.template_dirs = template_dirs or []
        self.templates = Jinja2Templates(directory=[template_dir] + self.template_dirs)

        if create_tables:

            @app.on_event("startup")
            async def startup_event():
                await create_db_and_tables()

        if discover_apps:
            discover_admin_modules(discover_apps)

    def _register_views(self):
        """Registers the views from the site registry."""
        from hyperadmin.routing import HyperAdminRouter

        router = HyperAdminRouter(engine=self.engine, templates=self.templates)
        router.generate_routes()
        self.router.include_router(router.router)

    def mount(self, path: str):
        """
        Mounts the admin interface on the FastAPI application.
        """
        self._register_views()
        self.app.include_router(self.router, prefix=path, tags=["HyperAdmin"])
