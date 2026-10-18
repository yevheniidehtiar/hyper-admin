"""``CsrfGuard``: signed double-submit CSRF wired into ``HyperAdminRoute`` (SDD D.1).

st-v058-byoa-39. The first half drives a real ``Admin`` with a built-in-style
auth backend (CSRF enforced by ``csrf_mode="auto"``) through the story
scenarios; the second half pins the guard's Origin, token and cookie rules on
a minimal admin router built with ``make_admin_route_class(csrf=CsrfGuard(...))``.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from typing import Any

import anyio
import pytest
from fastapi import APIRouter, Depends, FastAPI, Request
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, create_async_engine
from sqlmodel import Field, SQLModel

from hyperadmin import Admin
from hyperadmin.core.csrf import CsrfTokenSigner, resolve_csrf_mode
from hyperadmin.core.registry import site
from hyperadmin.core.settings import HyperAdminSettings
from hyperadmin.views.csrf import CsrfGuard, install_csrf_globals
from hyperadmin.views.route import make_admin_route_class
from tests.conftest import with_csrf

SECRET = "csrf-guard-test-secret-" + "x" * 20
_HX_TOKEN = re.compile(r"hx-headers='\{\"X-CSRF-Token\": \"([^\"]+)\"\}'")
_META_TOKEN = re.compile(r'<meta name="csrf-token" content="([^"]+)">')
_FIELD_TOKEN = re.compile(r'<input type="hidden" name="csrf_token" value="([^"]+)">')


class CsrfOrder(SQLModel, table=True):
    __tablename__ = "csrf_guard_order"  # type: ignore[reportIncompatibleVariableOverride]
    id: int | None = Field(default=None, primary_key=True)
    name: str


@dataclass
class _User:
    id: int = 1
    username: str = "alice"
    is_superuser: bool = True
    is_active: bool = True
    mfa_enabled: bool = False


class _LoggedInBackend:
    """A built-in-style backend whose session always holds a superuser."""

    async def get_current_user(self, request: Any) -> _User:
        return _User()

    async def authenticate(self, username: str, password: str) -> None:
        return None


class _SessionBackend:
    """A built-in-style backend: ``alice``/``secret`` logs in to the session."""

    async def get_current_user(self, request: Any) -> _User | None:
        return _User() if request.session.get("user_id") else None

    async def authenticate(self, username: str, password: str) -> _User | None:
        return _User() if (username, password) == ("alice", "secret") else None

    async def login(self, request: Any, user: _User) -> None:
        request.session["user_id"] = user.id

    async def logout(self, request: Any) -> None:
        request.session.clear()


@pytest.fixture(autouse=True)
def _clean_registry():
    site._registry = {}
    yield
    site._registry = {}


@pytest.fixture
def engine() -> AsyncEngine:
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")

    async def _setup() -> None:
        async with engine.begin() as conn:
            await conn.run_sync(SQLModel.metadata.create_all, tables=[CsrfOrder.__table__])
        async with AsyncSession(engine) as session:
            session.add(CsrfOrder(id=5, name="five"))
            await session.commit()

    anyio.run(_setup)
    return engine


def _order_exists(engine: AsyncEngine, item_id: int) -> bool:
    async def _get() -> bool:
        async with AsyncSession(engine) as session:
            return await session.get(CsrfOrder, item_id) is not None

    return anyio.run(_get)


def _admin_client(
    engine: AsyncEngine,
    *,
    backend: Any = None,
    base_url: str = "http://testserver",
    app: FastAPI | None = None,
    **settings: Any,
) -> TestClient:
    app = app or FastAPI()
    admin = Admin(
        app,
        engine=engine,
        settings=HyperAdminSettings(create_tables=False, secret_key=SECRET, **settings),
        auth_backend=backend,
    )
    site.register(CsrfOrder)
    admin.mount("/admin")
    return TestClient(app, base_url=base_url, follow_redirects=False)


# ── Story scenarios ────────────────────────────────────────────────────────


def test_htmx_delete_without_a_token_is_rejected(engine: AsyncEngine) -> None:
    """
    Scenario: missing token rejected
      Given a logged-in built-in session user
      When  DELETE /admin/order/5 is sent with HX-Request and no X-CSRF-Token
      Then  the response is 403 with X-HyperAdmin-CSRF: failed
      And   order 5 still exists
    """
    # Given
    client = _admin_client(engine, backend=_LoggedInBackend())
    client.get("/admin/csrforder")  # the browser holds a valid cookie

    # When
    response = client.delete("/admin/csrforder/5", headers={"HX-Request": "true"})

    # Then
    assert response.status_code == 403
    assert response.headers["x-hyperadmin-csrf"] == "failed"
    assert response.text == "CSRF token missing or invalid"
    assert _order_exists(engine, 5)


def test_htmx_request_carrying_the_rendered_token_succeeds(engine: AsyncEngine) -> None:
    """
    Scenario: HTMX request carrying the rendered token succeeds
      Given the list page was rendered with body hx-headers containing the token
      When  the delete button issues DELETE /admin/order/5
      Then  the response is 200
      And   order 5 is deleted
    """
    # Given
    client = _admin_client(engine, backend=_LoggedInBackend())
    page = client.get("/admin/csrforder")
    hx_match = _HX_TOKEN.search(page.text)
    meta_match = _META_TOKEN.search(page.text)
    assert hx_match is not None
    assert meta_match is not None
    token = hx_match.group(1)
    assert meta_match.group(1) == token
    assert client.cookies.get("hyperadmin_csrf") == token

    # When
    response = client.delete(
        "/admin/csrforder/5", headers={"HX-Request": "true", "X-CSRF-Token": token}
    )

    # Then
    assert response.status_code == 200
    assert not _order_exists(engine, 5)


def test_cross_site_origin_is_rejected_even_with_a_matching_pair(engine: AsyncEngine) -> None:
    """
    Scenario: cross-site origin rejected
      Given a valid cookie and token pair
      When  POST /admin/order is sent with Origin: https://evil.example
      Then  the response is 403
    """
    # Given
    client = with_csrf(_admin_client(engine, backend=_LoggedInBackend()), SECRET)

    # When
    response = client.post(
        "/admin/csrforder", data={"name": "evil"}, headers={"Origin": "https://evil.example"}
    )

    # Then
    assert response.status_code == 403
    assert response.headers["x-hyperadmin-csrf"] == "failed"


def test_tls_terminating_proxy_does_not_break_csrf(engine: AsyncEngine) -> None:
    """
    Scenario: TLS-terminating proxy does not break CSRF
      Given the app sees scheme http and Host admin.example
      When  POST /admin/order is sent with Origin: https://admin.example and a valid token pair
      Then  the response is not 403
    """
    # Given
    client = with_csrf(
        _admin_client(engine, backend=_LoggedInBackend(), base_url="http://admin.example"),
        SECRET,
    )

    # When
    response = client.post(
        "/admin/csrforder", data={"name": "proxied"}, headers={"Origin": "https://admin.example"}
    )

    # Then
    assert response.status_code == 303


def test_report_mode_allows_and_logs(
    engine: AsyncEngine, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    """
    Scenario: report mode allows
      Given HYPERADMIN_CSRF_MODE=report
      When  POST /admin/order is sent without a token
      Then  the request is processed
      And   a WARNING mentioning csrf is logged
    """
    # Given
    monkeypatch.setenv("HYPERADMIN_CSRF_MODE", "report")
    client = _admin_client(engine, backend=_LoggedInBackend())

    # When
    with caplog.at_level(logging.WARNING, logger="hyperadmin.csrf"):
        response = client.post("/admin/csrforder", data={"name": "reported"})

    # Then
    assert response.status_code == 303
    warnings = [r for r in caplog.records if r.levelno == logging.WARNING]
    assert any("csrf" in r.getMessage() for r in warnings)


def test_csrf_is_off_for_admins_without_auth(engine: AsyncEngine) -> None:
    """
    Scenario: off without auth
      Given Admin() with no auth
      When  POST /admin/order is sent without a token
      Then  the response is not 403
      And   no token is rendered or set as a cookie
    """
    # Given
    client = _admin_client(engine)
    page = client.get("/admin/csrforder")

    # When
    response = client.post("/admin/csrforder", data={"name": "no-auth"})

    # Then
    assert response.status_code == 303
    assert "csrf-token" not in page.text
    assert "hx-headers" not in page.text
    assert "hyperadmin_csrf" not in client.cookies


def test_plain_login_form_post_uses_the_hidden_csrf_field(engine: AsyncEngine) -> None:
    """
    Scenario: plain form post uses the hidden csrf field
      Given the login page rendered a hidden csrf_token input
      When  POST /admin/login is sent with valid credentials and that field
      Then  the response is 302 to /admin/
    """
    # Given
    client = _admin_client(engine, backend=_SessionBackend())
    page = client.get("/admin/login")
    field = _FIELD_TOKEN.search(page.text)
    assert field is not None
    set_cookie = page.headers["set-cookie"]
    assert "hyperadmin_csrf=" in set_cookie
    assert "HttpOnly" in set_cookie
    assert "Path=/admin" in set_cookie
    assert "SameSite=lax" in set_cookie
    assert "Secure" not in set_cookie

    # When
    response = client.post(
        "/admin/login",
        data={"username": "alice", "password": "secret", "csrf_token": field.group(1)},
    )

    # Then
    assert response.status_code == 302
    assert response.headers["location"] == "/admin/"


def test_navbar_locale_switcher_posts_with_its_hidden_csrf_field(engine: AsyncEngine) -> None:
    """
    Scenario: the navbar locale switcher is a plain form carrying the token
      Given a logged-in user on a rendered admin page with the locale switcher
      When  the switcher form is submitted with its hidden csrf_token field
      Then  the locale cookie is set and the browser is redirected
    """
    # Given
    client = _admin_client(engine, backend=_LoggedInBackend())
    page = client.get("/admin/")
    switcher = page.text.split('class="ha-locale-switcher"', 1)[1].split("</form>", 1)[0]
    field = _FIELD_TOKEN.search(switcher)
    assert field is not None

    # When
    response = client.post("/admin/locale", data={"locale": "es", "csrf_token": field.group(1)})

    # Then
    assert response.status_code == 302
    assert "es" in response.headers["set-cookie"]


def test_login_csrf_is_blocked(engine: AsyncEngine) -> None:
    """
    Scenario: login CSRF is blocked
      Given no hyperadmin_csrf cookie in the browser
      When  a cross-site form POSTs /admin/login with attacker credentials
      Then  the response is 403
      And   no session is created
    """
    # Given
    client = _admin_client(engine, backend=_SessionBackend())

    # When
    response = client.post(
        "/admin/login",
        data={"username": "alice", "password": "secret"},
        headers={"Origin": "https://evil.example", "Sec-Fetch-Site": "cross-site"},
    )

    # Then
    assert response.status_code == 403
    assert "session" not in client.cookies


def test_rendered_error_page_sets_the_cookie_its_token_needs(engine: AsyncEngine) -> None:
    """
    Scenario: an admin error page carries a usable token
      Given a logged-in user with no CSRF cookie yet
      When  the browser opens a record that does not exist
      Then  the 404 page in the admin layout renders a token
      And   the response sets the matching hyperadmin_csrf cookie
    """
    # Given
    client = _admin_client(engine, backend=_LoggedInBackend())

    # When
    page = client.get("/admin/csrforder/999", headers={"accept": "text/html"})

    # Then
    assert page.status_code == 404
    match = _META_TOKEN.search(page.text)
    assert match is not None
    assert client.cookies.get("hyperadmin_csrf") == match.group(1)


def test_default_secret_is_refused_when_csrf_is_enforced_without_auth() -> None:
    """
    Scenario: CSRF enforcement needs a real secret key
      Given csrf_mode="enforce", no auth and the default secret_key
      When  Admin() is constructed
      Then  a ValueError names HYPERADMIN_SECRET_KEY
    """
    # Given
    settings = HyperAdminSettings(create_tables=False, csrf_mode="enforce")

    # When / Then
    with pytest.raises(ValueError, match="HYPERADMIN_SECRET_KEY"):
        Admin(FastAPI(), engine=object(), settings=settings)


def test_enforce_mode_protects_an_admin_without_auth(engine: AsyncEngine) -> None:
    """
    Scenario: csrf_mode="enforce" protects an admin without auth
      Given Admin() with no auth and csrf_mode="enforce"
      When  POST /admin/order is sent without a token
      Then  the response is 403
    """
    # Given
    client = _admin_client(engine, csrf_mode="enforce")

    # When
    response = client.post("/admin/csrforder", data={"name": "x"})

    # Then
    assert response.status_code == 403


def _host_login_guard() -> None:
    """A host app-level dependency standing in for the host's own login check."""


