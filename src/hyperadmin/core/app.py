import os
from typing import Any

from fastapi import APIRouter, FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlmodel import SQLModel

from hyperadmin.db import engine as default_engine
from hyperadmin.discover import discover_admin_modules


class Admin:
    """The main entry point for HyperAdmin.

    Mounts static files, wires the database engine, optionally discovers admin
    modules, and registers all model routes on the FastAPI application.

    Example:
        ```python
        from fastapi import FastAPI
        from hyperadmin import Admin

        app = FastAPI()
        admin = Admin(app, engine=engine, discover_apps=["myapp"])
        admin.mount("/admin")
        ```
    """

    def __init__(
        self,
        app: FastAPI,
        discover_apps: list[str] | None = None,
        create_tables: bool = True,
        engine: Any = None,
        template_dirs: list[str] | None = None,
        auth_backend: Any = None,
        permission_checker: Any = None,
        permission_registry: Any = None,
        session_secret: str | None = None,
    ):
        """Initialise HyperAdmin and attach it to a FastAPI application.

        Args:
            app: The FastAPI application instance to attach the admin to.
            discover_apps: List of Python module paths to auto-discover
                ``admin.py`` files in (e.g. ``["myapp", "otherapp"]``).
            create_tables: When ``True``, registers an ``on_event("startup")``
                handler that calls ``SQLModel.metadata.create_all``.
            engine: An async SQLAlchemy engine. Defaults to the built-in
                ``hyperadmin.db.engine`` if not provided.
            template_dirs: Additional Jinja2 template directories searched
                before the built-in HyperAdmin templates.
            auth_backend: An optional authentication backend implementing the
                ``AuthBackend`` protocol. When ``None``, auth is disabled.
            permission_checker: An optional ``PermissionChecker`` implementation.
            permission_registry: An optional ``PermissionRegistry`` implementation.
            session_secret: Secret key for ``SessionMiddleware``. Required when
                ``auth_backend`` is set.
        """
        self.app = app
        self.router = APIRouter()
        self.engine = engine or default_engine
        self.auth_backend = auth_backend
        self.permission_checker = permission_checker
        self.permission_registry = permission_registry
        self.session_secret = session_secret
        self.template_dirs = template_dirs or []
        template_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "templates")
        self.templates = Jinja2Templates(directory=[template_dir, *self.template_dirs])

        # Mount static files for the admin interface
        static_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "static")
        if os.path.exists(static_dir):
            app.mount("/static", StaticFiles(directory=static_dir), name="static")

        if create_tables:

            @app.on_event("startup")
            async def startup_event():
                await self._create_db_and_tables()

        if discover_apps:
            discover_admin_modules(discover_apps)

    async def _create_db_and_tables(self):
        """Creates the database and all tables using the configured engine."""
        async with self.engine.begin() as conn:
            await conn.run_sync(SQLModel.metadata.create_all)

    def _register_views(self):
        """Registers the views from the site registry."""
        from hyperadmin.routing import HyperAdminRouter

        admin_router = HyperAdminRouter(
            engine=self.engine,
            templates=self.templates,
            permission_checker=self.permission_checker if self.auth_backend else None,
        )
        admin_router.generate_routes()
        routers = admin_router.get_routers()
        for router in routers:
            self.router.include_router(router)

    def _register_auth_routes(self, path: str) -> None:
        """Register login/logout routes when auth is enabled."""
        from starlette.requests import Request

        from hyperadmin.auth.views import login_view, logout_view

        admin_prefix = path.rstrip("/")
        templates = self.templates
        auth_backend = self.auth_backend

        async def login_get(request: Request):
            return await login_view(request, templates, auth_backend, admin_prefix)

        async def login_post(request: Request):
            return await login_view(request, templates, auth_backend, admin_prefix)

        async def logout_post(request: Request):
            return await logout_view(request, auth_backend, admin_prefix)

        self.router.add_api_route("/login", login_get, methods=["GET"], name="admin-login")
        self.router.add_api_route("/login", login_post, methods=["POST"], name="admin-login-post")
        self.router.add_api_route("/logout", logout_post, methods=["POST"], name="admin-logout")

    def _add_auth_middleware(self, path: str) -> None:
        """Add session and authentication middleware."""
        from starlette.middleware.sessions import SessionMiddleware

        from hyperadmin.auth.middleware import AuthenticationMiddleware

        admin_prefix = path.rstrip("/")
        self.app.add_middleware(
            AuthenticationMiddleware,
            auth_backend=self.auth_backend,
            admin_prefix=admin_prefix,
        )
        self.app.add_middleware(
            SessionMiddleware,
            secret_key=self.session_secret or "hyperadmin-default-secret",
        )

    async def _sync_permissions(self) -> None:
        """Sync permissions for all registered models to the database."""
        if not self.permission_registry:
            return

        from hyperadmin.core.registry import site

        models = []
        for model, admin_class in site._registry.items():
            model_name = model.__name__.lower()
            models.append((model_name, admin_class))
        await self.permission_registry.sync_permissions(models)

    def mount(self, path: str):
        """Mounts the admin interface on the FastAPI application."""
        if self.auth_backend:
            self._register_auth_routes(path)

        self._register_views()
        self.templates.env.globals["admin_prefix"] = path.rstrip("/")
        self.templates.env.globals["auth_enabled"] = self.auth_backend is not None

        if self.auth_backend:
            self.router.on_startup.append(self._sync_permissions)

        self.app.include_router(self.router, prefix=path, tags=["HyperAdmin"])

        if self.auth_backend:
            self._add_auth_middleware(path)
