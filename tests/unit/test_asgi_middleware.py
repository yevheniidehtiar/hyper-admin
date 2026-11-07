"""Plain-ASGI contract tests for LocaleMiddleware and AuthenticationMiddleware.

Covers the scenarios of docs/specs/asgi-middleware.md (st-perf-03).
"""

from __future__ import annotations

from typing import Any

import pytest

from hyperadmin.core.settings import HyperAdminSettings
from hyperadmin.i18n.middleware import LocaleMiddleware

pytestmark = pytest.mark.anyio


class _Recorder:
    """Inner ASGI app recording the scope it receives."""

    def __init__(self) -> None:
        self.scopes: list[dict[str, Any]] = []

    async def __call__(self, scope: Any, receive: Any, send: Any) -> None:
        self.scopes.append(scope)
        if scope["type"] == "http":
            await send({"type": "http.response.start", "status": 200, "headers": []})
            await send({"type": "http.response.body", "body": b"ok"})


async def _noop_receive() -> dict[str, Any]:
    return {"type": "http.request", "body": b"", "more_body": False}


async def _discard(message: dict[str, Any]) -> None:
    return None


def _http_scope(
    headers: list[tuple[bytes, bytes]] | None = None, path: str = "/"
) -> dict[str, Any]:
    return {
        "type": "http",
        "method": "GET",
        "path": path,
        "raw_path": path.encode(),
        "root_path": "",
        "query_string": b"",
        "headers": headers or [],
    }


@pytest.mark.parametrize("scope_type", ["websocket", "lifespan"])
async def test_locale_non_http_scopes_pass_through_untouched(scope_type: str) -> None:
    """
    Scenario: non-HTTP scopes pass through untouched
      Given the admin app
      When  a websocket or lifespan scope arrives
      Then  each middleware forwards it to the inner app
    """
    inner = _Recorder()
    mw = LocaleMiddleware(inner, HyperAdminSettings())
    scope: dict[str, Any] = {"type": scope_type}

    await mw(scope, _noop_receive, _discard)

    assert inner.scopes == [scope]
    assert "state" not in scope


async def test_locale_sets_state_and_content_language_header() -> None:
    """
    Scenario: locale is negotiated, stored on scope state and echoed in the header
      Given supported locales and a locale cookie
      When  an http request passes the middleware
      Then  scope["state"]["locale"] is set and Content-Language is on the response
    """
    inner = _Recorder()
    mw = LocaleMiddleware(inner, HyperAdminSettings())
    sent: list[dict[str, Any]] = []

    async def send(message: dict[str, Any]) -> None:
        sent.append(message)

    scope = _http_scope([(b"cookie", b"hyperadmin_locale=es")])
    await mw(scope, _noop_receive, send)

    assert scope["state"]["locale"] == "es"
    assert (b"content-language", b"es") in sent[0]["headers"]
    assert sent[1]["body"] == b"ok"


async def test_locale_header_disabled_leaves_response_untouched() -> None:
    """
    Scenario: locale_response_header=False omits Content-Language
      Given locale_response_header is false
      When  an http request passes the middleware
      Then  the response has no Content-Language header
    """
    inner = _Recorder()
    mw = LocaleMiddleware(inner, HyperAdminSettings(locale_response_header=False))
    sent: list[dict[str, Any]] = []

    async def send(message: dict[str, Any]) -> None:
        sent.append(message)

    await mw(_http_scope(), _noop_receive, send)

    assert not any(k == b"content-language" for k, _ in sent[0]["headers"])


# ---------------------------------------------------------------------------
# AuthenticationMiddleware
# ---------------------------------------------------------------------------


class _User:
    id = 7
    username = "alice"
    is_superuser = True


class _Backend:
    def __init__(self, user: Any = None) -> None:
        self.user = user

    async def get_current_user(self, request: Any) -> Any:
        return self.user


async def _run_auth(mw: Any, scope: dict[str, Any]) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    sent: list[dict[str, Any]] = []

    async def send(message: dict[str, Any]) -> None:
        sent.append(message)

    await mw(scope, _noop_receive, send)
    return sent, scope


def _headers(start: dict[str, Any]) -> dict[bytes, bytes]:
    return dict(start["headers"])


@pytest.mark.parametrize("scope_type", ["websocket", "lifespan"])
async def test_auth_non_http_scopes_pass_through_untouched(scope_type: str) -> None:
    """
    Scenario: non-HTTP scopes pass through untouched
      Given the admin app
      When  a websocket or lifespan scope arrives
      Then  each middleware forwards it to the inner app
    """
    from hyperadmin.auth.middleware import AuthenticationMiddleware

    inner = _Recorder()
    mw = AuthenticationMiddleware(inner, _Backend())
    scope: dict[str, Any] = {"type": scope_type}

    await mw(scope, _noop_receive, _discard)

    assert inner.scopes == [scope]


