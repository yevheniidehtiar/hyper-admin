import logging
import os
import sys
import warnings
from typing import TYPE_CHECKING, Any, Literal

from fastapi import APIRouter, Depends, FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from hyperadmin.core.introspection import (
    discover_sqlmodel_models,
    infer_list_display,
    infer_list_filter,
    infer_search_fields,
)
from hyperadmin.core.lifecycle import Lifecycle, StartupGuardMiddleware
from hyperadmin.core.plugin_wiring import (
    build_plugin_routes,
    extend_template_loader,
    mount_plugin_static,
    plugin_permission_rows,
    resolve_plugin_nav,
)
from hyperadmin.core.plugins import PluginRegistry
from hyperadmin.core.settings import HyperAdminSettings
from hyperadmin.core.storage_paths import storage_root
from hyperadmin.discover import discover_admin_modules
from hyperadmin.realtime import ConnectionRegistry, RealtimeEvent, RealtimeSettings
from hyperadmin.realtime.emitting import RealtimeEmitter
from hyperadmin.realtime.sse import make_sse_handler
from hyperadmin.realtime.ws import make_ws_handler

if TYPE_CHECKING:
    from collections.abc import Iterable, Mapping
    from contextlib import AbstractAsyncContextManager

    from fastapi import params
    from fastapi.routing import APIRoute

    from hyperadmin.auth.bridge import ExternalAuth
    from hyperadmin.core.adapters import SessionFactory
    from hyperadmin.core.csrf import EffectiveCsrfMode
    from hyperadmin.db import TableScope
    from hyperadmin.views.csrf import CsrfGuard

logger = logging.getLogger("hyperadmin")

#: HyperAdmin's own CSS, JS, fonts and icons, served under ``{prefix}/static``.
_STATIC_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "static")