@pytest.mark.parametrize("mount_mode", ["router", "isolated"])
def test_auto_mode_enforces_when_the_host_brings_its_own_auth(
    engine: AsyncEngine, mount_mode: str
) -> None:
    """
    Scenario: auto enforces CSRF for a host that guards its app with dependencies
      Given Admin() with no auth_backend on a FastAPI(dependencies=[...]) host
            and the default csrf_mode
      When  POST /admin/order is sent without a token
      Then  the response is 403 with X-HyperAdmin-CSRF: failed
    """
    # Given
    app = FastAPI(dependencies=[Depends(_host_login_guard)])
    client = _admin_client(engine, app=app, mount_mode=mount_mode)
    client.get("/admin/csrforder")  # the browser holds a valid cookie

    # When
    response = client.post("/admin/csrforder", data={"name": "cross-site"})

    # Then
    assert response.status_code == 403
    assert response.headers["X-HyperAdmin-CSRF"] == "failed"


def test_cookie_secure_setting_marks_the_csrf_cookie_secure_over_http(
    engine: AsyncEngine,
) -> None:
    """
    Scenario: cookie_secure=True behind an untrusted TLS proxy
      Given built-in auth and HyperAdminSettings(cookie_secure=True)
      When  an admin page is opened over plain http
      Then  the hyperadmin_csrf cookie is issued with Secure
    """
    # Given
    client = _admin_client(engine, backend=_LoggedInBackend(), cookie_secure=True)

    # When
    response = client.get("/admin/csrforder")

    # Then
    cookie = response.headers["set-cookie"]
    assert cookie.startswith("hyperadmin_csrf=")
    assert "Secure" in cookie


