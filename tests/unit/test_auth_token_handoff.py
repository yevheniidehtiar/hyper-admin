"""Token handoff, bearer login form, JWT-exp cookie lifetime and bridge logout (SDD B.4).

Story st-v058-byoa-41. Covers the five story scenarios plus the review
amendments: the handoff is guarded by the host dependency and exempt from CSRF,
the opt-in admin login form for bearer hosts, ``Max-Age = min(max_age, exp - now)``,
clearing a rejected cookie token, strict ``next`` validation, and a bearer-only
host reaching ``/admin`` in a plain browser.
"""

from __future__ import annotations

import base64
import json
import re
import threading
import time
from collections.abc import Iterator
from http.server import BaseHTTPRequestHandler, HTTPServer
from typing import Any
from urllib.parse import parse_qs

import pytest
from fastapi import Depends, FastAPI, Form, Header, HTTPException
from fastapi.security import OAuth2PasswordBearer
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import create_async_engine
from sqlmodel import Field, SQLModel

from hyperadmin import Admin
from hyperadmin.adapters.sqlmodel import SQLModelAdapter
from hyperadmin.auth.bridge import ExternalAuth, TokenCookie
from hyperadmin.auth.token_handoff import (
    MAX_TOKEN_BYTES,
    cookie_max_age,
    discover_token_url,
    jwt_expiry,
    request_token,
    safe_next,
)
from hyperadmin.core.model import ModelAdmin
from hyperadmin.core.registry import site
from hyperadmin.core.settings import HyperAdminSettings

_SECRET = "handoff-test-secret"
_FIELD_TOKEN = re.compile(r'name="csrf_token" value="([^"]+)"')


class ThHostUser(SQLModel, table=True):
    __tablename__ = "th_host_user"

    id: int | None = Field(default=None, primary_key=True)
    username: str = ""
    is_staff: bool = False
    is_superuser: bool = False


class ThHostUserAdmin(ModelAdmin):
    adapter_class = SQLModelAdapter


STAFF = ThHostUser(id=1, username="ada", is_staff=True)
CUSTOMER = ThHostUser(id=3, username="cus")
_TOKENS: dict[str, ThHostUser] = {"staff-token": STAFF, "customer-token": CUSTOMER}


def get_current_user(authorization: str | None = Header(default=None)) -> ThHostUser | None:
    """A host ``get_user`` resolving ``Bearer <token>``; ``None`` when anonymous or unknown."""
    if not authorization or not authorization.startswith("Bearer "):
        return None
    return _TOKENS.get(authorization.removeprefix("Bearer "))


# json.dumps cannot emit an overflowing literal; json.loads reads 1e400 as inf.
_OVERFLOW_EXP_PAYLOAD = base64.urlsafe_b64encode(b'{"exp": 1e400}').decode()


def _jwt(payload: dict[str, Any]) -> str:
    def part(data: dict[str, Any]) -> str:
        raw = json.dumps(data).encode()
        return base64.urlsafe_b64encode(raw).rstrip(b"=").decode()

    return f"{part({'alg': 'HS256'})}.{part(payload)}.signature"


@pytest.fixture(autouse=True)
def _clean_registry() -> Iterator[None]:
    saved = dict(site._registry)
    site._registry = {}
    yield
    site._registry = saved


def _build(
    *,
    host: FastAPI | None = None,
    mount_mode: str | None = None,
    get_user: Any = get_current_user,
    settings: dict[str, Any] | None = None,
    **auth_kwargs: Any,
) -> tuple[Admin, TestClient]:
    app = host or FastAPI()
    site.register(ThHostUser, ThHostUserAdmin)
    values: dict[str, Any] = {"secret_key": _SECRET, **(settings or {})}
    if mount_mode is not None:
        values["mount_mode"] = mount_mode
    admin = Admin(
        app,
        engine=create_async_engine("sqlite+aiosqlite:///:memory:"),
        settings=HyperAdminSettings(**values),
        auth=ExternalAuth(get_user=get_user, **auth_kwargs),
    )
    with (
        pytest.warns(DeprecationWarning, match="router")
        if mount_mode == "router"
        else _no_warning()
    ):
        admin.mount("/admin")
    return admin, TestClient(app, follow_redirects=False)


class _no_warning:  # noqa: N801 - a tiny context manager stand-in for pytest.warns
    def __enter__(self) -> None:
        return None

    def __exit__(self, *exc: object) -> None:
        return None


def _csrf_from(client: TestClient, path: str) -> str:
    page = client.get(path)
    match = _FIELD_TOKEN.search(page.text)
    assert match is not None, page.text
    return match.group(1)


def _set_cookie_headers(response: Any) -> list[str]:
    return response.headers.get_list("set-cookie")


def _token_cookie_header(response: Any) -> str:
    matches = [h for h in _set_cookie_headers(response) if h.startswith("hyperadmin_token=")]
    assert len(matches) == 1, _set_cookie_headers(response)
    return matches[0]


# ---------------------------------------------------------------------------
# Story scenarios
# ---------------------------------------------------------------------------