async def test_auth_anonymous_request_is_redirected_to_login() -> None:
    """
    Scenario: an anonymous request is redirected to login
      Given auth is configured
      When  GET /admin/ without a session
      Then  the response is a 302 to /admin/login
    """
    from hyperadmin.auth.middleware import AuthenticationMiddleware

    inner = _Recorder()
    mw = AuthenticationMiddleware(inner, _Backend())

    sent, _ = await _run_auth(mw, _http_scope(path="/admin/"))

    assert sent[0]["status"] == 302
    assert _headers(sent[0])[b"location"] == b"/admin/login"
    assert inner.scopes == []


async def test_auth_anonymous_realtime_request_gets_401() -> None:
    """
    Scenario: anonymous API-style request is rejected with 401
      Given auth is configured
      When  GET /admin/realtime/stream without a session
      Then  the response is a 401 and the inner app is not called
    """
    from hyperadmin.auth.middleware import AuthenticationMiddleware

    inner = _Recorder()
    mw = AuthenticationMiddleware(inner, _Backend())

    sent, _ = await _run_auth(mw, _http_scope(path="/admin/realtime/stream"))

    assert sent[0]["status"] == 401
    assert inner.scopes == []


async def test_auth_partial_auth_session_is_redirected_to_mfa_challenge() -> None:
    """
    Scenario: a mid-MFA user is bounced to the challenge page
      Given an anonymous request whose session holds a partial-auth marker
      When  GET /admin/ is requested
      Then  the response is a 302 to /admin/mfa/challenge
    """
    from hyperadmin.auth.middleware import AuthenticationMiddleware
    from hyperadmin.auth.otp import PARTIAL_AUTH_SESSION_KEY

    inner = _Recorder()
    mw = AuthenticationMiddleware(inner, _Backend())
    scope = _http_scope(path="/admin/")
    scope["session"] = {PARTIAL_AUTH_SESSION_KEY: {"stage": "mfa_pending", "user_id": 3}}

    sent, _ = await _run_auth(mw, scope)

    assert _headers(sent[0])[b"location"] == b"/admin/mfa/challenge"


async def test_auth_mfa_route_and_host_route_pass_through() -> None:
    """
    Scenario: MFA endpoints, static assets and non-admin paths reach the inner app
      Given an anonymous request
      When  it targets /admin/mfa/challenge, a static asset or a host route
      Then  the inner app handles it
    """
    from hyperadmin.auth.middleware import AuthenticationMiddleware

    inner = _Recorder()
    mw = AuthenticationMiddleware(inner, _Backend())

    await _run_auth(mw, _http_scope(path="/admin/mfa/challenge"))
    await _run_auth(mw, _http_scope(path="/other"))
    await _run_auth(mw, _http_scope(path="/admin/static/x.css"))

    assert len(inner.scopes) == 3


async def test_auth_public_login_path_sets_anonymous_user_state() -> None:
    """
    Scenario: the login page is public
      Given an anonymous request
      When  GET /admin/login
      Then  the inner app runs with scope state user = None
    """
    from hyperadmin.auth.middleware import AuthenticationMiddleware

    inner = _Recorder()
    mw = AuthenticationMiddleware(inner, _Backend())

    _, scope = await _run_auth(mw, _http_scope(path="/admin/login"))

    assert scope["state"]["user"] is None
    assert len(inner.scopes) == 1


async def test_auth_authenticated_request_populates_scope_state() -> None:
    """
    Scenario: an authenticated request exposes the user on request.state
      Given a logged-in user
      When  GET /admin/ is requested
      Then  scope["state"] carries user, user_key and user_permissions
    """
    from hyperadmin.auth.middleware import AuthenticationMiddleware

    inner = _Recorder()
    mw = AuthenticationMiddleware(inner, _Backend(_User()))

    sent, scope = await _run_auth(mw, _http_scope(path="/admin/"))

    assert sent[0]["status"] == 200
    assert scope["state"]["user_key"] == 7
    assert scope["state"]["user_permissions"] is None


async def test_auth_non_superuser_permissions_loaded_once() -> None:
    """
    Scenario: permission codenames are loaded for non-superusers
      Given a permission checker and a non-superuser
      When  GET /admin/ is requested
      Then  scope state holds the frozenset of codenames
    """
    from hyperadmin.auth.middleware import AuthenticationMiddleware

    class _Checker:
        async def get_user_permissions(self, user: Any) -> list[str]:
            return ["a.view"]

    class _Plain(_User):
        is_superuser = False

    inner = _Recorder()
    mw = AuthenticationMiddleware(inner, _Backend(_Plain()), permission_checker=_Checker())

    _, scope = await _run_auth(mw, _http_scope(path="/admin/"))

    assert scope["state"]["user_permissions"] == frozenset({"a.view"})