def test_startup_logs_the_effective_trusted_origins(
    engine: AsyncEngine, caplog: pytest.LogCaptureFixture
) -> None:
    """
    Scenario: the admin logs its CSRF mode and trusted-origin count at mount
      Given csrf_trusted_origins=["https://ops.example"] and auth configured
      When  the admin is mounted
      Then  an INFO record gives the mode and one trusted origin
      And   the origin itself is not logged (settings also carry secret_key)
    """
    # Given / When
    with caplog.at_level(logging.INFO, logger="hyperadmin"):
        _admin_client(
            engine,
            backend=_LoggedInBackend(),
            csrf_trusted_origins=["https://ops.example"],
        )

    # Then
    messages = [r.getMessage() for r in caplog.records]
    assert "HyperAdmin CSRF enforce; 1 trusted origin(s) beyond the request host" in messages
    assert not any(re.search(r"\bops\.example\b", m) for m in messages)


# ── Guard rules on a minimal admin router ──────────────────────────────────


def _guard_client(
    *,
    base_url: str = "http://testserver",
    seen: dict[str, Any] | None = None,
    **guard: Any,
) -> TestClient:
    csrf = CsrfGuard(SECRET, **guard)
    router = APIRouter(route_class=make_admin_route_class(csrf=csrf))
    captured = seen if seen is not None else {}

    @router.get("/page")
    async def page() -> dict[str, str]:
        return {"ok": "page"}

    @router.post("/upload")
    async def upload(request: Request) -> dict[str, Any]:
        form = await request.form()
        upload_file = form["file"]
        assert not isinstance(upload_file, str)
        captured["file"] = await upload_file.read()
        captured["title"] = form.get("title")
        return {"ok": "upload"}

    @router.post("/json")
    async def json_endpoint() -> dict[str, str]:
        return {"ok": "json"}

    sub_app = FastAPI()
    sub_app.include_router(router)
    host = FastAPI()
    host.mount("/admin", sub_app)
    return TestClient(host, base_url=base_url, follow_redirects=False)