def test_handoff_sets_cookie() -> None:
    """
    Scenario: handoff sets cookie
      Given ExternalAuth(token_cookie=TokenCookie()) at /admin
      When  POST /admin/auth/session is sent with a valid bearer
      Then  hyperadmin_token is set HttpOnly, SameSite=Lax, Path=/admin
      And   a following GET /admin/ with only that cookie returns 200
    """
    # Given
    _, client = _build(token_cookie=TokenCookie())

    # When
    response = client.post("/admin/auth/session", headers={"Authorization": "Bearer staff-token"})

    # Then
    assert response.status_code == 204
    cookie = _token_cookie_header(response)
    assert cookie.startswith("hyperadmin_token=staff-token;")
    assert "HttpOnly" in cookie
    assert "SameSite=lax" in cookie
    assert "Path=/admin" in cookie
    assert "Max-Age=28800" in cookie
    assert "Secure" not in cookie
    # And
    assert client.cookies.get("hyperadmin_token") == "staff-token"
    assert client.get("/admin/").status_code == 200


@pytest.mark.parametrize(
    "auth_kwargs",
    [
        {},
        {"login_url": "/login"},
        {"token_cookie": TokenCookie(token_endpoint=lambda u, p: None)},
    ],
    ids=["no-login", "login_url", "token_endpoint"],
)
def test_invalid_token_rejected(auth_kwargs: dict[str, Any]) -> None:
    """
    Scenario: invalid token rejected
      Given the host rejects 'Bearer bad' (with or without a browser login page)
      When  POST /admin/auth/session is sent
      Then  the response is 401, never a redirect to a login page
      And   no cookie is set
    """
    # Given
    _, client = _build(**{"token_cookie": TokenCookie(), **auth_kwargs})

    # When
    response = client.post("/admin/auth/session", headers={"Authorization": "Bearer bad"})

    # Then
    assert response.status_code == 401
    assert "location" not in response.headers
    assert not any(h.startswith("hyperadmin_token=bad") for h in _set_cookie_headers(response))
    assert client.cookies.get("hyperadmin_token") is None


def test_oversized_token() -> None:
    """
    Scenario: oversized token
      Given a 5000-byte token
      When  POST /admin/auth/session is sent
      Then  the response is 400
    """
    # Given
    calls: list[str | None] = []

    def recording_user(authorization: str | None = Header(default=None)) -> ThHostUser | None:
        calls.append(authorization)
        return STAFF

    _, client = _build(token_cookie=TokenCookie(), get_user=recording_user)
    token = "x" * 5000

    # When
    response = client.post("/admin/auth/session", headers={"Authorization": f"Bearer {token}"})

    # Then
    assert response.status_code == 400
    assert calls == []  # rejected before the host dependency ever runs
    assert client.cookies.get("hyperadmin_token") is None


def test_token_at_the_size_limit_is_accepted() -> None:
    """
    Scenario: a token of exactly the size limit is accepted
      Given a token of MAX_TOKEN_BYTES bytes that the host accepts
      When  POST /admin/auth/session is sent
      Then  the response is 204
    """
    # Given
    token = "t" * MAX_TOKEN_BYTES
    _TOKENS[token] = STAFF
    try:
        _, client = _build(token_cookie=TokenCookie())

        # When
        response = client.post("/admin/auth/session", headers={"Authorization": f"Bearer {token}"})
    finally:
        del _TOKENS[token]

    # Then
    assert MAX_TOKEN_BYTES == 3800
    assert response.status_code == 204


def test_logout_clears_cookie() -> None:
    """
    Scenario: logout clears cookie
      Given a token cookie
      When  POST /admin/logout is sent with a CSRF token
      Then  the cookie is cleared
      And   the response redirects to logout_url
    """
    # Given
    _, client = _build(token_cookie=TokenCookie(), logout_url="https://host.example/signed-out")
    client.cookies.set("hyperadmin_token", "staff-token")
    page = client.get("/admin/")
    assert page.status_code == 200
    csrf = client.cookies.get("hyperadmin_csrf")
    assert csrf

    # When
    response = client.post("/admin/logout", headers={"X-CSRF-Token": csrf})

    # Then
    assert response.status_code == 303
    cookie = _token_cookie_header(response)
    assert 'hyperadmin_token=""' in cookie
    assert "Max-Age=0" in cookie
    assert "Path=/admin" in cookie
    # And
    assert response.headers["location"] == "https://host.example/signed-out"


def test_logout_without_logout_url_goes_to_site_root() -> None:
    """
    Scenario: logout without logout_url goes to the site root
      Given ExternalAuth without logout_url and without a token cookie
      When  POST /admin/logout is sent with a bearer and a CSRF token
      Then  the response is a 303 to /
      And   no token cookie is touched
    """
    # Given
    _, client = _build()
    bearer = {"Authorization": "Bearer staff-token"}
    client.get("/admin/", headers=bearer)
    csrf = client.cookies.get("hyperadmin_csrf")
    assert csrf

    # When
    response = client.post("/admin/logout", headers={**bearer, "X-CSRF-Token": csrf})

    # Then
    assert response.status_code == 303
    assert response.headers["location"] == "/"
    assert not any(h.startswith("hyperadmin_token=") for h in _set_cookie_headers(response))


