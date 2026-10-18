"""Unit tests for the admin-scoped session cookie (BYOA SDD C.4).

Story: ``.meta/epics/epic-v058-bring-your-own-app/stories/
featauth-admin-scoped-session-cookie-via-adminsessionmiddlew.md`` (st-v058-byoa-36),
including its review amendments: ``cookie_secure``, per-request cookie paths
under a host ``root_path``, the locale switcher's cookie path and open-redirect
fix, and ``AuthenticationMiddleware``'s ``login_url``.
"""

from __future__ import annotations

import base64
import json
import logging
import warnings
from typing import TYPE_CHECKING, Any

import pytest
from fastapi import FastAPI, Request
from httpx import ASGITransport, AsyncClient
from pydantic import ValidationError
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlmodel import SQLModel
from starlette.middleware.sessions import SessionMiddleware
from starlette.testclient import TestClient

from hyperadmin.auth.backend import hash_password
from hyperadmin.auth.middleware import AuthenticationMiddleware
from hyperadmin.auth.models import User
from hyperadmin.auth.session import SessionAuthBackend
from hyperadmin.auth.session_middleware import AdminSessionMiddleware, rewrite_cookie_header
from hyperadmin.core.app import Admin
from hyperadmin.core.registry import site
from hyperadmin.core.settings import HyperAdminSettings, resolve_cookie_secure

if TYPE_CHECKING:
    from collections.abc import AsyncIterator
    from pathlib import Path

    from sqlalchemy.ext.asyncio import AsyncEngine
    from starlette.types import Message, Receive, Scope, Send


pytestmark = pytest.mark.anyio

_CREDENTIALS = {"username": "admin", "password": "password123"}


@pytest.fixture(autouse=True)
def _clean_registry():
    """``mount()`` auto-registers the auth models; keep the global site untouched."""
    saved = dict(site._registry)
    yield
    site._registry = saved


@pytest.fixture
async def engine(tmp_path: Path) -> AsyncIterator[AsyncEngine]:
    db_engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'session.db'}")
    async with db_engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.create_all)
    async with AsyncSession(db_engine) as session:
        session.add(
            User(
                username="admin",
                email="admin@example.com",
                password_hash=hash_password("password123"),
                is_superuser=True,
            )
        )
        await session.commit()
    yield db_engine
    await db_engine.dispose()


def _admin(app: FastAPI, engine: AsyncEngine, **overrides: Any) -> Admin:
    # These scenarios are about the session cookie, not CSRF (covered in
    # test_csrf_guard.py), so the CSRF check is off unless a test opts in.
    overrides.setdefault("csrf_mode", "off")
    settings = HyperAdminSettings(create_tables=False, secret_key="test-secret-key", **overrides)
    return Admin(
        app, engine=engine, settings=settings, auth_backend=SessionAuthBackend(engine=engine)
    )


def _client(app: FastAPI, base_url: str = "http://test", **kwargs: Any) -> AsyncClient:
    return AsyncClient(transport=ASGITransport(app=app, **kwargs), base_url=base_url)


def _set_cookies(response: Any, name: str) -> list[str]:
    """Return the ``Set-Cookie`` values for cookie ``name``, lower-cased."""
    return [
        value.lower()
        for value in response.headers.get_list("set-cookie")
        if value.startswith(f"{name}=")
    ]


def _raw_set_cookies(response: Any, name: str) -> list[str]:
    """Return the ``Set-Cookie`` values for cookie ``name`` with their case intact.

    ``_set_cookies`` lower-cases for attribute checks, which garbles the base64
    payload; decode payloads from these instead.
    """
    return [v for v in response.headers.get_list("set-cookie") if v.startswith(f"{name}=")]


def _cookie_payload(cookie: str) -> dict[str, Any]:
    """Decode the JSON payload of a signed Starlette session ``Set-Cookie``."""
    signed = cookie.split(";", 1)[0].split("=", 1)[1]
    data = signed.split(".", 1)[0]
    return json.loads(base64.b64decode(data + "=" * (-len(data) % 4)))


def _attributes(cookie: str) -> set[str]:
    return {part.strip() for part in cookie.split(";")[1:]}


async def _login(client: AsyncClient, url: str = "/admin/login") -> Any:
    return await client.post(url, data=_CREDENTIALS, follow_redirects=False)


# ---------------------------------------------------------------------------
# Story scenarios
# ---------------------------------------------------------------------------