_FILE = {"file": ("notes.bin", bytes(range(256)) * 64, "application/octet-stream")}


def test_multipart_upload_with_the_header_token_reaches_the_endpoint_intact() -> None:
    """
    Scenario: multipart with header token
      Given a multipart upload with the header token
      When  it is posted
      Then  the endpoint receives the file intact
    """
    # Given
    seen: dict[str, Any] = {}
    client = with_csrf(_guard_client(seen=seen), SECRET)

    # When
    response = client.post("/admin/upload", data={"title": "t"}, files=_FILE)

    # Then
    assert response.status_code == 200
    assert seen["file"] == _FILE["file"][1]
    assert seen["title"] == "t"


def test_multipart_upload_with_the_body_token_reaches_the_endpoint_intact() -> None:
    """
    Scenario: multipart with the token in the body
      Given a multipart upload carrying csrf_token as a form field and no header
      When  it is posted
      Then  the check reads the field and the endpoint still receives the file intact
    """
    # Given
    seen: dict[str, Any] = {}
    client = _guard_client(seen=seen)
    token = CsrfTokenSigner(SECRET).issue()
    client.cookies.set("hyperadmin_csrf", token)

    # When
    response = client.post("/admin/upload", data={"title": "t", "csrf_token": token}, files=_FILE)

    # Then
    assert response.status_code == 200
    assert seen["file"] == _FILE["file"][1]