def test_logout_without_csrf_token_is_rejected() -> None:
    """
    Scenario: logout is CSRF-checked
      Given a token cookie
      When  POST /admin/logout is sent without a CSRF token
      Then  the response is 403
      And   the token cookie is not cleared
    """
    # Given
    _, client = _build(token_cookie=TokenCookie(), logout_url="/bye")
    client.cookies.set("hyperadmin_token", "staff-token")

    # When
    response = client.post("/admin/logout")

    # Then
    assert response.status_code == 403
    assert not any(h.startswith("hyperadmin_token=") for h in _set_cookie_headers(response))


def test_no_open_redirect() -> None:
    """
    Scenario: no open redirect
      Given next=https://evil.example
      When  the handoff succeeds
      Then  the redirect stays under /admin
    """
    # Given
    _, client = _build(token_cookie=TokenCookie())

    # When
    response = client.post(
        "/admin/auth/session",
        params={"next": "https://evil.example"},
        headers={"Authorization": "Bearer staff-token"},
    )

    # Then
    assert response.status_code == 303
    assert response.headers["location"] == "/admin/"
    assert client.cookies.get("hyperadmin_token") == "staff-token"


def test_handoff_redirects_to_a_valid_next() -> None:
    """
    Scenario: the handoff follows a next inside the admin
      Given next=/admin/ththostuser?page=2
      When  the handoff succeeds
      Then  the response is a 303 to that path
    """
    # Given
    _, client = _build(token_cookie=TokenCookie())

    # When
    response = client.post(
        "/admin/auth/session",
        params={"next": "/admin/ththostuser?page=2"},
        headers={"Authorization": "Bearer staff-token"},
    )

    # Then
    assert response.status_code == 303
    assert response.headers["location"] == "/admin/ththostuser?page=2"


# ---------------------------------------------------------------------------
# Review amendments: handoff guard, CSRF exemption, router mode
# ---------------------------------------------------------------------------


def test_handoff_is_exempt_from_csrf() -> None:
    """
    Scenario: the handoff needs no CSRF token
      Given CSRF is enforced in bridge mode
      When  POST /admin/auth/session is sent with a bearer and no CSRF cookie or token
      Then  the response is 204
    """
    # Given
    admin, client = _build(token_cookie=TokenCookie())
    assert admin.csrf_mode == "enforce"

    # When
    response = client.post("/admin/auth/session", headers={"Authorization": "Bearer staff-token"})

    # Then
    assert response.status_code == 204
    assert not any(h.startswith("hyperadmin_csrf=") for h in _set_cookie_headers(response))


def test_handoff_ignores_the_token_cookie() -> None:
    """
    Scenario: the handoff never authenticates from the cookie
      Given a valid hyperadmin_token cookie and no Authorization header
      When  POST /admin/auth/session is sent
      Then  the response is 401
      And   the cookie is not refreshed
    """
    # Given
    _, client = _build(token_cookie=TokenCookie())
    client.cookies.set("hyperadmin_token", "staff-token")

    # When
    response = client.post("/admin/auth/session")

    # Then
    assert response.status_code == 401
    assert not any(
        h.startswith("hyperadmin_token=staff-token") for h in _set_cookie_headers(response)
    )


def test_handoff_rejects_a_different_scheme() -> None:
    """
    Scenario: a non-bearer Authorization header is not stored
      Given a host get_user that accepts any Authorization header
      When  POST /admin/auth/session is sent with 'Basic abc'
      Then  the response is 400
      And   no cookie is set
    """

    # Given
    def any_header(authorization: str | None = Header(default=None)) -> ThHostUser | None:
        return STAFF if authorization else None

    _, client = _build(token_cookie=TokenCookie(), get_user=any_header)

    # When
    response = client.post("/admin/auth/session", headers={"Authorization": "Basic abc"})

    # Then
    assert response.status_code == 400
    assert client.cookies.get("hyperadmin_token") is None


def test_handoff_without_a_bearer_header_is_rejected() -> None:
    """
    Scenario: a host user resolved without a bearer header has no token to store
      Given a host get_user that resolves the user from something other than Authorization
      When  POST /admin/auth/session is sent with no Authorization header
      Then  the response is 400
      And   no cookie is set
    """

    # Given
    def ambient_user() -> ThHostUser:
        return STAFF

    _, client = _build(token_cookie=TokenCookie(), get_user=ambient_user)

    # When
    response = client.post("/admin/auth/session")

    # Then
    assert response.status_code == 400
    assert client.cookies.get("hyperadmin_token") is None


def test_handoff_denied_by_can_access() -> None:
    """
    Scenario: a host user that fails can_access gets no cookie
      Given the host accepts 'Bearer customer-token' for a non-staff user
      When  POST /admin/auth/session is sent
      Then  the response is 403
      And   no cookie is set
    """
    # Given
    _, client = _build(token_cookie=TokenCookie())

    # When
    response = client.post(
        "/admin/auth/session", headers={"Authorization": "Bearer customer-token"}
    )

    # Then
    assert response.status_code == 403
    assert client.cookies.get("hyperadmin_token") is None