async def test_cookie_scoped_to_prefix(engine: AsyncEngine) -> None:
    """
    Scenario: cookie scoped to prefix
      Given built-in auth at /admin
      When  a user logs in
      Then  Set-Cookie names hyperadmin_session with Path=/admin
    """
    # Given
    app = FastAPI()
    _admin(app, engine).mount("/admin")

    async with _client(app) as client:
        # When
        resp = await _login(client)

    # Then
    assert resp.status_code == 302
    cookies = _set_cookies(resp, "hyperadmin_session")
    assert len(cookies) == 1
    attributes = _attributes(cookies[0])
    assert "path=/admin" in attributes
    assert {"httponly", "samesite=lax"} <= attributes
    assert "max-age=1209600" in attributes
    assert _set_cookies(resp, "session") == []


async def test_host_session_untouched(engine: AsyncEngine) -> None:
    """
    Scenario: host session untouched
      Given the host SessionMiddleware with cookie 'session'
      When  the user logs in to /admin
      Then  the host session cookie is unchanged
    """
    # Given
    app = FastAPI()

    @app.post("/cart")
    async def add_to_cart(request: Request) -> dict[str, Any]:
        request.session["cart"] = ["apple"]
        return dict(request.session)

    @app.get("/cart")
    async def read_cart(request: Request) -> dict[str, Any]:
        return dict(request.session)

    _admin(app, engine).mount("/admin")
    app.add_middleware(SessionMiddleware, secret_key="host-secret", session_cookie="session")

    async with _client(app) as client:
        await client.post("/cart")
        host_cookie = client.cookies.get("session")

        # When
        resp = await _login(client)
        dashboard = await client.get("/admin/")
        host_view = await client.get("/cart")

    # Then the admin session lives in its own cookie, and the host cookie still
    # carries only the host's data (no admin user_id serialised into it).
    assert resp.status_code == 302
    assert _set_cookies(resp, "hyperadmin_session")
    assert dashboard.status_code == 200
    assert host_view.json() == {"cart": ["apple"]}
    assert host_cookie is not None
    # The login response never rewrites the host cookie with admin data...
    for cookie in _raw_set_cookies(resp, "session"):
        assert "user_id" not in _cookie_payload(cookie)
    # ...and the browser's host cookie still decodes to the host's own data. Compare the
    # payload, not the raw value: older Starlette re-signs the host cookie on every
    # response, so its timestamp segment changes when the requests cross a second.
    current = client.cookies.get("session")
    assert current is not None
    assert _cookie_payload(f"session={current}") == {"cart": ["apple"]}
    assert _cookie_payload(f"session={host_cookie}") == {"cart": ["apple"]}


async def test_testclient_login_over_plain_http(engine: AsyncEngine) -> None:
    """
    Scenario: TestClient login works with cookie_secure="auto"
      Given built-in auth at /admin and the default cookie_secure="auto"
      When  a user logs in through Starlette's TestClient (http://testserver)
      Then  the session cookie is not Secure
      And   the next admin request is authenticated
    """
    # Given
    app = FastAPI()
    _admin(app, engine).mount("/admin")

    with TestClient(app) as client:
        # When
        resp = client.post("/admin/login", data=_CREDENTIALS, follow_redirects=False)
        dashboard = client.get("/admin/", follow_redirects=False)

    # Then
    assert "secure" not in _attributes(_set_cookies(resp, "hyperadmin_session")[0])
    # And
    assert dashboard.status_code == 200


async def test_secure_cookie_on_https_with_auto(engine: AsyncEngine) -> None:
    """
    Scenario: cookie_secure="auto" marks the cookie Secure over https
      Given built-in auth at /admin and cookie_secure="auto"
      When  a user logs in over https
      Then  the session cookie is Secure
    """
    # Given
    app = FastAPI()
    _admin(app, engine).mount("/admin")

    async with _client(app, base_url="https://test") as client:
        # When
        resp = await _login(client)

    # Then
    assert "secure" in _attributes(_set_cookies(resp, "hyperadmin_session")[0])