def test_json_body_without_a_header_token_is_rejected() -> None:
    """
    Scenario: a non-form body must carry the header token
      Given a valid cookie and a JSON body with no X-CSRF-Token header
      When  it is posted
      Then  the response is 403
    """
    # Given
    client = _guard_client()
    client.cookies.set("hyperadmin_csrf", CsrfTokenSigner(SECRET).issue())

    # When
    response = client.post("/admin/json", json={"csrf_token": "ignored"})

    # Then
    assert response.status_code == 403


def test_a_token_that_does_not_match_the_cookie_is_rejected() -> None:
    """
    Scenario: two valid but different tokens do not pair
      Given a valid cookie and a different validly signed header token
      When  it is posted
      Then  the response is 403
    """
    # Given
    signer = CsrfTokenSigner(SECRET)
    client = _guard_client()
    client.cookies.set("hyperadmin_csrf", signer.issue())

    # When
    response = client.post("/admin/json", headers={"X-CSRF-Token": signer.issue()})

    # Then
    assert response.status_code == 403


@pytest.mark.parametrize(
    ("headers", "status"),
    [
        ({"Sec-Fetch-Site": "cross-site"}, 403),
        ({"Sec-Fetch-Site": "same-origin", "Origin": "https://elsewhere.example"}, 200),
        ({"Sec-Fetch-Site": "same-site", "Origin": "https://elsewhere.example"}, 403),
        ({"Origin": "null"}, 403),
        ({"Origin": "http://testserver"}, 200),
        ({"Origin": "http://testserver:80"}, 200),
        ({"Origin": "http://testserver:8080"}, 403),
        ({"Origin": "https://testserver"}, 200),
        ({"Origin": "https://ops.example"}, 200),
        ({"Origin": "https://ops.example/"}, 200),
        ({"Origin": "https://proxy.example", "X-Forwarded-Host": "proxy.example, inner"}, 200),
        ({"Origin": "ftp://testserver"}, 403),
    ],
)
def test_origin_rules(headers: dict[str, str], status: int) -> None:
    """
    Scenario: the fetch-metadata and Origin rules on an http request
      Given a valid cookie and token pair on http://testserver
      And   csrf_trusted_origins=["https://ops.example"]
      When  a POST carries the given Sec-Fetch-Site / Origin / X-Forwarded-Host
      Then  the response status follows the D.1 Origin rules
    """
    # Given
    client = with_csrf(_guard_client(trusted_origins=["https://ops.example"]), SECRET)

    # When
    response = client.post("/admin/json", headers=headers)

    # Then
    assert response.status_code == status


def test_an_http_origin_on_an_https_request_is_rejected() -> None:
    """
    Scenario: a scheme downgrade is never accepted
      Given a valid cookie and token pair on https://testserver
      When  a POST carries Origin: http://testserver
      Then  the response is 403
    """
    # Given
    client = with_csrf(_guard_client(base_url="https://testserver"), SECRET)

    # When
    response = client.post("/admin/json", headers={"Origin": "http://testserver"})

    # Then
    assert response.status_code == 403