def test_handoff_honours_host_dependency_overrides() -> None:
    """
    Scenario: the handoff resolves get_user through host overrides
      Given the host overrides get_user to accept 'Bearer override'
      When  POST /admin/auth/session is sent with that bearer
      Then  the response is 204
    """
    # Given
    host = FastAPI()
    _, client = _build(host=host, token_cookie=TokenCookie())
    host.dependency_overrides[get_current_user] = lambda: STAFF

    # When
    response = client.post("/admin/auth/session", headers={"Authorization": "Bearer override"})

    # Then
    assert response.status_code == 204
    assert client.cookies.get("hyperadmin_token") == "override"


def test_handoff_and_logout_in_router_mode() -> None:
    """
    Scenario: router mode serves the handoff and logout under the prefix
      Given mount_mode="router" with TokenCookie()
      When  the handoff succeeds and then POST /admin/logout is sent with a CSRF token
      Then  the cookie is set with Path=/admin and then cleared
    """
    # Given
    _, client = _build(mount_mode="router", token_cookie=TokenCookie(), logout_url="/bye")

    # When
    handoff = client.post("/admin/auth/session", headers={"Authorization": "Bearer staff-token"})
    client.get("/admin/")
    csrf = client.cookies.get("hyperadmin_csrf")
    assert csrf
    logout = client.post("/admin/logout", headers={"X-CSRF-Token": csrf})

    # Then
    assert handoff.status_code == 204
    assert "Path=/admin" in _token_cookie_header(handoff)
    assert logout.status_code == 303
    assert logout.headers["location"] == "/bye"
    assert "Max-Age=0" in _token_cookie_header(logout)


def test_handoff_cookie_is_secure_over_https() -> None:
    """
    Scenario: the token cookie follows cookie_secure="auto"
      Given an https request
      When  the handoff succeeds
      Then  hyperadmin_token is marked Secure
    """
    # Given
    admin, _ = _build(token_cookie=TokenCookie())
    client = TestClient(admin.app, base_url="https://testserver", follow_redirects=False)

    # When
    response = client.post("/admin/auth/session", headers={"Authorization": "Bearer staff-token"})

    # Then
    assert response.status_code == 204
    assert "Secure" in _token_cookie_header(response)


def test_no_handoff_route_without_token_cookie() -> None:
    """
    Scenario: apps without TokenCookie get no handoff route
      Given ExternalAuth without token_cookie
      When  POST /admin/auth/session is sent with a valid bearer
      Then  the response is 404 or 405 and no cookie is set
    """
    # Given
    _, client = _build(settings={"csrf_mode": "off"})

    # When
    response = client.post("/admin/auth/session", headers={"Authorization": "Bearer staff-token"})

    # Then
    assert response.status_code in {404, 405}
    assert client.cookies.get("hyperadmin_token") is None


# ---------------------------------------------------------------------------
# Review amendment: cookie Max-Age = min(max_age, jwt exp - now)
# ---------------------------------------------------------------------------


def test_handoff_cookie_lifetime_follows_jwt_exp() -> None:
    """
    Scenario: a short-lived JWT caps the cookie lifetime
      Given a JWT whose exp is 120 seconds from now and TokenCookie(max_age=3600)
      When  the handoff succeeds
      Then  the cookie Max-Age is at most 120
    """
    # Given
    token = _jwt({"sub": "ada", "exp": int(time.time()) + 120})
    _TOKENS[token] = STAFF
    try:
        _, client = _build(token_cookie=TokenCookie(max_age=3600))

        # When
        response = client.post("/admin/auth/session", headers={"Authorization": f"Bearer {token}"})
    finally:
        del _TOKENS[token]

    # Then
    assert response.status_code == 204
    match = re.search(r"Max-Age=(\d+)", _token_cookie_header(response))
    assert match is not None
    assert 110 <= int(match.group(1)) <= 120


