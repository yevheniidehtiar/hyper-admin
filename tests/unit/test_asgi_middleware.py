"""Plain-ASGI contract tests for LocaleMiddleware and AuthenticationMiddleware.

StartupGuardMiddleware was already plain ASGI; its tests pin that.

Covers the scenarios of docs/specs/asgi-middleware.md (st-perf-03).
"""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any

import anyio
import pytest
from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import StreamingResponse
from starlette.routing import Route

from hyperadmin.auth.middleware import AuthenticationMiddleware
from hyperadmin.auth.otp import PARTIAL_AUTH_SESSION_KEY
from hyperadmin.core.lifecycle import StartupGuardMiddleware
from hyperadmin.core.settings import HyperAdminSettings
from hyperadmin.i18n.loader import get_current_translations
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
# StartupGuardMiddleware (already plain ASGI: pinned here so it stays so)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("scope_type", ["websocket", "lifespan"])
async def test_startup_guard_non_http_scopes_pass_through_untouched(scope_type: str) -> None:
    """
    Scenario: non-HTTP scopes pass through untouched
      Given the admin app
      When  a websocket or lifespan scope arrives
      Then  each middleware forwards it to the inner app
    """
    inner = _Recorder()
    lifecycle: Any = SimpleNamespace(started=True)
    mw = StartupGuardMiddleware(inner, lifecycle=lifecycle, admin_prefix="/admin")
    scope: dict[str, Any] = {"type": scope_type}

    await mw(scope, _noop_receive, _discard)

    assert inner.scopes == [scope]


async def test_stack_does_not_buffer_a_streaming_response() -> None:
    """
    Scenario: a streaming response is not buffered
      Given an SSE-like app behind the locale and auth middleware
      When  the client reads the stream
      Then  the first chunk is sent before the app produces the second
    """
    events: list[str] = []

    async def streaming_app(scope: Any, receive: Any, send: Any) -> None:
        await send({"type": "http.response.start", "status": 200, "headers": []})
        events.append("produce-1")
        await send({"type": "http.response.body", "body": b"a", "more_body": True})
        events.append("produce-2")
        await send({"type": "http.response.body", "body": b"b", "more_body": False})

    stack = LocaleMiddleware(
        AuthenticationMiddleware(streaming_app, _Backend(_User())), HyperAdminSettings()
    )

    async def send(message: dict[str, Any]) -> None:
        if message["type"] == "http.response.body":
            events.append(f"recv-{message['body'].decode()}")

    await stack(_http_scope(path="/admin/"), _noop_receive, send)

    assert events == ["produce-1", "recv-a", "produce-2", "recv-b"]


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

    class _Checker:
        async def get_user_permissions(self, user: Any) -> list[str]:
            return ["a.view"]

    class _Plain(_User):
        is_superuser = False

    inner = _Recorder()
    mw = AuthenticationMiddleware(inner, _Backend(_Plain()), permission_checker=_Checker())

    _, scope = await _run_auth(mw, _http_scope(path="/admin/"))

    assert scope["state"]["user_permissions"] == frozenset({"a.view"})


async def test_auth_backend_reading_the_body_raises_and_leaves_the_stream_alone() -> None:
    """
    Scenario: the auth gate never drains the request body
      Given a backend whose get_current_user reads the body
      When  GET /admin/ is requested
      Then  the read raises instead of consuming the inner app's stream
    """

    class _BodyReader:
        async def get_current_user(self, request: Any) -> Any:
            return await request.body()

    mw = AuthenticationMiddleware(_Recorder(), _BodyReader())

    with pytest.raises(RuntimeError):
        await _run_auth(mw, _http_scope(path="/admin/"))


async def test_auth_state_is_visible_to_the_inner_app_request() -> None:
    """
    Scenario: the inner app reads auth state through Request(scope).state
      Given a logged-in user
      When  GET /admin/ reaches the inner app
      Then  Request(scope).state.user is that user
    """
    seen: list[Any] = []

    async def inner(scope: Any, receive: Any, send: Any) -> None:
        seen.append(Request(scope).state.user)

    user = _User()
    await _run_auth(AuthenticationMiddleware(inner, _Backend(user)), _http_scope(path="/admin/"))

    assert seen == [user]


# ---------------------------------------------------------------------------
# LocaleMiddleware edge cases and streaming
# ---------------------------------------------------------------------------


async def test_locale_adds_header_when_start_message_has_no_headers() -> None:
    """
    Scenario: a start message without headers still gets Content-Language
      Given an inner app that sends http.response.start with no headers key
      When  the request passes the locale middleware
      Then  Content-Language is set and no KeyError is raised
    """

    async def bare(scope: Any, receive: Any, send: Any) -> None:
        await send({"type": "http.response.start", "status": 204})
        await send({"type": "http.response.body", "body": b""})

    sent: list[dict[str, Any]] = []

    async def send(message: dict[str, Any]) -> None:
        sent.append(message)

    await LocaleMiddleware(bare, HyperAdminSettings())(_http_scope(), _noop_receive, send)

    assert (b"content-language", b"en") in sent[0]["headers"]


async def test_locale_resets_translations_when_the_inner_app_raises() -> None:
    """
    Scenario: translations are reset when the inner app fails
      Given an inner app that raises
      When  the request passes the locale middleware
      Then  the exception propagates and the translations contextvar is restored
    """

    async def boom(scope: Any, receive: Any, send: Any) -> None:
        raise ValueError("boom")

    before = get_current_translations()
    mw = LocaleMiddleware(boom, HyperAdminSettings())

    with pytest.raises(ValueError, match="boom"):
        await mw(_http_scope([(b"cookie", b"hyperadmin_locale=es")]), _noop_receive, _discard)

    assert get_current_translations() is before


async def test_real_streaming_response_is_not_buffered_and_header_is_set_once() -> None:
    """
    Scenario: a real StreamingResponse flows through the stack unbuffered
      Given a Starlette streaming route behind the locale and auth middleware
      When  the client reads the stream
      Then  Content-Language is on the start message only and chunks arrive as produced
    """
    gate = anyio.Event()

    async def body() -> Any:
        yield b"a"
        await gate.wait()
        yield b"b"

    async def stream(request: Request) -> StreamingResponse:
        return StreamingResponse(body())

    app = Starlette(routes=[Route("/admin/stream", stream)])
    stack = LocaleMiddleware(AuthenticationMiddleware(app, _Backend(_User())), HyperAdminSettings())
    sent: list[dict[str, Any]] = []

    async def send(message: dict[str, Any]) -> None:
        sent.append(message)
        if message["type"] == "http.response.body" and message["body"] == b"a":
            # The second chunk has not been produced yet: nothing buffered it.
            assert len(sent) == 2
            gate.set()

    async def idle_receive() -> dict[str, Any]:
        # A real client sends nothing more until it disconnects; a receive that
        # returns instantly would spin StreamingResponse's disconnect listener.
        await anyio.sleep_forever()
        raise AssertionError("unreachable")

    scope = _http_scope(path="/admin/stream")
    scope["app"] = app
    await stack(scope, idle_receive, send)

    starts = [m for m in sent if m["type"] == "http.response.start"]
    assert len(starts) == 1
    assert (b"content-language", b"en") in starts[0]["headers"]
    chunks = [m["body"] for m in sent if m["type"] == "http.response.body"]
    assert b"".join(chunks) == b"ab"