def test_origin_failure_log_names_origin_host_and_the_setting(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """
    Scenario: an Origin failure explains itself
      Given a valid cookie and token pair
      When  a POST carries Origin: https://evil.example
      Then  a WARNING names the observed Origin, the Host and csrf_trusted_origins
    """
    # Given
    client = with_csrf(_guard_client(), SECRET)

    # When
    with caplog.at_level(logging.WARNING, logger="hyperadmin.csrf"):
        client.post("/admin/json", headers={"Origin": "https://evil.example"})

    # Then
    message = " ".join(r.getMessage() for r in caplog.records if r.levelno == logging.WARNING)
    assert re.search(r"\bhttps://evil\.example\b", message)
    assert "testserver" in message
    assert "csrf_trusted_origins" in message


def test_a_valid_cookie_is_kept_and_an_invalid_one_is_replaced() -> None:
    """
    Scenario: tokens are per cookie, not per request
      Given a browser holding a valid cookie, and one holding a forged cookie
      When  each opens an admin page
      Then  the valid cookie is not re-issued
      And   the forged cookie is replaced by a validly signed one
    """
    # Given
    valid = CsrfTokenSigner(SECRET).issue()
    keeper = _guard_client()
    keeper.cookies.set("hyperadmin_csrf", valid)
    forger = _guard_client()
    forger.cookies.set("hyperadmin_csrf", "forged.token")

    # When
    kept = keeper.get("/admin/page")
    replaced = forger.get("/admin/page")

    # Then
    assert "set-cookie" not in kept.headers
    assert "hyperadmin_csrf=" in replaced.headers["set-cookie"]
    issued = replaced.headers["set-cookie"].split(";", 1)[0].removeprefix("hyperadmin_csrf=")
    assert CsrfTokenSigner(SECRET).is_valid(issued)


@pytest.mark.parametrize(
    ("origin", "cookie_secure", "secure"),
    [
        ("https://testserver", "auto", True),
        ("http://testserver", "auto", False),
        ("http://testserver", True, True),
        ("https://testserver", False, False),
    ],
)
def test_cookie_secure_follows_the_setting(origin: str, cookie_secure: Any, secure: bool) -> None:
    """
    Scenario: the CSRF cookie's Secure flag follows cookie_secure
      Given cookie_secure is auto, True or False
      When  an admin page is opened over http or https
      Then  Secure is set from the request scheme (auto) or forced
    """
    # Given
    client = _guard_client(base_url=origin, cookie_secure=cookie_secure)

    # When
    response = client.get("/admin/page")

    # Then
    assert ("Secure" in response.headers["set-cookie"]) is secure


def test_report_mode_lets_a_cross_site_request_through(caplog: pytest.LogCaptureFixture) -> None:
    """
    Scenario: report mode never blocks
      Given CsrfGuard in report mode
      When  a cross-site POST without a token arrives
      Then  the endpoint runs and a WARNING mentions csrf
    """
    # Given
    client = _guard_client(mode="report")

    # When
    with caplog.at_level(logging.WARNING, logger="hyperadmin.csrf"):
        response = client.post("/admin/json", headers={"Sec-Fetch-Site": "cross-site"})

    # Then
    assert response.status_code == 200
    assert any("csrf" in r.getMessage() for r in caplog.records)


def test_guard_refuses_a_mode_that_does_not_check() -> None:
    """
    Scenario: the guard only runs in enforce or report mode
      Given mode="off"
      When  a CsrfGuard is built
      Then  a ValueError is raised
    """
    with pytest.raises(ValueError, match="enforce' or 'report"):
        CsrfGuard(SECRET, mode="off")


@pytest.mark.parametrize(
    ("mode", "auth_enabled", "effective"),
    [
        ("auto", True, "enforce"),
        ("auto", False, "off"),
        ("report", True, "report"),
        ("enforce", False, "enforce"),
        ("off", True, "off"),
    ],
)
def test_resolve_csrf_mode(mode: Any, auth_enabled: bool, effective: str) -> None:
    """
    Scenario: auto enforces whenever any auth is configured
      Given a csrf_mode and whether auth is configured
      When  the mode is resolved
      Then  auto becomes enforce with auth and off without; explicit modes stay
    """
    assert resolve_csrf_mode(mode, auth_enabled=auth_enabled) == effective


def test_template_globals_render_nothing_without_a_token() -> None:
    """
    Scenario: a template rendered outside a CSRF-checked request
      Given the csrf globals installed and a request with no token
      When  csrf_token() and csrf_input() are rendered
      Then  both render empty strings
    """
    # Given
    from jinja2 import Environment

    env = Environment(autoescape=True)
    install_csrf_globals(env, field_name="csrf_token", header_name="X-CSRF-Token")

    class _State:
        pass

    class _Request:
        state = _State()

    # When
    rendered = env.from_string("[{{ csrf_token() }}][{{ csrf_input() }}]").render(
        request=_Request()
    )

    # Then
    assert rendered == "[][]"