class TestCookieMaxAge:
    def test_opaque_token_uses_max_age(self) -> None:
        """
        Scenario: an opaque token keeps max_age
          Given a token that is not a JWT
          When  cookie_max_age(token, 3600) is computed
          Then  the result is 3600
        """
        assert cookie_max_age("opaque", 3600) == 3600

    def test_jwt_exp_below_max_age_wins(self) -> None:
        """
        Scenario: exp - now below max_age wins
          Given a JWT expiring at now + 60
          When  cookie_max_age(token, 3600, now=now) is computed
          Then  the result is 60
        """
        assert cookie_max_age(_jwt({"exp": 1060}), 3600, now=1000) == 60

    def test_max_age_below_jwt_exp_wins(self) -> None:
        """
        Scenario: max_age below exp - now wins
          Given a JWT expiring at now + 9000
          When  cookie_max_age(token, 3600, now=now) is computed
          Then  the result is 3600
        """
        assert cookie_max_age(_jwt({"exp": 10000}), 3600, now=1000) == 3600

    def test_no_max_age_uses_jwt_exp(self) -> None:
        """
        Scenario: without max_age the JWT exp alone decides
          Given TokenCookie(max_age=None) and a JWT expiring at now + 90
          When  cookie_max_age(token, None, now=now) is computed
          Then  the result is 90
        """
        assert cookie_max_age(_jwt({"exp": 1090.5}), None, now=1000) == 90

    def test_no_max_age_and_opaque_is_a_session_cookie(self) -> None:
        """
        Scenario: an opaque token without max_age is a session cookie
          Given TokenCookie(max_age=None) and an opaque token
          When  cookie_max_age is computed
          Then  the result is None
        """
        assert cookie_max_age("opaque", None) is None

    def test_expired_jwt_is_zero(self) -> None:
        """
        Scenario: an already expired JWT never yields a negative Max-Age
          Given a JWT whose exp is in the past
          When  cookie_max_age is computed
          Then  the result is 0
        """
        assert cookie_max_age(_jwt({"exp": 10}), 3600, now=1000) == 0

    @pytest.mark.parametrize(
        "token",
        [
            "a.b",
            "a.!!!.c",
            f"a.{base64.urlsafe_b64encode(b'not json').decode()}.c",
            f"a.{base64.urlsafe_b64encode(b'[1]').decode()}.c",
            _jwt({"sub": "no-exp"}),
            _jwt({"exp": "soon"}),
            _jwt({"exp": True}),
            _jwt({"exp": float("nan")}),
            _jwt({"exp": float("inf")}),
            _jwt({"exp": float("-inf")}),
            f"a.{_OVERFLOW_EXP_PAYLOAD}.c",
        ],
    )
    def test_unreadable_payloads_have_no_expiry(self, token: str) -> None:
        """
        Scenario: a token without a readable numeric exp has no expiry
          Given a malformed, non-JSON, non-object, exp-less or non-finite-exp payload
          When  jwt_expiry(token) is read
          Then  the result is None
        """
        assert jwt_expiry(token) is None


# ---------------------------------------------------------------------------
# Review amendment: next validation
# ---------------------------------------------------------------------------


class TestSafeNext:
    @pytest.mark.parametrize(
        "value",
        [
            "/admin/",
            "/admin/order",
            "/admin/order/5?tab=x",
        ],
    )
    def test_accepts_relative_paths_under_the_admin(self, value: str) -> None:
        """
        Scenario: a relative path under the admin path plus '/' is kept
          Given admin path /admin
          When  safe_next(value, "/admin") is called
          Then  the value is returned unchanged
        """
        assert safe_next(value, "/admin") == value

    @pytest.mark.parametrize(
        "value",
        [
            None,
            "",
            "https://evil.example",
            "//evil.example/admin/",
            "/\\evil.example",
            "/admin/\\evil",
            "javascript:alert(1)",
            "/admin",
            "/administrator/x",
            "/other/",
            "admin/order",
            "/admin/../logout",
            "/admin/%2e%2e/host",
            "/admin/x\r\nSet-Cookie: a=b",
            "/admin/x\tY",
            "http:/admin/x",
        ],
    )
    def test_rejects_everything_else(self, value: str | None) -> None:
        """
        Scenario: schemes, '//', backslashes and outside paths fall back to the dashboard
          Given admin path /admin
          When  safe_next(value, "/admin") is called
          Then  the dashboard /admin/ is returned
        """
        assert safe_next(value, "/admin") == "/admin/"

    def test_follows_the_request_admin_path(self) -> None:
        """
        Scenario: the admin path carries the host root_path
          Given admin path /api/admin
          When  safe_next("/admin/x", "/api/admin") is called
          Then  the dashboard /api/admin/ is returned
        """
        assert safe_next("/admin/x", "/api/admin") == "/api/admin/"
        assert safe_next("/api/admin/x", "/api/admin") == "/api/admin/x"


# ---------------------------------------------------------------------------
# Review amendment: a rejected cookie token is cleared before the redirect
# ---------------------------------------------------------------------------


def test_rejected_cookie_token_is_cleared_before_the_redirect() -> None:
    """
    Scenario: a dead token cookie never causes a login loop
      Given a hyperadmin_token cookie the host no longer accepts and login_url set
      When  GET /admin/ is sent
      Then  the response is a 303 to the login_url
      And   the token cookie is cleared on that response
    """
    # Given
    _, client = _build(token_cookie=TokenCookie(), login_url="/login")
    client.cookies.set("hyperadmin_token", "expired-token")

    # When
    response = client.get("/admin/")

    # Then
    assert response.status_code == 303
    assert response.headers["location"].startswith("/login?next=")
    cookie = _token_cookie_header(response)
    assert "Max-Age=0" in cookie
    assert "Path=/admin" in cookie


# ---------------------------------------------------------------------------
# Review amendment: the opt-in admin login form for bearer hosts
# ---------------------------------------------------------------------------

_oauth2 = OAuth2PasswordBearer(tokenUrl="token")
_PASSWORDS = {"ada": ("secret", "staff-token")}


