"""Unit tests for the isolated sub-application mount (BYOA SDD C.1).

Story: ``.meta/epics/epic-v058-bring-your-own-app/stories/
featcore-isolated-sub-application-mount.md`` (st-v058-byoa-35).
"""

from __future__ import annotations

import logging
import warnings
from typing import TYPE_CHECKING, Any

import pytest
from fastapi import Depends, FastAPI, Request
from fastapi.staticfiles import StaticFiles
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlmodel import Field, SQLModel
from starlette.routing import NoMatchFound

from hyperadmin.auth.backend import hash_password
from hyperadmin.auth.models import User
from hyperadmin.auth.otp import PARTIAL_AUTH_SESSION_KEY
from hyperadmin.auth.permissions import ModelPermissionChecker, PermissionSyncService
from hyperadmin.auth.session import SessionAuthBackend
from hyperadmin.core.app import Admin
from hyperadmin.core.model import ModelAdmin
from hyperadmin.core.registry import site
from hyperadmin.core.settings import HyperAdminSettings
from hyperadmin.realtime import RealtimeSettings
from hyperadmin.views.urls import AdminScopeMiddleware, admin_base_path
from tests.conftest import with_csrf

if TYPE_CHECKING:
    from collections.abc import AsyncIterator
    from pathlib import Path

    from sqlalchemy.ext.asyncio import AsyncEngine


pytestmark = pytest.mark.anyio


class MountWidget(SQLModel, table=True):
    __tablename__ = "isolated_mount_widgets"

    id: int | None = Field(default=None, primary_key=True)
    name: str = Field(default="")


@pytest.fixture(autouse=True)
def _clean_registry():
    saved = dict(site._registry)
    site._registry.pop(MountWidget, None)
    site.register(MountWidget, admin_class=type("MountWidgetAdmin", (ModelAdmin,), {}))
    yield
    site._registry = saved


@pytest.fixture
async def engine(tmp_path: Path) -> AsyncIterator[AsyncEngine]:
    db_engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'mount.db'}")
    async with db_engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.create_all)
    yield db_engine
    await db_engine.dispose()


async def _seed_superuser(engine: AsyncEngine) -> None:
    async with AsyncSession(engine) as session:
        session.add(
            User(
                username="admin",
                email="admin@example.com",
                password_hash=hash_password("password123"),
                is_superuser=True,
            )
        )
        await session.commit()


def _settings(**overrides: Any) -> HyperAdminSettings:
    return HyperAdminSettings(create_tables=False, secret_key="test-secret-key", **overrides)


def _host_app() -> FastAPI:
    app = FastAPI()

    @app.get("/health")
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/administrator")
    async def administrator() -> dict[str, str]:
        return {"page": "host"}

    return app


def _auth_admin(app: FastAPI, engine: AsyncEngine, **settings: Any) -> Admin:
    return Admin(
        app,
        engine=engine,
        settings=_settings(**settings),
        auth_backend=SessionAuthBackend(engine=engine),
        permission_checker=ModelPermissionChecker(engine=engine),
        permission_registry=PermissionSyncService(engine=engine),
    )


def _client(app: FastAPI, **kwargs: Any) -> AsyncClient:
    """A client carrying a valid CSRF pair for the ``_settings()`` secret (SDD D.1)."""
    client = AsyncClient(transport=ASGITransport(app=app, **kwargs), base_url="http://test")
    return with_csrf(client, "test-secret-key")


async def _login(client: AsyncClient) -> None:
    resp = await client.post("/admin/login", data={"username": "admin", "password": "password123"})
    assert resp.status_code in (200, 302)


# ---------------------------------------------------------------------------
# Story scenarios
# ---------------------------------------------------------------------------


async def test_host_routes_untouched(engine: AsyncEngine) -> None:
    """
    Scenario: host routes untouched
      Given GET /health on the host and HyperAdmin (with auth) mounted at /admin
      When  it is requested
      Then  there is no Content-Language header
      And   no admin session cookie is set
    """
    # Given
    app = _host_app()
    _auth_admin(app, engine).mount("/admin")

    # When
    async with _client(app) as client:
        resp = await client.get("/health")
        admin_resp = await client.get("/admin/login")

    # Then
    assert resp.status_code == 200
    assert "content-language" not in resp.headers
    assert "set-cookie" not in resp.headers
    # ...while the admin itself still negotiates a locale.
    assert admin_resp.headers["content-language"] == "en"