@pytest.mark.parametrize(
    ("cookie_secure", "url", "expected"),
    [(True, "http://test", True), (False, "https://test", False)],
)
async def test_explicit_cookie_secure_wins(
    engine: AsyncEngine, cookie_secure: bool, url: str, expected: bool
) -> None:
    """
    Scenario: an explicit cookie_secure overrides the request scheme
      Given built-in auth at /admin and cookie_secure set to a bool
      When  a user logs in
      Then  the session cookie's Secure flag follows the setting
    """
    # Given
    app = FastAPI()
    _admin(app, engine, cookie_secure=cookie_secure).mount("/admin")

    async with _client(app, base_url=url) as client:
        # When
        resp = await _login(client)

    # Then
    assert ("secure" in _attributes(_set_cookies(resp, "hyperadmin_session")[0])) is expected


async def test_cookie_path_follows_host_root_path(engine: AsyncEngine) -> None:
    """
    Scenario: the cookie path follows the host root_path
      Given built-in auth at /admin
      And   the host is served under root_path="/api"
      When  a user logs in at /api/admin/login
      Then  Set-Cookie hyperadmin_session has Path=/api/admin
      And   the next admin request is authenticated
    """
    # Given
    app = FastAPI()
    _admin(app, engine).mount("/admin")

    async with _client(app, root_path="/api") as client:
        # When
        resp = await _login(client, "/api/admin/login")
        dashboard = await client.get("/api/admin/", follow_redirects=False)

    # Then
    assert "path=/api/admin" in _attributes(_set_cookies(resp, "hyperadmin_session")[0])
    # And
    assert dashboard.status_code == 200


async def test_custom_session_cookie_settings(engine: AsyncEngine) -> None:
    """
    Scenario: session cookie name, lifetime and SameSite come from settings
      Given session_cookie="bo_sid", session_max_age=600, session_same_site="strict"
      When  a user logs in to /backoffice
      Then  Set-Cookie names bo_sid with Path=/backoffice, Max-Age=600, SameSite=strict
    """
    # Given
    app = FastAPI()
    _admin(
        app, engine, session_cookie="bo_sid", session_max_age=600, session_same_site="strict"
    ).mount("/backoffice")

    async with _client(app) as client:
        # When
        resp = await _login(client, "/backoffice/login")

    # Then
    attributes = _attributes(_set_cookies(resp, "bo_sid")[0])
    assert {"path=/backoffice", "max-age=600", "samesite=strict"} <= attributes


async def test_logout_expires_the_scoped_cookie(engine: AsyncEngine) -> None:
    """
    Scenario: logout clears the admin cookie on the admin path
      Given a logged-in user, built-in auth at /admin
      When  the user logs out
      Then  hyperadmin_session is expired with Path=/admin
      And   the next admin request redirects to the login page
    """
    # Given
    app = FastAPI()
    _admin(app, engine).mount("/admin")

    async with _client(app) as client:
        await _login(client)
        # When
        resp = await client.post("/admin/logout", follow_redirects=False)
        after = await client.get("/admin/", follow_redirects=False)

    # Then
    cookie = _set_cookies(resp, "hyperadmin_session")[0]
    assert "path=/admin" in _attributes(cookie)
    assert "expires=thu, 01 jan 1970 00:00:00 gmt" in _attributes(cookie)
    # And
    assert after.headers["location"] == "/admin/login"


async def test_static_asset_never_rescopes_the_session_cookie(engine: AsyncEngine) -> None:
    """
    Scenario: a static asset response keeps the cookie on the admin path
      Given a logged-in user, built-in auth at /admin
      When  the browser fetches a stylesheet under /admin/static/css/
      Then  every hyperadmin_session Set-Cookie on that response has Path=/admin
    """
    # Given
    app = FastAPI()
    _admin(app, engine).mount("/admin")

    async with _client(app) as client:
        await _login(client)
        # When
        resp = await client.get("/admin/static/css/_accessibility.css")

    # Then
    assert resp.status_code == 200
    for cookie in _set_cookies(resp, "hyperadmin_session"):
        assert "path=/admin" in _attributes(cookie)


async def test_cookie_path_resolved_before_inner_routing() -> None:
    """
    Scenario: inner routing cannot change the session cookie path
      Given an AdminSessionMiddleware whose admin path is the scope root_path "/admin"
      When  an inner mount extends root_path to "/admin/static" and writes the session
      Then  the session Set-Cookie has Path=/admin
    """
    # Given
    scope = _scope(root_path="/admin", path="/admin/static/x.css")
    sent: list[Message] = []

    async def app(scope: Scope, receive: Receive, send: Send) -> None:
        scope["root_path"] += "/static"
        scope["session"]["user_id"] = 1
        await send({"type": "http.response.start", "status": 200, "headers": []})
        await send({"type": "http.response.body", "body": b""})

    async def send(message: Message) -> None:
        sent.append(message)

    middleware = AdminSessionMiddleware(
        app, secret_key="k", admin_path=lambda request: request.scope["root_path"]
    )

    # When
    await middleware(scope, _noop_receive, send)

    # Then
    cookie = dict(sent[0]["headers"])[b"set-cookie"].decode().lower()
    assert "path=/admin" in _attributes(cookie)