def bearer_user(token: str = Depends(_oauth2)) -> ThHostUser | None:
    """A bearer-only host get_user built on OAuth2PasswordBearer(auto_error=True)."""
    user = _TOKENS.get(token)
    if user is None:
        raise HTTPException(status_code=401, detail="Invalid token")
    return user


def _bearer_host() -> FastAPI:
    """A bearer-only host app: an OAuth2 password-grant /token endpoint, no frontend change."""
    host = FastAPI()

    @host.post("/token")
    def issue(
        grant_type: str = Form(default="password"),
        username: str = Form(...),
        password: str = Form(...),
    ) -> dict[str, str]:
        expected = _PASSWORDS.get(username)
        if grant_type != "password" or expected is None or expected[0] != password:
            raise HTTPException(status_code=400, detail="Incorrect username or password")
        return {"access_token": expected[1], "token_type": "bearer"}

    return host


def test_bearer_only_host_reaches_admin_in_a_browser() -> None:
    """
    Scenario: a bearer-only host with no frontend change reaches /admin in a browser
      Given a host using OAuth2PasswordBearer(tokenUrl="token") and TokenCookie(token_endpoint="auto")
      When  a browser opens /admin/, follows the login redirect and submits valid credentials
      Then  it is redirected back to /admin/ with the hyperadmin_token cookie set
      And   GET /admin/ with only that cookie returns 200
    """
    # Given
    _, client = _build(
        host=_bearer_host(), get_user=bearer_user, token_cookie=TokenCookie(token_endpoint="auto")
    )

    # When
    first = client.get("/admin/")
    assert first.status_code == 303
    assert first.headers["location"] == "/admin/login?next=%2Fadmin%2F"
    page = client.get(first.headers["location"])
    assert page.status_code == 200
    assert 'name="next" value="/admin/"' in page.text
    csrf = _FIELD_TOKEN.search(page.text)
    assert csrf is not None
    login = client.post(
        "/admin/login",
        data={
            "username": "ada",
            "password": "secret",
            "next": "/admin/",
            "csrf_token": csrf.group(1),
        },
    )

    # Then
    assert login.status_code == 303
    assert login.headers["location"] == "/admin/"
    cookie = _token_cookie_header(login)
    assert cookie.startswith("hyperadmin_token=staff-token;")
    assert "HttpOnly" in cookie
    # And
    assert client.get("/admin/").status_code == 200


def test_login_form_rejects_wrong_credentials() -> None:
    """
    Scenario: wrong credentials re-render the form
      Given the bridge login form backed by the host /token endpoint
      When  POST /admin/login is sent with a wrong password
      Then  the form is re-rendered with an error
      And   no token cookie is set
    """
    # Given
    _, client = _build(
        host=_bearer_host(), get_user=bearer_user, token_cookie=TokenCookie(token_endpoint="/token")
    )
    csrf = _csrf_from(client, "/admin/login")

    # When
    response = client.post(
        "/admin/login", data={"username": "ada", "password": "wrong", "csrf_token": csrf}
    )

    # Then
    assert response.status_code == 200
    assert 'data-testid="login-error"' in response.text
    assert client.cookies.get("hyperadmin_token") is None


def test_login_form_is_csrf_protected() -> None:
    """
    Scenario: the login form is CSRF-protected
      Given the bridge login form
      When  POST /admin/login is sent with valid credentials but no CSRF token
      Then  the response is 403 and no cookie is set
    """
    # Given
    _, client = _build(
        host=_bearer_host(), get_user=bearer_user, token_cookie=TokenCookie(token_endpoint="/token")
    )

    # When
    response = client.post("/admin/login", data={"username": "ada", "password": "secret"})

    # Then
    assert response.status_code == 403
    assert client.cookies.get("hyperadmin_token") is None


def test_login_form_with_issue_token_callable_and_bad_next() -> None:
    """
    Scenario: an issue_token callable signs the user in and a foreign next is ignored
      Given TokenCookie(token_endpoint=issue_token) with an async callable
      When  POST /admin/login is sent with valid credentials and next=//evil.example
      Then  the response is a 303 to /admin/ with the token cookie set
    """

    # Given
    async def issue_token(username: str, password: str) -> str | None:
        return "staff-token" if (username, password) == ("ada", "secret") else None

    _, client = _build(get_user=bearer_user, token_cookie=TokenCookie(token_endpoint=issue_token))
    page = client.get("/admin/login", params={"next": "//evil.example"})
    assert 'name="next"' not in page.text
    csrf = _FIELD_TOKEN.search(page.text)
    assert csrf is not None

    # When
    response = client.post(
        "/admin/login",
        data={
            "username": "ada",
            "password": "secret",
            "next": "//evil.example",
            "csrf_token": csrf.group(1),
        },
    )

    # Then
    assert response.status_code == 303
    assert response.headers["location"] == "/admin/"
    assert client.cookies.get("hyperadmin_token") == "staff-token"