async def test_host_static_keeps_working(engine: AsyncEngine, tmp_path: Path) -> None:
    """
    Scenario: host static keeps working
      Given the host mounts /static named "static" before Admin(app).mount("/admin")
      When  the host's /static/app.css and the admin dashboard are requested
      Then  /static/app.css returns the host file
      And   the dashboard's stylesheet is served from /admin/static
    """
    # Given
    host_static = tmp_path / "host-static"
    host_static.mkdir()
    (host_static / "app.css").write_text("body { color: hotpink; }")
    app = _host_app()
    app.mount("/static", StaticFiles(directory=str(host_static)), name="static")
    Admin(app, engine=engine, settings=_settings()).mount("/admin")

    # When
    async with _client(app) as client:
        host_css = await client.get("/static/app.css")
        dashboard = await client.get("/admin/")
        admin_css = await client.get("/admin/static/css/hyperadmin.css")

    # Then
    assert host_css.status_code == 200
    assert "hotpink" in host_css.text
    assert dashboard.status_code == 200
    assert 'href="http://test/admin/static/css/hyperadmin.css"' in dashboard.text
    assert admin_css.status_code == 200


async def test_segment_safe_prefix_in_router_mode(engine: AsyncEngine) -> None:
    """
    Scenario: segment-safe prefix
      Given auth at /admin in router mode
      When  GET /administrator is requested
      Then  no redirect to /admin/login occurs
    """
    # Given
    app = _host_app()
    with pytest.warns(DeprecationWarning, match="mount_mode=.router."):
        _auth_admin(app, engine, mount_mode="router").mount("/admin")

    # When
    async with _client(app) as client:
        resp = await client.get("/administrator", follow_redirects=False)
        admin_resp = await client.get("/admin/", follow_redirects=False)

    # Then
    assert resp.status_code == 200
    assert resp.json() == {"page": "host"}
    # ...while a real admin path is still protected.
    assert admin_resp.status_code == 302
    assert admin_resp.headers["location"] == "/admin/login"


async def test_segment_safe_prefix_in_isolated_mode(engine: AsyncEngine) -> None:
    """
    Scenario: /administrator is not an admin path in isolated mode either
      Given auth at /admin in isolated mode
      When  GET /administrator is requested
      Then  the host route answers and no redirect to /admin/login occurs
    """
    # Given
    app = _host_app()
    _auth_admin(app, engine).mount("/admin")

    # When
    async with _client(app) as client:
        resp = await client.get("/administrator", follow_redirects=False)

    # Then
    assert resp.status_code == 200
    assert resp.json() == {"page": "host"}


async def test_not_in_host_openapi(engine: AsyncEngine) -> None:
    """
    Scenario: not in host OpenAPI
      Given isolated mode
      When  GET /openapi.json is requested
      Then  no path starts with /admin
    """
    # Given
    app = _host_app()
    Admin(app, engine=engine, settings=_settings()).mount("/admin")

    # When
    async with _client(app) as client:
        resp = await client.get("/openapi.json")
        sub_openapi = await client.get("/admin/openapi.json")
        sub_docs = await client.get("/admin/docs")

    # Then
    paths = resp.json()["paths"]
    assert "/health" in paths
    assert not [path for path in paths if path == "/admin" or path.startswith("/admin/")]
    # The private sub-app publishes no schema or docs of its own.
    assert sub_openapi.status_code == 404
    assert sub_docs.status_code == 404


async def test_router_mode_legacy(engine: AsyncEngine) -> None:
    """
    Scenario: router mode legacy
      Given mount_mode='router'
      When  the admin is mounted
      Then  a DeprecationWarning is emitted
      And   routes use un-namespaced names
    """
    # Given
    app = FastAPI()
    admin = Admin(app, engine=engine, settings=_settings(mount_mode="router"))

    # When
    with pytest.warns(DeprecationWarning, match="mount_mode='router'"):
        admin.mount("/admin")

    # Then
    assert app.url_path_for("mountwidget-list") == "/admin/mountwidget"
    assert app.url_path_for("static", path="/css/hyperadmin.css") == "/static/css/hyperadmin.css"
    assert admin.asgi_app is None