def _bare_auth_app(engine: AsyncEngine, *, isolated: bool) -> FastAPI:
    """A host app with ``AuthenticationMiddleware`` added directly, no ``admin_path``."""
    app = FastAPI()

    @app.get("/admin/")
    @app.get("/")
    async def dashboard() -> dict[str, str]:
        return {"ok": "yes"}

    app.add_middleware(
        AuthenticationMiddleware,
        auth_backend=SessionAuthBackend(engine=engine),
        admin_prefix="/admin",
        isolated=isolated,
    )
    app.add_middleware(SessionMiddleware, secret_key="k")
    return app


async def test_auth_middleware_router_fallback_uses_admin_prefix(engine: AsyncEngine) -> None:
    """
    Scenario: without admin_path, router-mode redirects use the static prefix
      Given AuthenticationMiddleware added directly with admin_prefix="/admin"
      When  an anonymous GET reaches /admin/
      Then  the response redirects to /admin/login
    """
    # Given
    app = _bare_auth_app(engine, isolated=False)

    async with _client(app) as client:
        # When
        resp = await client.get("/admin/", follow_redirects=False)

    # Then
    assert resp.status_code == 302
    assert resp.headers["location"] == "/admin/login"


async def test_auth_middleware_isolated_fallback_uses_root_path(engine: AsyncEngine) -> None:
    """
    Scenario: without admin_path, isolated redirects use the scope root_path
      Given AuthenticationMiddleware added directly with isolated=True
      When  an anonymous GET arrives under root_path "/sub"
      Then  the response redirects to /sub/login
    """
    # Given
    app = _bare_auth_app(engine, isolated=True)

    async with _client(app, root_path="/sub") as client:
        # When
        resp = await client.get("/", follow_redirects=False)

    # Then
    assert resp.status_code == 302
    assert resp.headers["location"] == "/sub/login"


async def test_router_mode_keeps_legacy_cookie(engine: AsyncEngine) -> None:
    """
    Scenario: router mode keeps the legacy session cookie
      Given built-in auth at /admin in (deprecated) router mode
      When  a user logs in
      Then  Set-Cookie names session with Path=/
    """
    # Given
    app = FastAPI()
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", DeprecationWarning)
        _admin(app, engine, mount_mode="router").mount("/admin")

    async with _client(app) as client:
        # When
        resp = await _login(client)

    # Then
    assert "path=/" in _attributes(_set_cookies(resp, "session")[0])
    assert _set_cookies(resp, "hyperadmin_session") == []


async def test_router_mode_with_explicit_session_cookie(engine: AsyncEngine) -> None:
    """
    Scenario: router mode scopes an explicitly named cookie to the admin path
      Given router mode, session_cookie="hyperadmin_session" set explicitly
      And   the host is served under root_path="/api"
      When  a user logs in at /api/admin/login
      Then  Set-Cookie names hyperadmin_session with Path=/api/admin
    """
    # Given
    app = FastAPI()
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", DeprecationWarning)
        _admin(app, engine, mount_mode="router", session_cookie="hyperadmin_session").mount(
            "/admin"
        )

    async with _client(app, root_path="/api") as client:
        # When
        resp = await _login(client, "/api/admin/login")

    # Then
    assert "path=/api/admin" in _attributes(_set_cookies(resp, "hyperadmin_session")[0])


async def test_router_mode_login_url_follows_host_root_path(engine: AsyncEngine) -> None:
    """
    Scenario: router mode's login redirect follows the host root_path
      Given built-in auth at /admin in router mode
      And   the host is served under root_path="/api"
      When  an anonymous user requests /api/admin/
      Then  it is redirected to /api/admin/login
    """
    # Given
    app = FastAPI()
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", DeprecationWarning)
        _admin(app, engine, mount_mode="router").mount("/admin")

    async with _client(app, root_path="/api") as client:
        # When
        resp = await client.get("/api/admin/", follow_redirects=False)

    # Then
    assert resp.status_code == 302
    assert resp.headers["location"] == "/api/admin/login"