#: ``"builtin"`` with ``auth_backend=``, ``"external"`` with ``auth=`` (SDD B.3).
AuthMode = Literal["builtin", "external"]


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
        auth: "ExternalAuth | None" = None,
        disabled_plugins: "Iterable[str]" = (),
        plugin_settings: "Mapping[str, Mapping[str, Any]] | None" = None,
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
            storage: An optional ``FileSystemStorage`` or ``S3StorageBackend``
                instance for file uploads. When ``None``, ``settings.storage_backend``
                decides: ``"s3"`` builds an ``S3StorageBackend`` from the ``aws_*``
                settings, ``"local"`` (default) disables file upload support.
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
            auth: Bring-your-own-auth (``ExternalAuth``): the host's own
                ``get_user`` dependency guards every admin route, and no
                built-in session, login or ``hyperadmin_*`` table is used.
                Mutually exclusive with ``auth_backend`` and ``otp_service``.
                See SDD B.3.
            disabled_plugins: Names of ``hyperadmin.plugins`` entry points not to
                load; unioned with ``HYPERADMIN_DISABLED_PLUGINS``.
            plugin_settings: Raw settings per plugin name, validated into each
                plugin's ``settings_model`` before its ``on_register``. See
                ``docs/specs/plugin-registry.md``.

        Raises:
            ValueError: ``auth`` is combined with ``auth_backend`` or
                ``otp_service``, or with a ``ModelPermissionChecker`` while
                ``settings.register_auth_models`` is not ``True``.
        """
        self.settings = settings or HyperAdminSettings()
        self.app = app
        self.router = APIRouter()
        #: Admin routes outside the auth guard (SDD B.3): the bridge login form, and
        #: the token handoff, which carries its own guard. Included without the
        #: protected router's dependencies.
        self.public_router = APIRouter()
        demo_mode = engine is None and session_factory is None
        self.engine = engine if not demo_mode else self._default_engine()
        self.session_factory = session_factory
        self.auth_backend = auth_backend
        self.permission_checker = permission_checker
        self.permission_registry = permission_registry
        self.storage = storage if storage is not None else self._default_storage()
        self.otp_service = otp_service
        self.auth = auth
        self._auth_mode: AuthMode | None = None
        if auth is not None:
            self._auth_mode = "external"
            self._validate_external_auth()
            self.permission_checker = self._resolve_bridge_permission_checker(auth)
        elif auth_backend is not None:
            self._auth_mode = "builtin"
        self.realtime = realtime
        self._realtime_registry: ConnectionRegistry | None = (
            ConnectionRegistry() if realtime is not None else None
        )
        self._realtime_pubsub = realtime.resolve_pubsub() if realtime is not None else None
        self._realtime_emitter: RealtimeEmitter | None = (
            RealtimeEmitter(self._realtime_pubsub, realtime.channel_prefix)
            if realtime is not None and self._realtime_pubsub is not None
            else None
        )
        self._notification_models: set[str] = set()

        self._validate_secret_key()

        template_dirs = self.settings.template_dirs
        template_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "templates")
        self.templates = Jinja2Templates(directory=[*template_dirs, template_dir])
        # Wire jinja2.ext.i18n + per-request gettext callables (C1-C). The
        # callables read translations from a context var populated by
        # LocaleMiddleware; outside a request they pass msgids through.
        from hyperadmin.i18n import install_jinja_i18n

        install_jinja_i18n(self.templates.env)
        # Namespace-aware url_for (C.1): tries "<namespace>:<name>" first when
        # mount() has tagged the request scope (isolated mode), then the plain
        # name (router mode, and host routes in either mode).
        from hyperadmin.views.urls import install_namespaced_url_for

        install_namespaced_url_for(self.templates.env)

        self._asgi_app: FastAPI | None = None

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

        # Assigned before loading: a plugin's on_register calls admin.plugins.add_*.
        # What plugins contribute is applied in mount().
        self.plugins = PluginRegistry()
        if self.settings.plugins_enabled:
            self.plugins.load_entry_points(
                admin=self, disabled=disabled_plugins, settings=plugin_settings
            )
        self._register_permissions_matrix()

    # ── Convenience properties ─────────────────────────────────────────────

    @property
    def theme(self) -> str:
        """Active theme from settings."""
        return self.settings.theme

    @property
    def asgi_app(self) -> FastAPI | None:
        """The private admin sub-application, once ``mount()`` ran in isolated mode.

        ``None`` before ``mount()``, and in (legacy) router mode, where admin
        routes live directly on the host app. Hosts may add their own admin-side
        routes to it; they then run behind the admin's middleware.
        """
        return self._asgi_app

    # ── Validation helpers ─────────────────────────────────────────────────

    @property
    def csrf_mode(self) -> "EffectiveCsrfMode":
        """The effective CSRF mode: ``csrf_mode="auto"`` enforces when auth is on (SDD D.1).

        "Auth is on" means ``auth_backend``, ``auth=`` or app-level ``dependencies`` on the
        host app (the usual host login guard). Host auth middleware cannot be
        detected; such hosts set ``csrf_mode="enforce"``.
        """
        from hyperadmin.core.csrf import resolve_csrf_mode

        # getattr: a plain Starlette router (or a test double) has no ``dependencies``.
        host_dependencies = getattr(getattr(self.app, "router", None), "dependencies", None)
        auth_enabled = self._auth_mode is not None or bool(host_dependencies)
        return resolve_csrf_mode(self.settings.csrf_mode, auth_enabled=auth_enabled)

    def _validate_external_auth(self) -> None:
        """Reject combinations ``auth=`` cannot serve (SDD B.3)."""
        for name, value in (("auth_backend", self.auth_backend), ("otp_service", self.otp_service)):
            if value is not None:
                msg = (
                    f"Admin(auth=...) and Admin({name}=...) are mutually exclusive: "
                    f"auth= brings the host's own authentication, {name}= is built-in auth."
                )
                raise ValueError(msg)
        # Looked up, not imported: importing auth.permissions registers the
        # hyperadmin_* tables, which a bridge-mode host must never get. A checker
        # cannot be a ModelPermissionChecker unless its module is already loaded.
        model_checker = getattr(
            sys.modules.get("hyperadmin.auth.permissions"), "ModelPermissionChecker", None
        )
        if (
            model_checker is not None
            and isinstance(self.permission_checker, model_checker)
            and self.settings.register_auth_models is not True
        ):
            msg = (
                "ModelPermissionChecker with Admin(auth=...) requires "
                "settings.register_auth_models=True: it reads the built-in hyperadmin_* "
                "permission tables keyed on user.id, so host user ids must also be ints "
                "matching hyperadmin_users. Pass ExternalAuth(has_permission=...) instead "
                "to keep permissions in the host application."
            )
            raise ValueError(msg)

    def _resolve_bridge_permission_checker(self, auth: "ExternalAuth") -> Any:
        """Pick the bridge-mode permission checker; the first match wins (SDD B.3).

        1. An explicit ``Admin(permission_checker=...)``.
        2. ``auth.has_permission``: used as is when it is a ``PermissionChecker``,
           wrapped in ``CallablePermissionChecker`` when it is a plain callable.
        3. The fail-safe ``BridgeDefaultPermissionChecker``: superusers get every
           permission, everyone else ``view_*`` only (all of them with
           ``allow_full_access=True``).

        Every checker except one built from ``has_permission`` is wrapped in
        ``HostUserModelGuard``, so a non-superuser never gets ``change_*`` or
        ``delete_*`` on the host user model unless ``has_permission`` grants it.
        """
        import hyperadmin.auth as auth_package
        from hyperadmin.auth.bridge import (
            BridgeDefaultPermissionChecker,
            CallablePermissionChecker,
            HostUserModelGuard,
        )

        # Lets hyperadmin.auth.metadata() warn a bridge-mode host (SDD B.5).
        auth_package._note_bridge_admin_constructed()
        if self.permission_checker is not None:
            return HostUserModelGuard(self.permission_checker)
        has_permission = auth.has_permission
        if has_permission is not None:
            if callable(getattr(has_permission, "has_permission", None)):
                return has_permission
            return CallablePermissionChecker(has_permission)  # type: ignore[arg-type]
        logger.warning(
            "HyperAdmin Admin(auth=ExternalAuth(...)) has no has_permission: using the "
            "fail-safe default (superusers get every permission, everyone else view-only). "
            "Pass ExternalAuth(has_permission=...) to map the host's own permissions."
        )
        if auth.allow_full_access:
            logger.warning(
                "HyperAdmin ExternalAuth(allow_full_access=True): every user that passes "
                "can_access gets every permission, except change/delete on the host user model."
            )
        return HostUserModelGuard(
            BridgeDefaultPermissionChecker(allow_full_access=auth.allow_full_access)
        )

    def _validate_secret_key(self) -> None:
        """Refuse the default ``secret_key`` when it signs anything that matters.

        Fires when auth is enabled (it signs the session) or when CSRF resolves to
        ``enforce`` (it signs the CSRF tokens, SDD D.1).
        """
        if not self.auth_backend and self.csrf_mode != "enforce":
            return
        if not self.settings.is_default_secret_key:
            return
        if self.settings.debug:
            logger.warning(
                "Using default session secret. Set HYPERADMIN_SECRET_KEY for production."
            )
        else:
            msg = (
                "Auth or CSRF enforcement is enabled but no secret_key is configured. "
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
        if self._realtime_emitter is not None:
            await self._realtime_emitter.drain()
        if self._realtime_pubsub is not None:
            await self._realtime_pubsub.close()

    def publish_event(self, event: RealtimeEvent) -> None:
        """Publish a custom CRUD event; a no-op unless realtime and notifications are enabled."""
        if (
            self._realtime_emitter is None
            or event.model_name.lower() not in self._notification_models
        ):
            logger.debug("Dropping realtime event for %s (not enabled)", event.model_name)
            return
        self._realtime_emitter.schedule(event)

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
            permission_checker=self.permission_checker if self._auth_mode is not None else None,
            storage=self.storage,
            timezone=self.settings.tzinfo,
            datetime_format=self.settings.datetime_format,
            session_factory=self.session_factory,
            debug=self.settings.debug,
            route_class=self.router.route_class,
            realtime_emitter=self._realtime_emitter,
            realtime_settings=self.realtime,
        )
        admin_router.generate_routes()
        self._notification_models = admin_router.notification_models
        routers = admin_router.get_routers()
        for router in routers:
            self.router.include_router(router)

    def _register_auth_routes(self, path: str) -> None:
        """Register login/logout (and MFA) routes when auth is enabled."""
        from starlette.requests import Request

        from hyperadmin.auth.views import login_view, logout_view
        from hyperadmin.views.urls import request_admin_path

        admin_prefix = path.rstrip("/")
        templates = self.templates
        auth_backend = self.auth_backend
        otp_service = self.otp_service

        # Redirects use the per-request admin path (SDD C.1), so they follow a
        # host served under a root_path (e.g. "/api/admin/", not "/admin/").
        async def login_get(request: Request):
            base = request_admin_path(request, admin_prefix)
            return await login_view(request, templates, auth_backend, base, otp_service)

        async def login_post(request: Request):
            base = request_admin_path(request, admin_prefix)
            return await login_view(request, templates, auth_backend, base, otp_service)

        async def logout_post(request: Request):
            base = request_admin_path(request, admin_prefix)
            return await logout_view(request, auth_backend, base)

        self.router.add_api_route("/login", login_get, methods=["GET"], name="admin-login")
        self.router.add_api_route("/login", login_post, methods=["POST"], name="admin-login-post")
        self.router.add_api_route("/logout", logout_post, methods=["POST"], name="admin-logout")

        if otp_service is not None:
            self._register_mfa_routes(admin_prefix)

    def _register_bridge_routes(self, path: str, auth: "ExternalAuth") -> None:
        """Register the bridge-mode logout, token handoff and login form (SDD B.3, B.4).

        - ``POST {prefix}/logout``: protected and CSRF-checked; clears the token
          cookie and redirects to ``auth.logout_url or "/"``.
        - ``POST {prefix}/auth/session`` (with ``token_cookie``): exempt from
          CSRF and guarded by its own dependencies, the size check first, then
          ``build_admin_dependency(auth)``.
        - ``GET/POST {prefix}/login`` (with ``token_cookie.token_endpoint``): the
          public, CSRF-protected admin login form for bearer-only hosts.

        Raises:
            ValueError: ``token_endpoint="auto"`` finds no ``OAuth2PasswordBearer``
                in ``auth.get_user``'s dependencies.
        """
        from starlette.requests import Request

        from hyperadmin.auth import token_handoff
        from hyperadmin.auth.bridge import build_admin_dependency
        from hyperadmin.views.route import csrf_exempt
        from hyperadmin.views.urls import request_admin_path

        admin_prefix = path.rstrip("/")
        cookie = auth.token_cookie
        cookie_secure = self.settings.cookie_secure

        async def logout_post(request: Request):
            return await token_handoff.bridge_logout_view(
                request,
                cookie=cookie,
                admin_path=request_admin_path(request, admin_prefix),
                logout_url=auth.logout_url,
                cookie_secure=cookie_secure,
            )

        self.router.add_api_route("/logout", logout_post, methods=["POST"], name="admin-logout")
        if cookie is None:
            return

        @csrf_exempt
        async def handoff_post(request: Request):
            return await token_handoff.token_handoff_view(
                request,
                cookie=cookie,
                admin_path=request_admin_path(request, admin_prefix),
                cookie_secure=cookie_secure,
                next_param=auth.next_param,
            )

        self.public_router.add_api_route(
            cookie.handoff_path,
            handoff_post,
            methods=["POST"],
            name="admin-token-handoff",
            dependencies=[
                Depends(token_handoff.reject_oversized_token),
                Depends(build_admin_dependency(auth)),
            ],
        )
        if cookie.token_endpoint is None:
            return
        endpoint = token_handoff.resolve_token_endpoint(cookie.token_endpoint, auth.get_user)
        templates = self.templates
        host_app = self.app

        async def login(request: Request):
            return await token_handoff.bridge_login_view(
                request,
                templates=templates,
                cookie=cookie,
                endpoint=endpoint,
                host_app=host_app,
                admin_path=request_admin_path(request, admin_prefix),
                cookie_secure=cookie_secure,
                next_param=auth.next_param,
            )

        self.public_router.add_api_route(
            "/login", login, methods=["GET", "POST"], name="admin-login"
        )

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
        from hyperadmin.views.urls import request_admin_path

        templates = self.templates
        auth_backend = self.auth_backend
        otp_service = self.otp_service

        # Redirects and template links use the per-request admin path (SDD C.1).
        async def challenge_get(request: Request):
            base = request_admin_path(request, admin_prefix)
            return await mfa_challenge_view(request, templates, base)

        async def verify_post(request: Request):
            base = request_admin_path(request, admin_prefix)
            return await mfa_verify_view(request, templates, auth_backend, otp_service, base)

        async def resend_post(request: Request):
            base = request_admin_path(request, admin_prefix)
            return await mfa_resend_view(request, templates, auth_backend, otp_service, base)

        async def settings_get(request: Request):
            base = request_admin_path(request, admin_prefix)
            return await mfa_settings_view(request, templates, base)

        async def enable_post(request: Request):
            base = request_admin_path(request, admin_prefix)
            return await mfa_enable_view(request, templates, auth_backend, otp_service, base)

        async def disable_post(request: Request):
            base = request_admin_path(request, admin_prefix)
            return await mfa_disable_view(request, templates, auth_backend, otp_service, base)

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

    def _register_realtime_routes(self) -> None:
        """Register the SSE GET route and WebSocket route on the admin router.

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
        registry = self._realtime_registry
        settings = self.realtime

        sse_handler = make_sse_handler(registry, settings)
        self.router.add_api_route(
            "/realtime/sse",
            sse_handler,
            methods=["GET"],
            name="admin-realtime-sse",
        )
        self._register_realtime_ws_route(registry, settings)

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

    def _register_realtime_ws_route(
        self, registry: ConnectionRegistry, settings: RealtimeSettings
    ) -> None:
        """Register the realtime WebSocket route, with its handshake ``Origin`` check.

        In bridge mode the host resolves WebSocket users through
        ``ExternalAuth.websocket_user`` (HTTP dependencies do not run on WebSocket
        scope). Without it no user could ever be admitted, so the route is not
        registered at all; SSE keeps working (SDD B, Edge cases).
        """
        from hyperadmin.views.csrf import make_websocket_origin_check

        ws_auth: Any = self.auth_backend
        if self.auth is not None:
            if self.auth.websocket_user is None:
                logger.info(
                    "HyperAdmin realtime: WebSocket route not registered in bridge mode "
                    "because ExternalAuth.websocket_user is not set; SSE stays available."
                )
                return
            from hyperadmin.auth.bridge import BridgeWebSocketAuth

            ws_auth = BridgeWebSocketAuth(self.auth)
        origin_allowed = make_websocket_origin_check(self.settings.csrf_trusted_origins)
        ws_handler = make_ws_handler(
            registry, settings, ws_auth, origin_allowed, pubsub=self._realtime_pubsub
        )
        # On the admin router, so it lands under the prefix in both mount modes
        # (and inside the namespace in isolated mode).
        self.router.add_websocket_route("/realtime/ws", ws_handler, name="admin-realtime-ws")

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

    def _add_auth_middleware(self, target: FastAPI, admin_prefix: str, *, isolated: bool) -> None:
        """Add session and authentication middleware to ``target``.

        ``target`` is the private sub-app in isolated mode, so neither the session
        nor the auth check ever touches a host request; in router mode it is the
        host app, and ``AuthenticationMiddleware`` matches ``admin_prefix`` on whole
        path segments.

        The session cookie (SDD C.4) is ``settings.session_cookie`` scoped to the
        per-request admin path, and ``AdminSessionMiddleware`` keeps a host
        ``scope["session"]`` intact. Router mode keeps the legacy cookie
        (``session``, ``Path=/``) unless ``session_cookie`` is set explicitly.
        """
        from starlette.requests import Request

        from hyperadmin.auth.middleware import AuthenticationMiddleware
        from hyperadmin.auth.session_middleware import AdminSessionMiddleware
        from hyperadmin.views.urls import request_admin_path

        def admin_path(request: Request) -> str:
            return request_admin_path(request, admin_prefix)

        settings = self.settings
        scoped_cookie = isolated or "session_cookie" in settings.model_fields_set

        target.add_middleware(
            AuthenticationMiddleware,
            auth_backend=self.auth_backend,
            admin_prefix=admin_prefix,
            permission_checker=self.permission_checker,
            isolated=isolated,
            admin_path=admin_path,
        )
        target.add_middleware(
            AdminSessionMiddleware,
            secret_key=settings.secret_key,
            session_cookie=settings.session_cookie if scoped_cookie else "session",
            max_age=settings.session_max_age,
            same_site=settings.session_same_site,
            cookie_secure=settings.cookie_secure,
            admin_path=admin_path if scoped_cookie else None,
        )

    def _add_locale_middleware(self, target: FastAPI) -> None:
        """Add the locale-resolution middleware to ``target``."""
        from hyperadmin.i18n import LocaleMiddleware

        target.add_middleware(LocaleMiddleware, settings=self.settings)

    def _default_storage(self) -> Any:
        """Build the storage ``settings.storage_backend`` selects when no ``storage=`` is passed.

        ``"s3"`` returns an ``S3StorageBackend`` built from the ``aws_*`` settings
        (story #402). ``"local"`` returns ``None``: uploads stay off until the host
        passes a ``FileSystemStorage``, as before.
        """
        if self.settings.storage_backend != "s3":
            return None
        from hyperadmin.uploads.storage import S3StorageBackend

        return S3StorageBackend.from_settings(self.settings)

    def _mount_public_uploads(self, path: str) -> None:
        """Legacy escape hatch: mount the storage directory publicly at ``path`` (SDD C.5).

        Only used when ``settings.public_uploads_path`` is set. Files are
        otherwise served per record behind the admin's permission checks.
        """
        root = storage_root(self.storage)
        if root is None or not root.is_dir():
            logger.warning(
                "public_uploads_path=%r ignored: the storage has no local directory", path
            )
            return
        logger.warning(
            "HyperAdmin serves uploaded files publicly at %r (settings.public_uploads_path), "
            "outside the admin's authentication and permissions. Unset it to serve files "
            "only per record under the admin prefix.",
            path,
        )
        self.app.mount(path, StaticFiles(directory=str(root)), name="uploads")

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
        await self._sync_plugin_permissions(models)

    async def _sync_plugin_permissions(self, models: "list[tuple[str, Any]]") -> None:
        """Sync plugin codenames next to the model ones (plugin-registry SDD).

        Needs a registry with ``sync_codenames`` (``PermissionSyncService``); a
        codename a model already defines is logged and skipped.
        """
        sync_codenames = getattr(self.permission_registry, "sync_codenames", None)
        if not self.plugins.permissions or sync_codenames is None:
            return
        from hyperadmin.auth.permissions import generate_default_permissions

        taken = {
            codename
            for model_name, admin_class in models
            for codename, _ in [
                *generate_default_permissions(model_name),
                *(getattr(admin_class, "permissions", None) or []),
            ]
        }
        await sync_codenames(plugin_permission_rows(self.plugins, taken=taken))

    def _register_permissions_matrix(self) -> None:
        """Register the built-in permission-matrix page (``docs/specs/permission-matrix-ui.md``).

        It edits the built-in ``Group`` / ``GroupPermission`` tables, so it is only
        registered when those are in use: built-in auth, or bridge mode with
        ``settings.register_auth_models=True``. Otherwise there are no groups to
        edit and the page, its nav entry and its codename are left out (the URL
        answers 404), as they are with ``permissions_matrix_enabled=False``.
        """
        if not self.settings.permissions_matrix_enabled or self._auth_mode is None:
            return
        if self._auth_mode == "external" and self.settings.register_auth_models is not True:
            logger.info(
                "HyperAdmin permission matrix not registered: Admin(auth=...) without the "
                "built-in auth models (settings.register_auth_models=True), so there are "
                "no groups to edit."
            )
            return
        from hyperadmin.views.permissions_matrix import PermissionMatrixPage

        self.plugins.register(PermissionMatrixPage(self), admin=self)

    def dispatch_hook(self, hook: str, /, **kwargs: Any) -> None:
        """Fire a plugin lifecycle hook with ``admin=self`` (errors are logged, not raised)."""
        self.plugins.dispatch_hook(hook, admin=self, **kwargs)

    def _apply_plugins(self) -> None:
        """Add plugin pages after the model routes, plugin templates and sidebar entries."""
        from hyperadmin.core.registry import site

        model_slugs = {model.__name__.lower() for model in site._registry}
        self.router.routes.extend(
            build_plugin_routes(
                self.plugins, route_class=self.router.route_class, reserved=model_slugs
            )
        )
        extend_template_loader(self.templates.env, self.plugins)
        self.templates.env.globals["plugin_nav"] = resolve_plugin_nav(self.plugins, self.router)

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

    def _should_register_auth_models(self) -> bool:
        """Whether ``mount()`` registers the built-in auth model admins (SDD B.3).

        ``settings.register_auth_models=None`` (default) means on for
        ``auth_backend=``, off for ``auth=`` and without auth; a bool wins.
        """
        explicit = self.settings.register_auth_models
        if explicit is not None:
            return explicit
        return self._auth_mode == "builtin"

    def _register_auth_models(self) -> None:
        """Auto-register User, Group, Permission in the admin site.

        Called from ``mount()`` when :meth:`_should_register_auth_models` is true.
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

    def _resolve_mount_mode(self, admin_prefix: str) -> bool:
        """Return ``True`` for an isolated sub-app mount, ``False`` for router mode.

        Router mode is the deprecated legacy mode (SDD C.1). Mounting at the root
        always uses it: a ``Mount("/")`` would shadow every host route.
        """
        if self.settings.mount_mode == "router":
            warnings.warn(
                "HyperAdmin mount_mode='router' is deprecated and will be removed in 0.6. "
                "The default isolated mode mounts the admin as a private sub-application; "
                "admin route names then resolve as "
                f"'{self.settings.route_namespace}:<name>'.",
                DeprecationWarning,
                stacklevel=3,
            )
            return False
        if not admin_prefix:
            logger.warning(
                "HyperAdmin mounted at '/': using router mode, because an isolated "
                "sub-application mounted at the root would shadow every host route."
            )
            return False
        return True

    def _make_route_class(self) -> "type[APIRoute]":
        """Build the ``HyperAdminRoute`` class shared by every admin router (SDD B.2)."""
        from hyperadmin.views.route import DEFAULT_API_PREFIXES, make_admin_route_class

        csrf = self._build_csrf_guard()
        auth = self.auth
        if auth is None:
            return make_admin_route_class(self.templates, csrf=csrf)
        # Bridge mode: the route class owns auth-error translation and the
        # token-cookie bridge (SDD B.2, B.4).
        token_cookie = auth.token_cookie
        # A rejected token handoff is an API call from an SPA: always a bare 401,
        # never a browser redirect to a login page (SDD B.4).
        api_prefixes = (
            (*DEFAULT_API_PREFIXES, token_cookie.handoff_path)
            if token_cookie is not None
            else DEFAULT_API_PREFIXES
        )
        return make_admin_route_class(
            self.templates,
            csrf=csrf,
            translate_auth_errors=True,
            api_prefixes=api_prefixes,
            login_url=auth.login_url,
            login_path="/login" if token_cookie and token_cookie.token_endpoint else None,
            next_param=auth.next_param,
            token_cookie=token_cookie.name if token_cookie is not None else None,
            token_scheme=token_cookie.scheme if token_cookie is not None else "Bearer",
        )

    def _protected_dependencies(self) -> "list[params.Depends]":
        """Dependencies the (protected) admin router is included with (SDD B.3).

        In bridge mode the host's ``get_user``, through ``build_admin_dependency``,
        guards every admin route; otherwise there are none.
        """
        if self.auth is None:
            return []
        from hyperadmin.auth.bridge import build_admin_dependency

        return [Depends(build_admin_dependency(self.auth))]

    def _build_csrf_guard(self) -> "CsrfGuard | None":
        """Build the CSRF check and its template globals; ``None`` when CSRF is off."""
        from hyperadmin.views.csrf import CsrfGuard, install_csrf_globals

        mode = self.csrf_mode
        if mode == "off":
            return None
        settings = self.settings
        install_csrf_globals(
            self.templates.env,
            field_name=settings.csrf_field_name,
            header_name=settings.csrf_header_name,
        )
        # Only the count: the settings object also carries secret_key, and an Origin
        # rejection already logs the offending origin together with csrf_trusted_origins.
        logger.info(
            "HyperAdmin CSRF %s; %d trusted origin(s) beyond the request host",
            mode,
            len(settings.csrf_trusted_origins),
        )
        return CsrfGuard(
            settings.secret_key,
            mode=mode,
            cookie_name=settings.csrf_cookie_name,
            header_name=settings.csrf_header_name,
            field_name=settings.csrf_field_name,
            trusted_origins=settings.csrf_trusted_origins,
            cookie_secure=settings.cookie_secure,
        )

    def mount(self, path: str = "/admin") -> None:
        """Mount the admin interface on the host FastAPI application.

        By default (``settings.mount_mode == "isolated"``) the admin is built as a
        private ``FastAPI`` sub-application, without OpenAPI or docs, and attached
        with ``app.mount(path, sub_app, name=settings.route_namespace)`` (SDD C.1):

        - its middleware (locale, session, authentication, the startup guard)
          wraps admin requests only;
        - its static files and realtime WebSocket live under ``path``;
        - its route names are namespaced, e.g. ``hyperadmin:user-list``;
        - it shares the host's ``dependency_overrides`` and ``state``.

        ``mount_mode="router"`` (deprecated) and ``mount("/")`` keep the legacy
        ``include_router`` behaviour.
        """
        admin_prefix = path.rstrip("/")
        isolated = self._resolve_mount_mode(admin_prefix)

        # Every admin route uses HyperAdminRoute (SDD B.2): 403/404/409 render inside
        # the admin layout for people (JSON stays for API callers), and it is the one
        # place for the auth-error translation, token-cookie bridge and CSRF hook.
        # Set before any route is added to the admin router.
        self.router.route_class = self._make_route_class()
        self.public_router.route_class = self.router.route_class

        if self.storage and self.settings.public_uploads_path:
            self._mount_public_uploads(self.settings.public_uploads_path)

        if self.auth_backend:
            self._register_auth_routes(path)
        if self.auth is not None:
            self._register_bridge_routes(path, self.auth)
        if self._should_register_auth_models():
            self._register_auth_models()

        if self.settings.auto_discover:
            self._auto_register_models()

        self._register_locale_route(path)
        self._register_realtime_routes()
        self._register_views()
        self._apply_plugins()
        self.templates.env.globals["admin_prefix"] = admin_prefix
        # Per-request override of the static global (SDD C.1): under a host
        # root_path, "{{ admin_prefix }}/..." links must carry it too.
        from hyperadmin.views.urls import admin_prefix_context

        if admin_prefix_context not in self.templates.context_processors:
            self.templates.context_processors.append(admin_prefix_context)
        self.templates.env.globals["auth_enabled"] = self._auth_mode is not None
        self.templates.env.globals["auth_mode"] = self._auth_mode
        self.templates.env.globals["logout_url"] = (
            self.auth.logout_url if self.auth is not None else None
        )
        self.templates.env.globals["realtime_enabled"] = self.realtime is not None
        self.templates.env.globals["theme"] = self.settings.theme
        self.templates.env.globals["site_title"] = self.settings.site_title
        self.templates.env.globals["site_header"] = self.settings.site_header
        self.templates.env.globals["supported_locales"] = self.settings.supported_locales
        from hyperadmin.i18n import RTL_LOCALES

        self.templates.env.globals["rtl_locales"] = RTL_LOCALES

        if isolated:
            self._mount_isolated(admin_prefix)
        else:
            self._mount_router(admin_prefix)

    def _mount_isolated(self, admin_prefix: str) -> None:
        """Build the private admin sub-app and attach it under ``admin_prefix`` (SDD C.1)."""
        from hyperadmin.views.urls import AdminScopeMiddleware

        sub_app = FastAPI(openapi_url=None, docs_url=None, redoc_url=None)
        # Shared, not copied: host test overrides and dependencies that read
        # request.app.state keep working under the admin prefix.
        sub_app.dependency_overrides = self.app.dependency_overrides
        sub_app.state = self.app.state
        mount_plugin_static(sub_app, self.plugins)
        sub_app.mount("/static", StaticFiles(directory=_STATIC_DIR), name="static")
        sub_app.include_router(
            self.router, tags=["HyperAdmin"], dependencies=self._protected_dependencies()
        )
        sub_app.include_router(self.public_router, tags=["HyperAdmin"])

        # add_middleware prepends, so the last one added runs first:
        # StartupGuard -> AdminScope -> Session -> Authentication -> Locale -> routes.
        self._add_locale_middleware(sub_app)
        if self.auth_backend:
            self._add_auth_middleware(sub_app, admin_prefix, isolated=True)
        sub_app.add_middleware(AdminScopeMiddleware, namespace=self.settings.route_namespace)
        # Every sub-app request is an admin request, hence the "/" prefix.
        sub_app.add_middleware(StartupGuardMiddleware, lifecycle=self._lifecycle, admin_prefix="/")

        self.app.mount(admin_prefix, sub_app, name=self.settings.route_namespace)
        self._asgi_app = sub_app

    def _mount_router(self, admin_prefix: str) -> None:
        """Legacy router mode: admin routes and middleware live on the host app."""
        from hyperadmin.views.urls import AdminScopeMiddleware

        mount_plugin_static(self.app, self.plugins)
        self.app.mount("/static", StaticFiles(directory=_STATIC_DIR), name="static")
        self.app.include_router(
            self.router,
            prefix=admin_prefix,
            tags=["HyperAdmin"],
            dependencies=self._protected_dependencies(),
        )
        self.app.include_router(self.public_router, prefix=admin_prefix, tags=["HyperAdmin"])

        # LocaleMiddleware runs whether or not auth is configured. It must be
        # added before the auth middleware so the chain is
        # SessionMiddleware -> AuthenticationMiddleware -> LocaleMiddleware -> routes.
        self._add_locale_middleware(self.app)

        if self.auth_backend:
            self._add_auth_middleware(self.app, admin_prefix, isolated=False)

        self.app.add_middleware(AdminScopeMiddleware, namespace=None, prefix=admin_prefix)
        # Added last so it is outermost (SDD C.2): the safety net must run before
        # Session/Auth/Locale, so a permission sync it triggers is visible to this
        # same request's own permission checks. One mechanism now, not two — there
        # is no more ``router.on_startup`` append here (Starlette silently ignores
        # on_startup/on_shutdown handlers once a host passes its own ``lifespan=``,
        # and a mounted sub-app never receives lifespan events at all).
        self.app.add_middleware(
            StartupGuardMiddleware, lifecycle=self._lifecycle, admin_prefix=admin_prefix
        )