async def test_isolated_mode_namespaces_route_names(engine: AsyncEngine) -> None:
    """
    Scenario: isolated mode namespaces admin route names
      Given the default (isolated) mount mode
      When  the admin is mounted at /admin
      Then  admin routes resolve only as "hyperadmin:<name>"
      And   no DeprecationWarning is emitted
    """
    # Given
    app = FastAPI()
    admin = Admin(app, engine=engine, settings=_settings())

    # When
    with warnings.catch_warnings():
        warnings.simplefilter("error", DeprecationWarning)
        admin.mount("/admin")

    # Then
    assert app.url_path_for("hyperadmin:mountwidget-list") == "/admin/mountwidget"
    assert (
        app.url_path_for("hyperadmin:static", path="/css/hyperadmin.css")
        == "/admin/static/css/hyperadmin.css"
    )
    with pytest.raises(NoMatchFound):
        app.url_path_for("mountwidget-list")
    assert isinstance(admin.asgi_app, FastAPI)


async def test_custom_route_namespace(engine: AsyncEngine) -> None:
    """
    Scenario: the route namespace follows settings.route_namespace
      Given route_namespace="backoffice"
      When  the admin is mounted at /backoffice
      Then  admin routes resolve as "backoffice:<name>"
    """
    # Given
    app = FastAPI()
    admin = Admin(app, engine=engine, settings=_settings(route_namespace="backoffice"))

    # When
    admin.mount("/backoffice")

    # Then
    assert app.url_path_for("backoffice:mountwidget-list") == "/backoffice/mountwidget"


async def test_route_namespace_rejects_a_colon() -> None:
    """
    Scenario: a route namespace containing ':' is rejected
      Given route_namespace="a:b"
      When  the settings are built
      Then  a validation error is raised
    """
    with pytest.raises(ValueError, match="route_namespace"):
        HyperAdminSettings(route_namespace="a:b")


async def test_mount_at_root_forces_router_mode(
    engine: AsyncEngine, caplog: pytest.LogCaptureFixture
) -> None:
    """
    Scenario: mount('/') forces router mode
      Given the default (isolated) mount mode
      When  the admin is mounted at "/"
      Then  a warning explains why router mode is used
      And   routes use un-namespaced names
    """
    # Given
    app = FastAPI()
    admin = Admin(app, engine=engine, settings=_settings())

    # When
    with caplog.at_level(logging.WARNING, logger="hyperadmin"):
        admin.mount("/")

    # Then
    assert "router mode" in caplog.text
    assert app.url_path_for("mountwidget-list") == "/mountwidget"
    assert admin.asgi_app is None


async def test_mount_defaults_to_admin_prefix(engine: AsyncEngine) -> None:
    """
    Scenario: mount() without a path uses /admin
      Given an Admin
      When  mount() is called with no argument
      Then  the dashboard is served at /admin/
    """
    # Given
    app = FastAPI()
    admin = Admin(app, engine=engine, settings=_settings())

    # When
    admin.mount()

    # Then
    async with _client(app) as client:
        resp = await client.get("/admin/")
    assert resp.status_code == 200


# ---------------------------------------------------------------------------
# Review amendments: shared host objects
# ---------------------------------------------------------------------------


def get_user() -> str:
    return "real-user"


async def test_host_dependency_override_applies_under_admin(engine: AsyncEngine) -> None:
    """
    Scenario: a host override of get_user applies under /admin
      Given a host that overrides get_user via app.dependency_overrides
      And   an admin-side route that depends on get_user
      When  that route is requested under /admin
      Then  the host's override is used
    """
    # Given
    app = FastAPI()
    admin = Admin(app, engine=engine, settings=_settings())
    admin.mount("/admin")
    assert admin.asgi_app is not None

    @admin.asgi_app.get("/whoami")
    async def whoami(user: str = Depends(get_user)) -> dict[str, str]:
        return {"user": user}

    app.dependency_overrides[get_user] = lambda: "test-user"

    # When
    async with _client(app) as client:
        resp = await client.get("/admin/whoami")

    # Then
    assert resp.json() == {"user": "test-user"}