# ---------------------------------------------------------------------------
# Locale switcher (views/locale.py): cookie path and open-redirect fix
# ---------------------------------------------------------------------------


async def test_locale_cookie_follows_custom_mount(engine: AsyncEngine) -> None:
    """
    Scenario: the locale cookie is scoped to a custom mount prefix
      Given the admin mounted with mount("/backoffice")
      When  a user switches the locale without a Referer
      Then  Set-Cookie hyperadmin_locale has Path=/backoffice
      And   the response redirects to /backoffice/
      And   the next admin request is rendered in that locale
    """
    # Given
    app = FastAPI()
    Admin(app, engine=engine, settings=HyperAdminSettings(create_tables=False)).mount("/backoffice")

    async with _client(app) as client:
        # When
        resp = await client.post(
            "/backoffice/locale", data={"locale": "es"}, follow_redirects=False
        )
        dashboard = await client.get("/backoffice/")

    # Then
    assert "path=/backoffice" in _attributes(_set_cookies(resp, "hyperadmin_locale")[0])
    # And
    assert resp.headers["location"] == "/backoffice/"
    # And
    assert dashboard.headers.get("content-language") == "es"


async def test_locale_cookie_follows_host_root_path(engine: AsyncEngine) -> None:
    """
    Scenario: the locale cookie follows the host root_path over https
      Given the admin at /admin, the host under root_path="/api", served over https
      When  a user switches the locale
      Then  Set-Cookie hyperadmin_locale has Path=/api/admin and is Secure
    """
    # Given
    app = FastAPI()
    Admin(app, engine=engine, settings=HyperAdminSettings(create_tables=False)).mount("/admin")

    async with _client(app, base_url="https://test", root_path="/api") as client:
        # When
        resp = await client.post("/api/admin/locale", data={"locale": "es"}, follow_redirects=False)

    # Then
    attributes = _attributes(_set_cookies(resp, "hyperadmin_locale")[0])
    assert {"path=/api/admin", "secure"} <= attributes
    assert resp.headers["location"] == "/api/admin/"


@pytest.mark.parametrize(
    "referer",
    [
        "https://evil.example/admin/users/",
        "//evil.example/admin/users/",
        "/\\evil.example/admin/",
        "http://test/health",
        "http://test/administrator",
        "javascript:alert(1)",
        "ftp://test/admin/",
    ],
)
async def test_locale_ignores_unsafe_referer(engine: AsyncEngine, referer: str) -> None:
    """
    Scenario: an off-site or non-admin Referer falls back to the dashboard
      Given the admin at /admin
      When  a user switches the locale with an off-site or non-admin Referer
      Then  the response redirects to /admin/
    """
    # Given
    app = FastAPI()
    Admin(app, engine=engine, settings=HyperAdminSettings(create_tables=False)).mount("/admin")

    async with _client(app) as client:
        # When
        resp = await client.post(
            "/admin/locale",
            data={"locale": "es"},
            headers={"Referer": referer},
            follow_redirects=False,
        )

    # Then
    assert resp.status_code == 302
    assert resp.headers["location"] == "/admin/"


async def test_locale_at_root_ignores_double_slash_referer_path(engine: AsyncEngine) -> None:
    """
    Scenario: a same-origin Referer with a "//" path never becomes a redirect target
      Given the admin mounted at "/" (router mode, empty admin path)
      When  a user switches the locale with Referer http://test//evil.example/
      Then  the response redirects to / and the locale cookie has Path=/
    """
    # Given
    app = FastAPI()
    Admin(app, engine=engine, settings=HyperAdminSettings(create_tables=False)).mount("/")

    async with _client(app) as client:
        # When
        resp = await client.post(
            "/locale",
            data={"locale": "es"},
            headers={"Referer": "http://test//evil.example/"},
            follow_redirects=False,
        )

    # Then
    assert resp.headers["location"] == "/"
    assert "path=/" in _attributes(_set_cookies(resp, "hyperadmin_locale")[0])