def test_login_form_refuses_an_oversized_issued_token(caplog: pytest.LogCaptureFixture) -> None:
    """
    Scenario: an issued token too large for the cookie re-renders the form
      Given TokenCookie(token_endpoint=issue_token) returning a token over MAX_TOKEN_BYTES
      When  POST /admin/login is sent with valid credentials
      Then  the form is re-rendered (200) with an error
      And   no hyperadmin_token cookie is set
    """

    # Given
    def issue_token(username: str, password: str) -> str | None:
        return "x" * (MAX_TOKEN_BYTES + 1)

    _, client = _build(get_user=bearer_user, token_cookie=TokenCookie(token_endpoint=issue_token))
    csrf = _csrf_from(client, "/admin/login")

    # When
    with caplog.at_level("WARNING", logger="hyperadmin.auth"):
        response = client.post(
            "/admin/login", data={"username": "ada", "password": "secret", "csrf_token": csrf}
        )

    # Then
    assert response.status_code == 200
    assert 'data-testid="login-error"' in response.text
    assert "too large for the admin cookie" in response.text
    assert "exceeds" in caplog.text
    # And
    assert not any(h.startswith("hyperadmin_token=") for h in _set_cookie_headers(response))
    assert client.cookies.get("hyperadmin_token") is None


def test_bridge_navbar_logout_form_targets_admin_logout_with_csrf() -> None:
    """
    Scenario: the bridge-mode navbar logs out through the admin's own logout route
      Given ExternalAuth(token_cookie=TokenCookie(), logout_url="/bye") and a token cookie
      When  the dashboard is rendered
      Then  the logout form posts to /admin/logout and carries a CSRF field
      And   it does not post straight to the host's logout_url
    """
    # Given
    _, client = _build(token_cookie=TokenCookie(), logout_url="/bye")
    client.cookies.set("hyperadmin_token", "staff-token")

    # When
    page = client.get("/admin/")

    # Then
    assert page.status_code == 200
    form = re.search(
        r'<form method="post" action="/admin/logout">(.*?)</form>', page.text, re.DOTALL
    )
    assert form is not None
    assert 'name="csrf_token"' in form.group(1)
    assert 'data-testid="logout-btn"' in form.group(1)
    # And
    assert 'action="/bye"' not in page.text


def test_login_url_wins_over_the_login_form() -> None:
    """
    Scenario: an explicit login_url keeps sending browsers to the host login
      Given TokenCookie(token_endpoint=...) and login_url="/signin"
      When  an anonymous browser opens /admin/
      Then  it is redirected to /signin, not the admin login form
    """
    # Given
    _, client = _build(
        host=_bearer_host(),
        get_user=bearer_user,
        login_url="/signin",
        token_cookie=TokenCookie(token_endpoint="/token"),
    )

    # When
    response = client.get("/admin/")

    # Then
    assert response.status_code == 303
    assert response.headers["location"].startswith("/signin?next=")


def test_no_login_form_without_token_endpoint() -> None:
    """
    Scenario: the admin login form is opt-in
      Given TokenCookie() without token_endpoint
      When  GET /admin/login is sent anonymously
      Then  no login form is served
    """
    # Given
    _, client = _build(token_cookie=TokenCookie())

    # When
    response = client.get("/admin/login")

    # Then
    assert 'data-testid="login-form"' not in response.text


def test_auto_token_endpoint_without_oauth2_bearer_fails_fast() -> None:
    """
    Scenario: token_endpoint="auto" needs an OAuth2PasswordBearer in get_user
      Given a get_user dependency tree with no OAuth2PasswordBearer
      When  admin.mount() runs with TokenCookie(token_endpoint="auto")
      Then  a ValueError names the missing tokenUrl
    """
    # Given / When / Then
    with pytest.raises(ValueError, match="OAuth2PasswordBearer"):
        _build(token_cookie=TokenCookie(token_endpoint="auto"))


class TestDiscoverTokenUrl:
    def test_finds_nested_oauth2_password_bearer(self) -> None:
        """
        Scenario: the tokenUrl is found deep in the get_user dependency tree
          Given get_user -> current_token -> OAuth2PasswordBearer(tokenUrl="/auth/token")
          When  discover_token_url(get_user) is called
          Then  "/auth/token" is returned
        """
        scheme = OAuth2PasswordBearer(tokenUrl="/auth/token")

        def current_token(token: str = Depends(scheme)) -> str:
            return token

        def get_user(token: str = Depends(current_token)) -> str:
            return token

        assert discover_token_url(get_user) == "/auth/token"

    def test_returns_none_without_one(self) -> None:
        """
        Scenario: no OAuth2PasswordBearer means no tokenUrl
          Given a get_user reading only a header
          When  discover_token_url(get_user) is called
          Then  None is returned
        """
        assert discover_token_url(get_current_user) is None