async def test_host_get_db_reading_app_state_works_under_admin(engine: AsyncEngine) -> None:
    """
    Scenario: a host get_db(request) that reads request.app.state works
      Given a host that stores its sessionmaker on app.state
      And   an admin-side route that depends on a get_db(request) reading it
      When  that route is requested under /admin
      Then  the host's sessionmaker is found
    """
    # Given
    app = FastAPI()
    admin = Admin(app, engine=engine, settings=_settings())
    admin.mount("/admin")
    assert admin.asgi_app is not None
    app.state.sessionmaker = "host-sessionmaker"

    def get_db(request: Request) -> str:
        return request.app.state.sessionmaker

    @admin.asgi_app.get("/db")
    async def db(session: str = Depends(get_db)) -> dict[str, str]:
        return {"db": session}

    # When
    async with _client(app) as client:
        resp = await client.get("/admin/db")

    # Then
    assert resp.json() == {"db": "host-sessionmaker"}


# ---------------------------------------------------------------------------
# URL resolution, admin path and middleware inside the sub-app
# ---------------------------------------------------------------------------


async def test_create_redirect_resolves_through_the_namespace(engine: AsyncEngine) -> None:
    """
    Scenario: a successful create redirects to the namespaced detail URL
      Given the admin mounted in isolated mode
      When  a new MountWidget is POSTed
      Then  the response redirects to /admin/mountwidget/1
    """
    # Given
    app = FastAPI()
    Admin(app, engine=engine, settings=_settings()).mount("/admin")

    # When
    async with _client(app) as client:
        resp = await client.post(
            "/admin/mountwidget", data={"name": "first"}, follow_redirects=False
        )

    # Then
    assert resp.status_code == 303
    assert resp.headers["location"] == "http://test/admin/mountwidget/1"


async def test_admin_base_path_in_both_modes(engine: AsyncEngine) -> None:
    """
    Scenario: the per-request admin path is known in both mount modes
      Given an admin route that reports admin_base_path(request)
      When  it is requested in isolated mode and in router mode
      Then  both report /admin
    """
    seen: dict[str, str] = {}

    def _build(mode: str) -> FastAPI:
        app = FastAPI()
        admin = Admin(app, engine=engine, settings=_settings(mount_mode=mode))

        async def probe(request: Request) -> dict[str, str]:
            seen[mode] = admin_base_path(request)
            return {}

        admin.router.add_api_route("/probe", probe, methods=["GET"])
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", DeprecationWarning)
            admin.mount("/admin")
        return app

    # When
    for mode in ("isolated", "router"):
        async with _client(_build(mode)) as client:
            assert (await client.get("/admin/probe")).status_code == 200

    # Then
    assert seen == {"isolated": "/admin", "router": "/admin"}


async def test_router_mode_does_not_mark_host_requests(engine: AsyncEngine) -> None:
    """
    Scenario: router mode only tags admin requests with admin routing data
      Given router mode at /admin and a host route /administrator
      When  the host route is requested
      Then  its scope carries no hyperadmin routing data
    """
    # Given
    app = FastAPI()
    seen: dict[str, Any] = {}

    @app.get("/administrator")
    async def administrator(request: Request) -> dict[str, str]:
        seen["scope"] = request.scope.get("hyperadmin")
        return {}

    with pytest.warns(DeprecationWarning, match="mount_mode=.router."):
        Admin(app, engine=engine, settings=_settings(mount_mode="router")).mount("/admin")

    # When
    async with _client(app) as client:
        await client.get("/administrator")

    # Then
    assert seen == {"scope": None}


