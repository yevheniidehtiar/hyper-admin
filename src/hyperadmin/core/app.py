import logging
import os
from typing import TYPE_CHECKING, Any

from fastapi import APIRouter, FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from hyperadmin.core.introspection import (
    discover_sqlmodel_models,
    infer_list_display,
    infer_list_filter,
    infer_search_fields,
)
from hyperadmin.core.lifecycle import Lifecycle, StartupGuardMiddleware
from hyperadmin.core.settings import HyperAdminSettings
from hyperadmin.discover import discover_admin_modules
from hyperadmin.realtime import ConnectionRegistry, RealtimeSettings
from hyperadmin.realtime.sse import make_sse_handler
from hyperadmin.realtime.ws import make_ws_handler

if TYPE_CHECKING:
    from contextlib import AbstractAsyncContextManager

    from hyperadmin.core.adapters import SessionFactory
    from hyperadmin.db import TableScope

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

    def __init__(  # noqa: PLR0917 - public signature; keyword-only would break callers
        self,
        app: FastAPI,
        engine: Any = None,
        settings: HyperAdminSettings | None = None,
        auth_backend: Any = None,
        permission_checker: Any = None,
        permission_registry: Any = None,
        storage: Any = None,
        otp_service: Any = None,
        realtime: RealtimeSettings | None = None,
        *,
        session_factory: "SessionFactory | None" = None,
    ) -> None:
        """Initialise HyperAdmin and attach it to a FastAPI application.

        Args:
            app: The FastAPI application instance to attach the admin to.
            engine: An async SQLAlchemy engine. When both ``engine`` and
                ``session_factory`` are ``None`` (demo mode), an engine is built
                lazily from ``settings.database_url`` by
                ``hyperadmin.db.get_default_engine``.
            settings: A ``HyperAdminSettings`` instance. When ``None``, one is
                auto-instantiated (reads ``HYPERADMIN_*`` env vars and ``.env``).
            auth_backend: An optional authentication backend implementing the
                ``AuthBackend`` protocol. When ``None``, auth is disabled.
            permission_checker: An optional ``PermissionChecker`` implementation.
            permission_registry: An optional ``PermissionRegistry`` implementation.
            storage: An optional ``FileSystemStorage`` (or compatible) instance
                for file uploads. When ``None``, file upload support is disabled.
            otp_service: An optional MFA OTP service (e.g. ``EmailOTPService``).
                When ``None``, the MFA endpoints (``/mfa/challenge`` etc) are
                NOT registered and ``login_view`` skips the MFA branch — apps
                without MFA are entirely unaffected (C3-A, #487).
            realtime: Opt-in ``RealtimeSettings``. When ``None`` (default),
                no SSE / WebSocket endpoints are registered and the status
                widget is not injected — fully backward compatible. See
                ``docs/specs/realtime-connection-foundation.md``.
            session_factory: A host-provided session factory (e.g.
                ``async_sessionmaker(engine)``), forwarded to every adapter and
                auth service instead of ``engine``. Bring-your-own-app hosts
                that manage their own engine and session lifecycle pass this
                instead of ``engine=``. See SDD C.3.
        """
        self.settings = settings or HyperAdminSettings()
        self.app = app
        self.router = APIRouter()
        demo_mode = engine is None and session_factory is None
        self.engine = engine if not demo_mode else self._default_engine()
        self.session_factory = session_factory
        self.auth_backend = auth_backend
        self.permission_checker = permission_checker
        self.permission_registry = permission_registry
        self.storage = storage
        self.otp_service = otp_service
        self.realtime = realtime
        self._realtime_registry: ConnectionRegistry | None = (
            ConnectionRegistry() if realtime is not None else None
        )

        self._validate_session_secret()

        template_dirs = self.settings.template_dirs
        template_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "templates")
        self.templates = Jinja2Templates(directory=[*template_dirs, template_dir])
        # Wire jinja2.ext.i18n + per-request gettext callables (C1-C). The
        # callables read translations from a context var populated by
        # LocaleMiddleware; outside a request they pass msgids through.
        from hyperadmin.i18n import install_jinja_i18n

        install_jinja_i18n(self.templates.env)
        # Namespace-aware url_for (C.1): falls back to today's plain-name
        # resolution until mount() wires scope["hyperadmin"]["namespace"]
        # (isolated sub-app mount, st-v058-byoa-35), so this is a no-op today.
        from hyperadmin.views.urls import install_namespaced_url_for

        install_namespaced_url_for(self.templates.env)

        static_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "static")
        if os.path.exists(static_dir):
            app.mount("/static", StaticFiles(directory=static_dir), name="static")

        # Opt-in auto-create decision is made once, here, from the settings this
        # Admin was built with — never re-evaluated on every startup() call.
        self._auto_create_tables = self._should_create_tables(demo_mode=demo_mode)
        self._lifecycle = Lifecycle(
            create_tables=self._create_tables_if_opted_in,
            sync_permissions=self._sync_permissions,
            drain=self._drain_realtime,
            realtime_enabled=realtime is not None,
        )

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

    def _should_create_tables(self, *, demo_mode: bool) -> bool:
        """Whether ``startup()`` auto-creates tables (SDD C.2).

        ``create_tables`` defaults to ``False``, so a host ``engine=`` or
        ``session_factory=`` never gets DDL run against it unless the host opts in
        explicitly. Demo mode (no ``engine=``, no ``session_factory=``) builds its
        engine from ``settings.database_url``, which may be the host's own database
        (``HYPERADMIN_DATABASE_URL``); there, tables are still auto-created when that
        URL is SQLite — so zero-config ``Admin(app).mount("/admin")`` keeps working —
        but never for any other URL, so a host database is never altered behind its
        migrations' back (Goal 4). An explicit ``create_tables=`` (either value)
        always wins over the demo-mode default.
        """
        if "create_tables" in self.settings.model_fields_set:
            return self.settings.create_tables
        if not demo_mode:
            return False
        from hyperadmin.db import is_sqlite_url

        if is_sqlite_url(self.settings.database_url):
            logger.warning(
                "HyperAdmin demo mode: database_url is SQLite, so tables are created "
                "automatically at startup. Set create_tables=False to disable this."
            )
            return True
        logger.warning(
            "HyperAdmin demo mode: database_url is not SQLite, so no tables are created "
            "automatically. Set create_tables=True (HYPERADMIN_CREATE_TABLES=true) to "
            "create them at startup, or create them with your migrations."
        )
        return False

    def _default_engine(self) -> Any:
        """Build (or reuse) the demo-mode engine for ``settings.database_url``."""
        from hyperadmin.db import get_default_engine

        return get_default_engine(self.settings)

    async def _create_db_and_tables(self) -> None:
        """Creates the database and all tables using the configured engine.

        In ``session_factory=``-only mode (no ``engine=``), the bind is taken
        from the factory itself via ``db.resolve_bind``, which raises a clear
        error when the factory carries no async engine (SDD C.3).

        Kept as a private alias for one release — the ERP example calls it
        directly from its own host lifespan (SDD C.2 review amendments).
        """
        from hyperadmin.db import create_tables, resolve_bind

        bind = self.engine if self.engine is not None else resolve_bind(self.session_factory)
        await create_tables(bind)

    async def _create_tables_if_opted_in(self) -> None:
        """``Lifecycle``'s ``create_tables`` callable: respects the opt-in decision.

        ``self._auto_create_tables`` is computed once, in ``__init__``, from the
        settings this ``Admin`` was built with (SDD C.2) — never re-evaluated here.
        """
        if self._auto_create_tables:
            await self._create_db_and_tables()

    async def _drain_realtime(self) -> None:
        """``Lifecycle``'s ``drain`` callable: a no-op when realtime is disabled."""
        if self._realtime_registry is not None:
            await self._realtime_registry.drain()

    # ── Public lifecycle API (SDD C.2) ─────────────────────────────────────

    async def startup(self) -> None:
        """Create tables (if opted in), then sync permissions. Idempotent.

        Call this directly, or compose :meth:`lifespan` into the host's own
        ``lifespan=`` — either way it only runs once. When neither is done,
        the first admin request runs it instead, as a safety net (``mount()``
        installs :class:`~hyperadmin.core.lifecycle.StartupGuardMiddleware`).
        """
        await self._lifecycle.startup()

    async def shutdown(self) -> None:
        """Drain realtime (SSE/WebSocket) connections.

        Unlike :meth:`startup`, this has **no** safety net: it only runs when
        the host calls it directly or composes :meth:`lifespan`.
        """
        await self._lifecycle.shutdown()

    def lifespan(self) -> "AbstractAsyncContextManager[None]":
        """Async context manager the host composes into its own ``lifespan=``.

        Example::

            @asynccontextmanager
            async def lifespan(app: FastAPI):
                async with admin.lifespan():
                    yield


            app = FastAPI(lifespan=lifespan)
        """
        return self._lifecycle.lifespan()

    async def create_tables(self, scope: "TableScope" = "all") -> None:
        """Create database tables directly, independent of ``settings.create_tables``.

        Args:
            scope: ``"hyperadmin"`` creates only the built-in ``hyperadmin_*``
                tables (what ``hyperadmin init-db`` does by default);
                ``"all"`` creates every table on ``SQLModel.metadata``,
                matching ``settings.create_tables=True``'s behaviour.
        """
        from hyperadmin.db import create_tables as db_create_tables
        from hyperadmin.db import resolve_bind

        bind = self.engine if self.engine is not None else resolve_bind(self.session_factory)
        tables = None
        if scope == "hyperadmin":
            import hyperadmin.auth as auth_module

            tables = list(auth_module.metadata().tables.values())
        await db_create_tables(bind, tables=tables)

    def _register_views(self) -> None:
        """Registers the views from the site registry."""
        from hyperadmin.routing import HyperAdminRouter

        admin_router = HyperAdminRouter(
            engine=self.engine,
            templates=self.templates,
            permission_checker=self.permission_checker if self.auth_backend else None,
            storage=self.storage,
            timezone=self.settings.tzinfo,
            datetime_format=self.settings.datetime_format,
            session_factory=self.session_factory,
        )
        admin_router.generate_routes()
        routers = admin_router.get_routers()
        for router in routers:
            self.router.include_router(router)

    def _register_auth_routes(self, path: str) -> None:
        """Register login/logout (and MFA) routes when auth is enabled."""
        from starlette.requests import Request

        from hyperadmin.auth.views import login_view, logout_view

        admin_prefix = path.rstrip("/")
        templates = self.templates
        auth_backend = self.auth_backend
        otp_service = self.otp_service

        async def login_get(request: Request):
            return await login_view(request, templates, auth_backend, admin_prefix, otp_service)

        async def login_post(request: Request):
            return await login_view(request, templates, auth_backend, admin_prefix, otp_service)

        async def logout_post(request: Request):
            return await logout_view(request, auth_backend, admin_prefix)

        self.router.add_api_route("/login", login_get, methods=["GET"], name="admin-login")
        self.router.add_api_route("/login", login_post, methods=["POST"], name="admin-login-post")
        self.router.add_api_route("/logout", logout_post, methods=["POST"], name="admin-logout")

        if otp_service is not None:
            self._register_mfa_routes(admin_prefix)

    def _register_mfa_routes(self, admin_prefix: str) -> None:
        """Register the MFA challenge / verify / resend / settings endpoints.

        Only called when ``otp_service`` is configured. Apps without MFA see
        no new routes — ``mfa_enabled=True`` users in such apps will hit the
        normal single-factor path because ``login_view`` skips the MFA branch
        unless an ``otp_service`` is provided.
        """
        from starlette.requests import Request

        from hyperadmin.auth.views import (
            mfa_challenge_view,
            mfa_disable_view,
            mfa_enable_view,
            mfa_resend_view,
            mfa_settings_view,
            mfa_verify_view,
        )

        templates = self.templates
        auth_backend = self.auth_backend
        otp_service = self.otp_service

        async def challenge_get(request: Request):
            return await mfa_challenge_view(request, templates, admin_prefix)

        async def verify_post(request: Request):
            return await mfa_verify_view(
                request, templates, auth_backend, otp_service, admin_prefix
            )

        async def resend_post(request: Request):
            return await mfa_resend_view(
                request, templates, auth_backend, otp_service, admin_prefix
            )

        async def settings_get(request: Request):
            return await mfa_settings_view(request, templates, admin_prefix)

        async def enable_post(request: Request):
            return await mfa_enable_view(
                request, templates, auth_backend, otp_service, admin_prefix
            )

        async def disable_post(request: Request):
            return await mfa_disable_view(
                request, templates, auth_backend, otp_service, admin_prefix
            )

        self.router.add_api_route(
            "/mfa/challenge", challenge_get, methods=["GET"], name="admin-mfa-challenge"
        )
        self.router.add_api_route(
            "/mfa/verify", verify_post, methods=["POST"], name="admin-mfa-verify"
        )
        self.router.add_api_route(
            "/mfa/resend", resend_post, methods=["POST"], name="admin-mfa-resend"
        )
        self.router.add_api_route(
            "/mfa/settings", settings_get, methods=["GET"], name="admin-mfa-settings"
        )
        self.router.add_api_route(
            "/mfa/enable", enable_post, methods=["POST"], name="admin-mfa-enable"
        )
        self.router.add_api_route(
            "/mfa/disable", disable_post, methods=["POST"], name="admin-mfa-disable"
        )

    def _register_realtime_routes(self, path: str) -> None:
        """Register the SSE GET route and WebSocket route under the admin prefix.

        Both endpoints share a single ``ConnectionRegistry`` so ``shutdown()``
        (``Admin.shutdown()`` / ``Lifecycle.shutdown()``) can drain every open
        connection in one pass. There is no ``on_event("shutdown")`` hook here
        any more (SDD C.2): it only ever drained when the host did NOT pass
        its own ``lifespan=``, which is backwards — draining matters most
        for hosts that DO manage their own lifespan. Compose ``admin.lifespan()``
        (or call ``admin.shutdown()`` yourself) to drain on shutdown.
        """
        if self.realtime is None or self._realtime_registry is None:
            return
        admin_prefix = path.rstrip("/")
        registry = self._realtime_registry
        settings = self.realtime

        sse_handler = make_sse_handler(registry, settings)
        self.router.add_api_route(
            "/realtime/sse",
            sse_handler,
            methods=["GET"],
            name="admin-realtime-sse",
        )
        ws_handler = make_ws_handler(registry, settings, self.auth_backend)
        self.app.router.add_websocket_route(
            f"{admin_prefix}/realtime/ws",
            ws_handler,
            name="admin-realtime-ws",
        )

        if settings.enable_test_endpoints:
            from hyperadmin.realtime._debug import (
                make_count_handler,
                make_disconnect_all_handler,
                make_disconnect_transport_handler,
            )

            self.router.add_api_route(
                "/_test/realtime/count",
                make_count_handler(registry),
                methods=["GET"],
                name="admin-realtime-test-count",
            )
            self.router.add_api_route(
                "/_test/realtime/disconnect_all",
                make_disconnect_all_handler(registry),
                methods=["POST"],
                name="admin-realtime-test-disconnect-all",
            )
            self.router.add_api_route(
                "/_test/realtime/disconnect/{transport}",
                make_disconnect_transport_handler(registry),
                methods=["POST"],
                name="admin-realtime-test-disconnect-transport",
            )

    def _register_locale_route(self, path: str) -> None:
        """Register the POST /locale route for the locale switcher."""
        from starlette.requests import Request
        from starlette.responses import Response

        from hyperadmin.views.locale import set_locale_view

        admin_prefix = path.rstrip("/")
        settings = self.settings

        async def locale_post(request: Request) -> Response:
            return await set_locale_view(request, settings, admin_prefix)

        self.router.add_api_route(
            "/locale",
            locale_post,
            methods=["POST"],
            name="admin-locale",
        )

    def _add_auth_middleware(self, path: str) -> None:
        """Add session and authentication middleware."""
        from starlette.middleware.sessions import SessionMiddleware

        from hyperadmin.auth.middleware import AuthenticationMiddleware

        admin_prefix = path.rstrip("/")
        self.app.add_middleware(
            AuthenticationMiddleware,
            auth_backend=self.auth_backend,
            admin_prefix=admin_prefix,
            permission_checker=self.permission_checker,
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
        from hyperadmin.views.error_pages import admin_route_class

        # Admin routes render 403/404/409 inside the admin layout for people (JSON stays
        # for API callers). Set before any route is added to the admin router.
        self.router.route_class = admin_route_class(self.templates)

        if self.storage:
            self._mount_upload_storage()

        if self.auth_backend:
            self._register_auth_routes(path)
            self._register_auth_models()

        if self.settings.auto_discover:
            self._auto_register_models()

        self._register_locale_route(path)
        self._register_realtime_routes(path)
        self._register_views()
        self.templates.env.globals["admin_prefix"] = path.rstrip("/")
        self.templates.env.globals["auth_enabled"] = self.auth_backend is not None
        self.templates.env.globals["realtime_enabled"] = self.realtime is not None
        self.templates.env.globals["theme"] = self.settings.theme
        self.templates.env.globals["site_title"] = self.settings.site_title
        self.templates.env.globals["site_header"] = self.settings.site_header
        self.templates.env.globals["supported_locales"] = self.settings.supported_locales
        from hyperadmin.i18n import RTL_LOCALES

        self.templates.env.globals["rtl_locales"] = RTL_LOCALES

        self.app.include_router(self.router, prefix=path, tags=["HyperAdmin"])

        # LocaleMiddleware runs whether or not auth is configured. It must be
        # added before the auth middleware so the chain is
        # SessionMiddleware -> AuthenticationMiddleware -> LocaleMiddleware -> routes.
        self._add_locale_middleware()

        if self.auth_backend:
            self._add_auth_middleware(path)

        # Added last so it is outermost (SDD C.2): the safety net must run before
        # Session/Auth/Locale, so a permission sync it triggers is visible to this
        # same request's own permission checks. One mechanism now, not two — there
        # is no more ``router.on_startup`` append here (Starlette silently ignores
        # on_startup/on_shutdown handlers once a host passes its own ``lifespan=``,
        # and a mounted sub-app never receives lifespan events at all).
        self.app.add_middleware(
            StartupGuardMiddleware, lifecycle=self._lifecycle, admin_prefix=path
        )