class TestRequestToken:
    pytestmark = pytest.mark.anyio

    @pytest.fixture
    def anyio_backend(self) -> str:
        return "asyncio"

    async def test_sync_callable(self) -> None:
        """
        Scenario: a sync issue_token callable is used as is
          Given issue_token returning "tok"
          When  request_token is called
          Then  "tok" is returned
        """
        assert await request_token(lambda u, p: "tok", "u", "p", host_app=FastAPI()) == "tok"

    async def test_callable_returning_empty_is_none(self) -> None:
        """
        Scenario: an empty token from the callable counts as a failure
          Given issue_token returning ""
          When  request_token is called
          Then  None is returned
        """
        assert await request_token(lambda u, p: "", "u", "p", host_app=FastAPI()) is None

    @pytest.mark.parametrize(
        "body",
        [{"token_type": "bearer"}, {"access_token": ""}, {"access_token": 5}, ["x"]],
    )
    async def test_in_process_payload_without_access_token(self, body: Any) -> None:
        """
        Scenario: a 200 response without a usable access_token is a failure
          Given a host /token endpoint answering 200 with no string access_token
          When  request_token is called
          Then  None is returned
        """
        host = FastAPI()

        @host.post("/token")
        def issue() -> Any:
            return body

        assert await request_token("token", "u", "p", host_app=host) is None

    async def test_in_process_non_json_payload(self) -> None:
        """
        Scenario: a non-JSON token response is a failure
          Given a host /token endpoint answering plain text
          When  request_token is called
          Then  None is returned
        """
        from fastapi.responses import PlainTextResponse

        host = FastAPI()

        @host.post("/token")
        def issue() -> PlainTextResponse:
            return PlainTextResponse("nope")

        assert await request_token("/token", "u", "p", host_app=host) is None

    async def test_in_process_endpoint_crash_is_a_failure(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        """
        Scenario: a crashing host token endpoint never breaks the login form
          Given a host /token endpoint that raises
          When  request_token is called
          Then  None is returned and the error is logged
        """
        host = FastAPI()

        @host.post("/token")
        def issue() -> dict[str, str]:
            raise RuntimeError("boom")

        assert await request_token("/token", "u", "p", host_app=host) is None
        assert "token endpoint" in caplog.text

    async def test_in_process_sends_the_password_grant(self) -> None:
        """
        Scenario: the in-process call posts the OAuth2 password grant form
          Given a host /auth/token?x=1 endpoint echoing the form
          When  request_token is called with ("ada", "s3cret")
          Then  it receives grant_type=password, username and password
        """
        host = FastAPI()
        seen: dict[str, str] = {}

        @host.post("/auth/token")
        def issue(
            x: str,
            grant_type: str = Form(...),
            username: str = Form(...),
            password: str = Form(...),
        ) -> dict[str, str]:
            seen.update(x=x, grant_type=grant_type, username=username, password=password)
            return {"access_token": "tok"}

        token = await request_token("/auth/token?x=1", "ada", "s3cret", host_app=host)

        assert token == "tok"
        assert seen == {"x": "1", "grant_type": "password", "username": "ada", "password": "s3cret"}

    async def test_in_process_receive_after_the_body_reports_a_disconnect(self) -> None:
        """
        Scenario: the in-process call ends the request stream after the body
          Given a raw ASGI host app that reads the body and then reads once more
          When  request_token is called
          Then  the second read is an http.disconnect
          And   the token from the response is returned
        """
        seen: list[str] = []

        async def host(scope: Any, receive: Any, send: Any) -> None:
            seen.append((await receive())["type"])
            seen.append((await receive())["type"])
            body = json.dumps({"access_token": "raw-token"}).encode()
            await send({"type": "http.response.start", "status": 200, "headers": []})
            await send({"type": "http.response.body", "body": body})

        assert await request_token("/token", "u", "p", host_app=host) == "raw-token"
        assert seen == ["http.request", "http.disconnect"]

    async def test_absolute_url_is_posted_over_http(self, token_server: str) -> None:
        """
        Scenario: an absolute token URL is posted to over HTTP
          Given an HTTP token server accepting ada/secret
          When  request_token is called with good and then bad credentials
          Then  the token is returned and then None
        """
        url = f"{token_server}/token"

        assert await request_token(url, "ada", "secret", host_app=FastAPI()) == "remote-token"
        assert await request_token(url, "ada", "wrong", host_app=FastAPI()) is None

    async def test_unreachable_absolute_url_is_none(self) -> None:
        """
        Scenario: an unreachable token server is a failure
          Given a token URL on a closed port
          When  request_token is called
          Then  None is returned
        """
        assert (
            await request_token("http://127.0.0.1:9/token", "ada", "x", host_app=FastAPI()) is None
        )


class _TokenHandler(BaseHTTPRequestHandler):
    def do_POST(self) -> None:
        length = int(self.headers.get("content-length", "0"))
        form = parse_qs(self.rfile.read(length).decode())
        ok = form.get("username") == ["ada"] and form.get("password") == ["secret"]
        body = json.dumps({"access_token": "remote-token"} if ok else {"detail": "bad"}).encode()
        self.send_response(200 if ok else 400)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format: str, *args: Any) -> None:  # noqa: A002 - stdlib signature
        return None


@pytest.fixture
def token_server() -> Iterator[str]:
    server = HTTPServer(("127.0.0.1", 0), _TokenHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{server.server_address[1]}"
    finally:
        server.shutdown()
        server.server_close()
