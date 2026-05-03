import logging
import os
from typing import Any

from fastapi import APIRouter, FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlmodel import SQLModel

from hyperadmin.core.introspection import (
    discover_sqlmodel_models,
    infer_list_display,
    infer_list_filter,
    infer_search_fields,
)
from hyperadmin.core.settings import HyperAdminSettings
from hyperadmin.db import engine as default_engine
from hyperadmin.discover import discover_admin_modules

logger = logging.getLogger("hyperadmin")


class Admin:
    """The main entry point for HyperAdmin.

    Mounts static files, wires the database engine, optionally discovers admin
    modules, and registers all model routes on the FastAPI application.

    All scalar configuration lives in ``HyperAdminSettings`` — pass a settings
    object or let HyperAdmin auto-instantiate one (which reads from environment
    variables and a ``.env`` file).

    Example::

        from fastapi import FastAPI
        from hyperadmin import Admin, HyperAdminSettings

        app = FastAPI()
        settings = HyperAdminSettings(secret_key="my-secret", theme="dark")
        admin = Admin(app, engine=engine, settings=settings)
        admin.mount("/admin")
    """

    def __init__(
        self,
        app: FastAPI,
        engine: Any = None,
        settings: HyperAdminSettings | None = None,
        auth_backend: Any = None,
        permission_checker: Any = None,
        permission_registry: Any = None,
        storage: Any = None,
    ) -> None:
        """Initialise HyperAdmin and attach it to a FastAPI application.

        Args:
            app: The FastAPI application instance to attach the admin to.
            engine: An async SQLAlchemy engine. Defaults to the built-in
                ``hyperadmin.db.engine`` if not provided.
            settings: A ``HyperAdminSettings`` instance. When ``None``, one is
                auto-instantiated (reads ``HYPERADMIN_*`` env vars and ``.env``).
            auth_backend: An optional authentication backend implementing the
                ``AuthBackend`` protocol. When ``None``, auth is disabled.
            permission_checker: An optional ``PermissionChecker`` implementation.
            permission_registry: An optional ``PermissionRegistry`` implementation.
            storage: An optional ``FileSystemStorage`` (or compatible) instance
                for file uploads. When ``None``, file upload support is disabled.
        """
        self.settings = settings or HyperAdminSettings()
        self.app = app
        self.router = APIRouter()
        self.engine = engine or default_engine
        self.auth_backend = auth_backend
        self.permission_checker = permission_checker
        self.permission_registry = permission_registry
        self.storage = storage

        self._validate_session_secret()

        template_dirs = self.settings.template_dirs
        template_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "templates")
        self.templates = Jinja2Templates(directory=[*template_dirs, template_dir])
        # Wire jinja2.ext.i18n + per-request gettext callables (C1-C). The
        # callables read translations from a context var populated by
        # LocaleMiddleware; outside a request they pass msgids through.
        from hyperadmin.i18n import install_jinja_i18n

        install_jinja_i18n(self.templates.env)

        static_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "static")
        if os.path.exists(static_dir):
            app.mount("/static", StaticFiles(directory=static_dir), name="static")

        if self.settings.create_tables:

            @app.on_event("startup")
            async def startup_event() -> None:
                await self._create_db_and_tables()

        if self.settings.discover_apps:
            discover_admin_modules(self.settings.discover_apps)

    # ── Convenience properties ─────────────────────────────────────────────

    @property
    def theme(self) -> str:
        """Active theme from settings."""
        return self.settings.theme

    # ── Validation helpers ─────────────────────────────────────────────────

    def _validate_session_secret(self) -> None:
        """Enforce session secret security policy when auth is enabled."""
        if not self.auth_backend:
            return
        if not self.settings.is_default_secret_key:
            return
        if self.settings.debug:
            logger.warning(
                "Using default session secret. Set HYPERADMIN_SECRET_KEY for production."
            )
        else:
            msg = (
                "Auth is enabled but no secret_key is configured. "
                "Set HYPERADMIN_SECRET_KEY (or pass HyperAdminSettings(secret_key=...))."
            )
            raise ValueError(msg)

    # ── Internal helpers ───────────────────────────────────────────────────

    async def _create_db_and_tables(self) -> None:
        """Creates the database and all tables using the configured engine."""
        async with self.engine.begin() as conn:
            await conn.run_sync(SQLModel.metadata.create_all)

    def _register_views(self) -> None:
        """Registers the views from the site registry."""
        from hyperadmin.routing import HyperAdminRouter

        admin_router = HyperAdminRouter(
            engine=self.engine,
            templates=self.templates,
            permission_checker=self.permission_checker if self.auth_backend else None,
            storage=self.storage,
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
            secret_key=self.settings.secret_key,
        )

    def _add_locale_middleware(self) -> None:
        """Add the locale-resolution middleware to the FastAPI app."""
        from hyperadmin.i18n import LocaleMiddleware

        self.app.add_middleware(LocaleMiddleware, settings=self.settings)

    def _mount_upload_storage(self) -> None:
        """Mount the upload storage directory as a static-files endpoint."""
        storage_path = getattr(self.storage, "_path", None)
        if storage_path is None:
            return
        storage_path_str = str(storage_path)
        if os.path.isdir(storage_path_str):
            self.app.mount(
                "/uploads",
                StaticFiles(directory=storage_path_str),
                name="uploads",
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

    def _auto_register_models(self) -> None:
        """Auto-register discovered SQLModel models with smart defaults.

        For each model not already in ``site._registry``, generates
        ``AdminOptions`` with inferred list_display, search_fields,
        and list_filter. Called from ``mount()`` when
        ``settings.auto_discover`` is ``True``.
        """
        from hyperadmin.core.model import ModelAdmin
        from hyperadmin.core.options import AdminOptions
        from hyperadmin.core.registry import site

        discovered = discover_sqlmodel_models()
        for model in discovered:
            if model in site._registry:
                continue
            try:
                options = AdminOptions(
                    list_display=infer_list_display(model),
                    search_fields=infer_search_fields(model),
                    list_filter=infer_list_filter(model),
                )
                admin_cls = type(f"{model.__name__}Admin", (ModelAdmin,), {})
                site.register(model, admin_class=admin_cls, options=options)
            except Exception:
                logger.warning("Failed to auto-register model %s", model.__name__)

    def _register_auth_models(self) -> None:
        """Auto-register User, Group, Permission in the admin site.

        Called from ``mount()`` when ``auth_backend`` is configured.
        Skips silently if a model is already registered.
        Each auth model gets its own admin class to avoid shared
        class-level state on the default ``ModelAdmin``.
        """
        from hyperadmin.auth.models import Group, Permission, User
        from hyperadmin.core.model import ModelAdmin
        from hyperadmin.core.options import AdminOptions
        from hyperadmin.core.registry import site

        if User not in site._registry:
            user_admin = type("UserAdmin", (ModelAdmin,), {})
            site.register(
                User,
                admin_class=user_admin,
                options=AdminOptions(
                    can_delete=False,
                    list_filter=["is_active", "is_superuser"],
                ),
            )
        if Group not in site._registry:
            group_admin = type("GroupAdmin", (ModelAdmin,), {})
            site.register(Group, admin_class=group_admin)
        if Permission not in site._registry:
            perm_admin = type("PermissionAdmin", (ModelAdmin,), {})
            site.register(
                Permission,
                admin_class=perm_admin,
                options=AdminOptions(can_create=False, can_delete=False),
            )

    def mount(self, path: str) -> None:
        """Mounts the admin interface on the FastAPI application."""
        if self.storage:
            self._mount_upload_storage()

        if self.auth_backend:
            self._register_auth_routes(path)
            self._register_auth_models()

        if self.settings.auto_discover:
            self._auto_register_models()

        self._register_views()
        self.templates.env.globals["admin_prefix"] = path.rstrip("/")
        self.templates.env.globals["auth_enabled"] = self.auth_backend is not None
        self.templates.env.globals["theme"] = self.settings.theme
        self.templates.env.globals["site_title"] = self.settings.site_title
        self.templates.env.globals["site_header"] = self.settings.site_header

        if self.auth_backend:
            self.router.on_startup.append(self._sync_permissions)

        self.app.include_router(self.router, prefix=path, tags=["HyperAdmin"])

        # LocaleMiddleware runs whether or not auth is configured. It must be
        # added before the auth middleware so the chain is
        # SessionMiddleware -> AuthenticationMiddleware -> LocaleMiddleware -> routes.
        self._add_locale_middleware()

        if self.auth_backend:
            self._add_auth_middleware(path)