@pytest.mark.parametrize(
    ("referer", "expected"),
    [
        ("http://test/admin/users/?page=2", "/admin/users/?page=2"),
        ("http://test/admin", "/admin"),
        ("/admin/users/", "/admin/users/"),
    ],
)
async def test_locale_follows_same_origin_admin_referer(
    engine: AsyncEngine, referer: str, expected: str
) -> None:
    """
    Scenario: a same-origin admin Referer is followed
      Given the admin at /admin
      When  a user switches the locale from a same-origin admin page
      Then  the response redirects back to that page (as a relative URL)
    """
    # Given
    app = FastAPI()
    Admin(app, engine=engine, settings=HyperAdminSettings(create_tables=False)).mount("/admin")

    async with _client(app) as client:
        # When
        resp = await client.post(
            "/admin/locale",
            data={"locale": "es"},
            headers={"Referer": referer},
            follow_redirects=False,
        )

    # Then
    assert resp.headers["location"] == expected


# ---------------------------------------------------------------------------
# AdminSessionMiddleware in isolation
# ---------------------------------------------------------------------------


def _scope(**overrides: Any) -> dict[str, Any]:
    scope: dict[str, Any] = {
        "type": "http",
        "scheme": "http",
        "method": "GET",
        "path": "/",
        "raw_path": b"/",
        "root_path": "",
        "query_string": b"",
        "headers": [],
        "server": ("test", 80),
    }
    scope.update(overrides)
    return scope


async def _noop_receive() -> Message:
    return {"type": "http.request", "body": b"", "more_body": False}


async def test_non_http_scopes_pass_through() -> None:
    """
    Scenario: lifespan scopes bypass the admin session
      Given an AdminSessionMiddleware
      When  a lifespan scope arrives
      Then  it reaches the app with no session set
    """
    # Given
    seen: list[Scope] = []

    async def app(scope: Scope, receive: Receive, send: Send) -> None:
        seen.append(dict(scope))

    middleware = AdminSessionMiddleware(app, secret_key="k")

    # When
    await middleware({"type": "lifespan"}, _noop_receive, _noop_send)

    # Then
    assert seen == [{"type": "lifespan"}]


async def _noop_send(message: Message) -> None:
    return None


async def test_websocket_scope_restores_host_session() -> None:
    """
    Scenario: a websocket sees the admin session, then the host's is restored
      Given a scope already carrying a host session
      When  a websocket passes through AdminSessionMiddleware
      Then  the app sees an empty admin session
      And   the host session is back on the scope afterwards
    """
    # Given
    host_session = {"cart": 1}
    scope = _scope(type="websocket", scheme="ws", session=host_session)
    seen: list[Any] = []

    async def app(scope: Scope, receive: Receive, send: Send) -> None:
        seen.append(dict(scope["session"]))

    # When
    await AdminSessionMiddleware(app, secret_key="k")(scope, _noop_receive, _noop_send)

    # Then
    assert seen == [{}]
    # And
    assert scope["session"] is host_session


async def test_websocket_scope_with_admin_path_reaches_the_app() -> None:
    """
    Scenario: a websocket under a scoped admin cookie is not rejected
      Given an AdminSessionMiddleware scoped to the per-request admin path
      When  a websocket scope passes through it
      Then  the app runs with the admin session
    """
    # Given
    seen: list[Any] = []

    async def app(scope: Scope, receive: Receive, send: Send) -> None:
        seen.append(dict(scope["session"]))

    middleware = AdminSessionMiddleware(
        app, secret_key="k", admin_path=lambda request: request.scope["root_path"]
    )

    # When
    await middleware(_scope(type="websocket", scheme="ws"), _noop_receive, _noop_send)

    # Then
    assert seen == [{}]


async def test_scope_without_host_session_stays_without_one() -> None:
    """
    Scenario: no host session means none is left behind
      Given a scope with no host session
      When  a request writes to the admin session
      Then  the cookie path falls back to "/" for an empty admin path
      And   the scope carries no session afterwards
    """
    # Given
    scope = _scope()
    sent: list[Message] = []

    async def app(scope: Scope, receive: Receive, send: Send) -> None:
        scope["session"]["user_id"] = 1
        await send({"type": "http.response.start", "status": 200, "headers": []})
        await send({"type": "http.response.body", "body": b""})

    async def send(message: Message) -> None:
        sent.append(message)

    middleware = AdminSessionMiddleware(app, secret_key="k", admin_path=lambda request: "")

    # When
    await middleware(scope, _noop_receive, send)

    # Then
    cookie = dict(sent[0]["headers"])[b"set-cookie"].decode().lower()
    assert "path=/" in _attributes(cookie)
    # And
    assert "session" not in scope