async def test_unauthenticated_redirect_follows_host_root_path(engine: AsyncEngine) -> None:
    """
    Scenario: the login redirect follows the host root_path in isolated mode
      Given a host served under root_path="/api" with auth at /admin
      When  an anonymous client requests /api/admin/
      Then  it is redirected to /api/admin/login
    """
    # Given
    app = FastAPI()
    _auth_admin(app, engine).mount("/admin")

    # When
    async with _client(app, root_path="/api") as client:
        resp = await client.get("/api/admin/", follow_redirects=False)

    # Then
    assert resp.status_code == 302
    assert resp.headers["location"] == "/api/admin/login"


async def test_login_and_dashboard_in_isolated_mode(engine: AsyncEngine) -> None:
    """
    Scenario: built-in login works in isolated mode
      Given a superuser and auth at /admin in isolated mode
      When  the user logs in and requests /admin/
      Then  the dashboard returns 200
      And   the admin static files stay public
    """
    # Given
    await _seed_superuser(engine)
    app = FastAPI()
    _auth_admin(app, engine).mount("/admin")

    async with _client(app) as client:
        anonymous_css = await client.get("/admin/static/css/hyperadmin.css")
        # When
        await _login(client)
        resp = await client.get("/admin/")

    # Then
    assert anonymous_css.status_code == 200
    assert resp.status_code == 200


async def test_mfa_partial_auth_redirect_uses_admin_path(engine: AsyncEngine) -> None:
    """
    Scenario: a mid-MFA user is sent to the challenge under the admin path
      Given a session carrying an MFA partial-auth marker, in isolated mode
      And   the host is served under root_path="/api"
      When  the user requests /api/admin/
      Then  the response redirects to /api/admin/mfa/challenge
    """
    # Given
    app = FastAPI()
    admin = _auth_admin(app, engine)
    admin.mount("/admin")
    assert admin.asgi_app is not None

    # "/login/..." is a public suffix, so this probe runs for an anonymous user.
    @admin.asgi_app.get("/login/_partial")
    async def partial(request: Request) -> dict[str, str]:
        request.session[PARTIAL_AUTH_SESSION_KEY] = {"stage": "mfa_pending", "user_id": 1}
        return {}

    async with _client(app, root_path="/api") as client:
        await client.get("/api/admin/login/_partial")
        # When
        resp = await client.get("/api/admin/", follow_redirects=False)

    # Then
    assert resp.status_code == 302
    assert resp.headers["location"] == "/api/admin/mfa/challenge"


async def test_realtime_websocket_moves_under_the_prefix(engine: AsyncEngine) -> None:
    """
    Scenario: the realtime WebSocket moves under the admin prefix
      Given realtime enabled and the admin mounted at /admin in isolated mode
      When  the WebSocket route is resolved
      Then  it lives at /admin/realtime/ws inside the admin namespace
    """
    # Given
    app = FastAPI()
    admin = Admin(app, engine=engine, settings=_settings(), realtime=RealtimeSettings())

    # When
    admin.mount("/admin")

    # Then
    assert app.url_path_for("hyperadmin:admin-realtime-ws") == "/admin/realtime/ws"


async def test_admin_scope_middleware_ignores_lifespan_scopes() -> None:
    """
    Scenario: lifespan events pass through the admin scope tagger untouched
      Given an AdminScopeMiddleware
      When  a lifespan scope passes through it
      Then  the scope carries no hyperadmin routing data
      And   the downstream app still receives it
    """
    # Given
    seen: list[dict[str, Any]] = []

    async def downstream(scope: Any, receive: Any, send: Any) -> None:
        seen.append(scope)

    middleware = AdminScopeMiddleware(downstream, namespace="hyperadmin")
    scope: dict[str, Any] = {"type": "lifespan"}

    # When
    await middleware(scope, None, None)

    # Then
    assert seen == [{"type": "lifespan"}]


# ---------------------------------------------------------------------------
# Per-request admin path under a host root_path (SDD C.1, security review)
# ---------------------------------------------------------------------------


