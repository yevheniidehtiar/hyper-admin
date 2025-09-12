from typing import Any

from fastapi import APIRouter, FastAPI

from hyperadmin.db import create_db_and_tables
from hyperadmin.db import engine as default_engine
from hyperadmin.discover import discover_admin_modules


class Admin:
    """The main Admin class that holds the admin interface."""

    def __init__(
        self,
        app: FastAPI,
        discover_apps: list[str] | None = None,
        create_tables: bool = True,
        engine: Any = None,
    ):
        self.app = app
        self.router = APIRouter()
        self.engine = engine or default_engine

        if create_tables:

            @app.on_event("startup")
            async def startup_event():
                await create_db_and_tables()

        if discover_apps:
            discover_admin_modules(discover_apps)

    def _register_views(self):
        """Registers the views from the site registry."""
        from hyperadmin.routing import HyperAdminRouter

        admin_router = HyperAdminRouter(engine=self.engine)
        admin_router.generate_routes()
        routers = admin_router.get_routers()
        for router in routers:
            self.router.include_router(router)

    def mount(self, path: str):
        """
        Mounts the admin interface on the FastAPI application.
        """
        self._register_views()
        self.app.include_router(self.router, prefix=path, tags=["HyperAdmin"])