@pytest.mark.parametrize(
    ("cookie_secure", "scheme", "origin", "warns"),
    [
        ("auto", "http", "https://admin.example", True),
        ("auto", "http", "http://admin.example", False),
        ("auto", "https", "https://admin.example", False),
        (True, "http", "https://admin.example", False),
    ],
)
async def test_warns_once_behind_untrusted_tls_proxy(
    caplog: pytest.LogCaptureFixture,
    cookie_secure: Any,
    scheme: str,
    origin: str,
    warns: bool,
) -> None:
    """
    Scenario: an https Origin over plain http logs a one-time warning
      Given cookie_secure="auto"
      When  two requests arrive over http with Origin: https://...
      Then  exactly one WARNING recommends HYPERADMIN_COOKIE_SECURE=true
    """

    # Given
    async def app(scope: Scope, receive: Receive, send: Send) -> None:
        return None

    middleware = AdminSessionMiddleware(app, secret_key="k", cookie_secure=cookie_secure)
    headers = [(b"origin", origin.encode())]

    # When
    with caplog.at_level(logging.WARNING, logger="hyperadmin"):
        for _ in range(2):
            await middleware(_scope(scheme=scheme, headers=headers), _noop_receive, _noop_send)

    # Then
    messages = [r.message for r in caplog.records if "HYPERADMIN_COOKIE_SECURE" in r.message]
    assert len(messages) == (1 if warns else 0)


def test_rewrite_cookie_header_replaces_path_and_secure() -> None:
    """
    Scenario: the Set-Cookie rewrite swaps the path and the Secure flag
      Given a Set-Cookie value with path=/ and secure
      When  it is rewritten for /admin without Secure
      Then  the path is /admin and secure is gone
    """
    # Given
    value = "hyperadmin_session=abc; path=/; Max-Age=60; httponly; samesite=lax; secure"

    # When
    rewritten = rewrite_cookie_header(value, path="/admin", secure=False)

    # Then
    assert rewritten == "hyperadmin_session=abc; path=/admin; Max-Age=60; httponly; samesite=lax"


# ---------------------------------------------------------------------------
# Settings
# ---------------------------------------------------------------------------


def test_session_cookie_settings_defaults() -> None:
    """
    Scenario: admin cookie settings have safe defaults
      Given no admin cookie settings
      When  HyperAdminSettings is built
      Then  the defaults are hyperadmin_session, 14 days, lax and "auto"
    """
    # Given / When
    settings = HyperAdminSettings()

    # Then
    assert settings.session_cookie == "hyperadmin_session"
    assert settings.session_max_age == 1_209_600
    assert settings.session_same_site == "lax"
    assert settings.cookie_secure == "auto"


@pytest.mark.parametrize(("raw", "expected"), [("true", True), ("false", False), ("auto", "auto")])
def test_cookie_secure_from_env(monkeypatch: pytest.MonkeyPatch, raw: str, expected: Any) -> None:
    """
    Scenario: HYPERADMIN_COOKIE_SECURE accepts true, false and auto
      Given HYPERADMIN_COOKIE_SECURE is set
      When  HyperAdminSettings is built
      Then  cookie_secure is the matching bool or "auto"
    """
    # Given
    monkeypatch.setenv("HYPERADMIN_COOKIE_SECURE", raw)

    # When
    settings = HyperAdminSettings()

    # Then
    assert settings.cookie_secure == expected


def test_invalid_session_same_site_is_rejected() -> None:
    """
    Scenario: an unknown SameSite value is rejected
      Given session_same_site="sometimes"
      When  HyperAdminSettings is built
      Then  a ValidationError is raised
    """
    with pytest.raises(ValidationError):
        HyperAdminSettings(session_same_site="sometimes")  # type: ignore[arg-type]


@pytest.mark.parametrize(
    ("setting", "scheme", "expected"),
    [
        ("auto", "https", True),
        ("auto", "HTTPS", True),
        ("auto", "wss", True),
        ("auto", "http", False),
        (True, "http", True),
        (False, "https", False),
    ],
)
def test_resolve_cookie_secure(setting: Any, scheme: str, expected: bool) -> None:
    """
    Scenario: cookie_secure resolves against the request scheme
      Given a cookie_secure setting and a request scheme
      When  resolve_cookie_secure is called
      Then  "auto" follows the scheme and a bool is used as-is
    """
    assert resolve_cookie_secure(setting, scheme) is expected