async def test_successful_login_redirect_follows_host_root_path(engine: AsyncEngine) -> None:
    """
    Scenario: a successful login redirects to the dashboard under the host root_path
      Given a superuser, auth at /admin in isolated mode
      And   the host is served under root_path="/api"
      When  the user posts valid credentials to /api/admin/login
      Then  the response redirects to /api/admin/
    """
    # Given
    await _seed_superuser(engine)
    app = FastAPI()
    _auth_admin(app, engine).mount("/admin")

    async with _client(app, root_path="/api") as client:
        # When
        resp = await client.post(
            "/api/admin/login",
            data={"username": "admin", "password": "password123"},
            follow_redirects=False,
        )

    # Then
    assert resp.status_code == 302
    assert resp.headers["location"] == "/api/admin/"


async def test_logout_redirect_follows_host_root_path(engine: AsyncEngine) -> None:
    """
    Scenario: logout redirects to the login page under the host root_path
      Given a logged-in superuser, auth at /admin in isolated mode
      And   the host is served under root_path="/api"
      When  the user posts to /api/admin/logout
      Then  the response redirects to /api/admin/login
    """
    # Given
    await _seed_superuser(engine)
    app = FastAPI()
    _auth_admin(app, engine).mount("/admin")

    async with _client(app, root_path="/api") as client:
        await client.post("/api/admin/login", data={"username": "admin", "password": "password123"})
        # When
        resp = await client.post("/api/admin/logout", follow_redirects=False)

    # Then
    assert resp.status_code == 302
    assert resp.headers["location"] == "/api/admin/login"


async def test_template_links_follow_host_root_path(engine: AsyncEngine) -> None:
    """
    Scenario: admin template links use the per-request admin path
      Given a superuser, auth at /admin in isolated mode
      And   the host is served under root_path="/api"
      When  the login page and the dashboard are rendered
      Then  the login form posts to /api/admin/login
      And   the navbar brand links to /api/admin/
    """
    # Given
    await _seed_superuser(engine)
    app = FastAPI()
    _auth_admin(app, engine).mount("/admin")

    async with _client(app, root_path="/api") as client:
        # When
        login_page = await client.get("/api/admin/login")
        await client.post("/api/admin/login", data={"username": "admin", "password": "password123"})
        dashboard = await client.get("/api/admin/")

    # Then
    assert 'action="/api/admin/login"' in login_page.text
    assert 'href="/api/admin/"' in dashboard.text


async def test_router_mode_login_redirect_follows_host_root_path(engine: AsyncEngine) -> None:
    """
    Scenario: a router-mode login redirects under the host root_path
      Given a superuser, auth at /admin in router mode
      And   the host is served under root_path="/api"
      When  the user posts valid credentials to /api/admin/login
      Then  the response redirects to /api/admin/
    """
    # Given
    await _seed_superuser(engine)
    app = FastAPI()
    with pytest.warns(DeprecationWarning, match="mount_mode=.router."):
        _auth_admin(app, engine, mount_mode="router").mount("/admin")

    async with _client(app, root_path="/api") as client:
        # When
        resp = await client.post(
            "/api/admin/login",
            data={"username": "admin", "password": "password123"},
            follow_redirects=False,
        )

    # Then
    assert resp.status_code == 302
    assert resp.headers["location"] == "/api/admin/"


async def test_mfa_challenge_redirect_follows_host_root_path(engine: AsyncEngine) -> None:
    """
    Scenario: MFA routes build their URLs from the per-request admin path
      Given auth with an OTP service at /admin in isolated mode
      And   the host is served under root_path="/api"
      When  an anonymous client requests /api/admin/mfa/challenge
      Then  it is redirected to /api/admin/login
    """
    # Given
    from hyperadmin.auth.otp import EmailOTPService

    class _NullSender:
        async def send(self, *args: Any, **kwargs: Any) -> None:
            return None

    app = FastAPI()
    admin = Admin(
        app,
        engine=engine,
        settings=_settings(),
        auth_backend=SessionAuthBackend(engine=engine),
        permission_checker=ModelPermissionChecker(engine=engine),
        permission_registry=PermissionSyncService(engine=engine),
        otp_service=EmailOTPService(email_sender=_NullSender()),
    )
    admin.mount("/admin")

    async with _client(app, root_path="/api") as client:
        # When
        resp = await client.get("/api/admin/mfa/challenge", follow_redirects=False)

    # Then
    assert resp.status_code == 302
    assert resp.headers["location"] == "/api/admin/login"
