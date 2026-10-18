"""Realtime under any auth mode: hashable user keys, bridge-aware SSE/WS, WS Origin check.

Story st-v058-byoa-42 (SDD ``bring-your-own-app.md`` section B, Reconciliation):

- ``RealtimeConnection.user_id`` is any ``Hashable`` (UUID, str, int);
- SSE and WebSocket key connections on ``request.state.user_key``, which both the
  bridge dependency and ``AuthenticationMiddleware`` set;
- the WebSocket route exists in bridge mode only when ``websocket_user`` is set;
- the WebSocket handshake refuses a foreign ``Origin``.
"""

from __future__ import annotations

import json
import logging
import uuid
from collections.abc import Hashable, Iterator
from dataclasses import dataclass, field
from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock

import anyio
import pytest
from fastapi import FastAPI, Header
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import create_async_engine
from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import JSONResponse
from starlette.routing import Route
from starlette.websockets import WebSocketDisconnect

from hyperadmin import Admin
from hyperadmin.auth.bridge import BridgeWebSocketAuth, ExternalAuth
from hyperadmin.auth.middleware import AuthenticationMiddleware
from hyperadmin.core.registry import site
from hyperadmin.core.settings import HyperAdminSettings
from hyperadmin.realtime import ConnectionRegistry, RealtimeConnection, RealtimeSettings
from hyperadmin.realtime._debug import make_count_handler
from hyperadmin.realtime.ws import WS_CLOSE_UNAUTHORIZED

_SECRET = "realtime-bridge-secret"
_UUID = uuid.UUID("6f1c2a54-8a3e-4d1b-9c55-0e7f3b2a9d10")


@dataclass
class _HostUser:
    """A host user whose primary key is a UUID."""

    id: Any
    username: str = "ada"
    is_staff: bool = True
    is_superuser: bool = True


@dataclass
class _KeylessUser:
    """A host user with no ``id`` at all, keyed by e-mail."""

    email: str
    is_staff: bool = True
    groups: list[str] = field(default_factory=list)


@pytest.fixture(autouse=True)
def _clean_registry() -> Iterator[None]:
    saved = dict(site._registry)
    site._registry = {}
    yield
    site._registry = saved


def _settings(**overrides: Any) -> HyperAdminSettings:
    values: dict[str, Any] = {"secret_key": _SECRET, "create_tables": False, **overrides}
    return HyperAdminSettings(**values)


def _engine() -> Any:
    return create_async_engine("sqlite+aiosqlite:///:memory:")


def _record_registrations(admin: Admin, monkeypatch: pytest.MonkeyPatch) -> list[Hashable]:
    """Record each registered connection's key, then close it so the stream ends.

    The SSE stream would otherwise hold the request open forever; closing the
    connection right after it registers makes the handler emit one frame and exit.
    """
    registry = admin._realtime_registry
    assert registry is not None
    keys: list[Hashable] = []
    register = registry.register

    async def _register(conn: RealtimeConnection) -> None:
        await register(conn)
        keys.append(conn.user_id)
        await conn.close()

    monkeypatch.setattr(registry, "register", _register)
    return keys


def _bridge_admin(user: Any, **auth_kwargs: Any) -> tuple[Admin, TestClient]:
    def get_user(authorization: str | None = Header(default=None)) -> Any:
        return user if authorization == "Bearer ok" else None

    app = FastAPI()
    admin = Admin(
        app,
        engine=_engine(),
        settings=_settings(csrf_mode="off"),
        realtime=RealtimeSettings(),
        auth=ExternalAuth(get_user=get_user, **auth_kwargs),
    )
    admin.mount("/admin")
    return admin, TestClient(app)


class _Backend:
    """A built-in-style ``auth_backend`` that resolves one fixed user."""

    def __init__(self, user: Any) -> None:
        self.user = user

    async def get_current_user(self, request: Any) -> Any:
        return self.user

    async def authenticate(self, username: str, password: str) -> None:
        return None


def _builtin_admin(user: Any, **settings: Any) -> tuple[Admin, TestClient]:
    app = FastAPI()
    admin = Admin(
        app,
        engine=_engine(),
        settings=_settings(register_auth_models=False, **settings),
        realtime=RealtimeSettings(),
        auth_backend=_Backend(user),
    )
    admin.mount("/admin")
    return admin, TestClient(app)


def _ws_route_names(admin: Admin) -> set[str]:
    return {getattr(route, "name", "") for route in admin.router.routes}


# ---------------------------------------------------------------------------
# Scenario: UUID principal
# ---------------------------------------------------------------------------


def test_uuid_principal(monkeypatch: pytest.MonkeyPatch) -> None:
    """
    Scenario: UUID principal
      Given realtime enabled and a bridged user with a UUID id
      When  GET /admin/realtime/sse is requested
      Then  a connection is registered under that UUID key
    """
    # Given realtime enabled and a bridged user with a UUID id
    admin, client = _bridge_admin(_HostUser(id=_UUID))
    keys = _record_registrations(admin, monkeypatch)

    # When GET /admin/realtime/sse is requested
    response = client.get("/admin/realtime/sse", headers={"Authorization": "Bearer ok"})

    # Then a connection is registered under that UUID key
    assert response.status_code == 200
    assert response.text == ":keepalive\n\n"
    assert keys == [_UUID]


def test_sse_keys_on_custom_user_key(monkeypatch: pytest.MonkeyPatch) -> None:
    """
    Scenario: SSE keys the connection on the bridge's user_key
      Given a bridged user without an id and ExternalAuth(user_key=lambda u: u.email)
      When  GET /admin/realtime/sse is requested
      Then  a connection is registered under the e-mail
    """
    admin, client = _bridge_admin(_KeylessUser(email="ada@example.com"), user_key=_email_key)
    keys = _record_registrations(admin, monkeypatch)

    response = client.get("/admin/realtime/sse", headers={"Authorization": "Bearer ok"})

    assert response.status_code == 200
    assert keys == ["ada@example.com"]


def _email_key(user: Any) -> Hashable:
    return user.email


def test_sse_refuses_anonymous_bridge_request() -> None:
    """
    Scenario: SSE without an admitted user is refused
      Given realtime enabled in bridge mode
      When  GET /admin/realtime/sse is requested without credentials
      Then  the response is 401 and no connection is registered
    """
    admin, client = _bridge_admin(_HostUser(id=_UUID))

    response = client.get("/admin/realtime/sse")

    assert response.status_code == 401
    assert admin._realtime_registry is not None
    assert admin._realtime_registry.count() == 0


def test_sse_with_built_in_auth_keys_on_user_id(monkeypatch: pytest.MonkeyPatch) -> None:
    """
    Scenario: built-in auth SSE is keyed on the user's id
      Given realtime enabled with an auth_backend resolving a user with a UUID id
      When  GET /admin/realtime/sse is requested
      Then  a connection is registered under that UUID key
    """
    admin, client = _builtin_admin(_HostUser(id=_UUID))
    keys = _record_registrations(admin, monkeypatch)

    response = client.get("/admin/realtime/sse")

    assert response.status_code == 200
    assert keys == [_UUID]


def test_sse_handler_refuses_request_without_user_key() -> None:
    """
    Scenario: SSE refuses a request carrying a user but no user_key
      Given a host middleware that sets request.state.user only
      When  the SSE handler runs
      Then  the response is 401
    """
    from hyperadmin.realtime.sse import make_sse_handler

    handler = make_sse_handler(ConnectionRegistry(), RealtimeSettings())
    request = Request({"type": "http", "method": "GET", "headers": [], "state": {}})
    request.state.user = _HostUser(id=1)

    response = anyio.run(handler, request)

    assert response.status_code == 401


# ---------------------------------------------------------------------------
# AuthenticationMiddleware sets user_key / user_display
# ---------------------------------------------------------------------------


def test_authentication_middleware_sets_user_key_and_display() -> None:
    """
    Scenario: built-in auth exposes the same request.state keys as the bridge
      Given AuthenticationMiddleware resolving a user with id 7 and username "ada"
      When  an admin route is requested
      Then  request.state.user_key is 7 and request.state.user_display is "ada"
    """

    async def echo(request: Request) -> JSONResponse:
        return JSONResponse({"key": request.state.user_key, "display": request.state.user_display})

    app = Starlette(routes=[Route("/admin/echo", echo)])
    app.add_middleware(AuthenticationMiddleware, auth_backend=_Backend(_HostUser(id=7)))

    response = TestClient(app).get("/admin/echo")

    assert response.json() == {"key": 7, "display": "ada"}


# ---------------------------------------------------------------------------
# Scenario: mixed key types
# ---------------------------------------------------------------------------


def test_mixed_key_types() -> None:
    """
    Scenario: mixed key types
      Given connections for int and UUID users
      When  the debug snapshot is built
      Then  it does not raise
      And   int keys keep their numeric order ahead of the other keys
    """
    # Given connections for int and UUID users
    registry = ConnectionRegistry()

    async def _seed() -> None:
        for key in (12, _UUID, 3, "carol"):
            await registry.register(
                RealtimeConnection(user_id=key, transport="sse", close=AsyncMock())
            )

    anyio.run(_seed)
    handler = make_count_handler(registry)

    # When the debug snapshot is built
    response = anyio.run(handler, Request({"type": "http", "method": "GET", "headers": []}))

    # Then it does not raise
    assert response.status_code == 200
    payload = json.loads(bytes(response.body))
    assert payload["count"] == 4
    # And int keys keep their numeric order ahead of the other keys
    assert payload["users"] == [3, 12, str(_UUID), "carol"]
    assert registry.users() == {12, 3, _UUID, "carol"}


# ---------------------------------------------------------------------------
# Scenario: foreign-origin WS closed
# ---------------------------------------------------------------------------


def _ws_session(
    client: TestClient, headers: dict[str, str], monkeypatch: pytest.MonkeyPatch, admin: Admin
) -> tuple[int, list[set[Hashable]]]:
    """Open the realtime WebSocket; return the close code and the users seen registered."""
    import hyperadmin.realtime.ws as ws_module

    registry = admin._realtime_registry
    assert registry is not None
    seen: list[set[Hashable]] = []

    async def _one_shot_receive_loop(websocket: Any) -> None:
        seen.append(registry.users())

    monkeypatch.setattr(ws_module, "_receive_loop", _one_shot_receive_loop)
    # A refused handshake raises from ``websocket_connect`` itself (the server
    # closes before accepting); an admitted one raises on the first receive.
    with (
        pytest.raises(WebSocketDisconnect) as excinfo,
        client.websocket_connect("/admin/realtime/ws", headers=headers) as ws,
    ):
        ws.receive_bytes()
    return excinfo.value.code, seen


def test_foreign_origin_ws_closed(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    """
    Scenario: foreign-origin WS closed
      Given realtime with built-in auth
      When  a WS handshake arrives with Origin: https://evil.example
      Then  the handshake is rejected with the unauthorized code
    """
    # Given realtime with built-in auth
    admin, client = _builtin_admin(_HostUser(id=1))

    # When a WS handshake arrives with Origin: https://evil.example
    with caplog.at_level(logging.WARNING, logger="hyperadmin.csrf"):
        code, seen = _ws_session(client, {"Origin": "https://evil.example"}, monkeypatch, admin)

    # Then the handshake is rejected with the unauthorized code
    assert code == WS_CLOSE_UNAUTHORIZED
    assert seen == []
    assert "https://evil.example" in caplog.text


@pytest.mark.parametrize(
    ("origin", "trusted"),
    [
        pytest.param("http://testserver", [], id="same-host"),
        pytest.param("https://testserver", [], id="tls-terminating-proxy"),
        pytest.param("https://admin.example", ["https://admin.example"], id="trusted"),
    ],
)
def test_allowed_origin_ws_is_admitted(
    monkeypatch: pytest.MonkeyPatch, origin: str, trusted: list[str]
) -> None:
    """
    Scenario: same-origin or trusted WS handshake is admitted
      Given realtime with built-in auth and csrf_trusted_origins
      When  a WS handshake arrives from the admin's own host or a trusted origin
      Then  the connection is registered for the user's id
    """
    admin, client = _builtin_admin(_HostUser(id=1), csrf_trusted_origins=trusted)

    code, seen = _ws_session(client, {"Origin": origin}, monkeypatch, admin)

    assert seen == [{1}]
    assert code != WS_CLOSE_UNAUTHORIZED


def test_ws_without_origin_is_admitted(monkeypatch: pytest.MonkeyPatch) -> None:
    """
    Scenario: a non-browser WS client without Origin is admitted
      Given realtime with built-in auth
      When  a WS handshake arrives without an Origin header
      Then  the connection is registered for the user's id
    """
    admin, client = _builtin_admin(_HostUser(id=_UUID))

    _code, seen = _ws_session(client, {}, monkeypatch, admin)

    assert seen == [{_UUID}]


def test_bridge_ws_keys_on_custom_user_key(monkeypatch: pytest.MonkeyPatch) -> None:
    """
    Scenario: bridge WS keys the connection on the bridge's user_key
      Given ExternalAuth(websocket_user=hook, user_key=lambda u: u.email)
      When  the WebSocket opens for a user without an id
      Then  the connection is registered under the e-mail
    """
    user = _KeylessUser(email="ada@example.com")

    async def ws_user(websocket: Any) -> Any:
        return user

    admin, client = _bridge_admin(user, websocket_user=ws_user, user_key=_email_key)

    _code, seen = _ws_session(client, {}, monkeypatch, admin)

    assert seen == [{"ada@example.com"}]


def test_bridge_ws_foreign_origin_closed(monkeypatch: pytest.MonkeyPatch) -> None:
    """
    Scenario: bridge-mode WS from a foreign origin is closed
      Given ExternalAuth(websocket_user=hook) with realtime enabled
      When  a WS handshake arrives with Origin: https://evil.example
      Then  the socket is closed with the unauthorized code before the hook runs
    """
    hook = AsyncMock(return_value=_HostUser(id=_UUID))
    admin, client = _bridge_admin(_HostUser(id=_UUID), websocket_user=hook)

    code, seen = _ws_session(client, {"Origin": "https://evil.example"}, monkeypatch, admin)

    assert code == WS_CLOSE_UNAUTHORIZED
    assert seen == []
    hook.assert_not_awaited()


# ---------------------------------------------------------------------------
# Scenario: bridge without websocket_user
# ---------------------------------------------------------------------------


def test_bridge_without_websocket_user(caplog: pytest.LogCaptureFixture) -> None:
    """
    Scenario: bridge without websocket_user
      Given bridge mode and no websocket_user
      When  the admin mounts
      Then  no WS route is registered
    """
    # Given bridge mode and no websocket_user
    # When the admin mounts
    with caplog.at_level(logging.INFO, logger="hyperadmin"):
        admin, _client = _bridge_admin(_HostUser(id=_UUID))

    # Then no WS route is registered
    names = _ws_route_names(admin)
    assert "admin-realtime-ws" not in names
    assert "admin-realtime-sse" in names
    assert "websocket_user" in caplog.text


def test_bridge_with_websocket_user_registers_ws_route() -> None:
    """
    Scenario: bridge with websocket_user registers the WS route
      Given bridge mode and a websocket_user hook
      When  the admin mounts
      Then  the WS route is registered
    """
    admin, _client = _bridge_admin(_HostUser(id=_UUID), websocket_user=AsyncMock())

    assert "admin-realtime-ws" in _ws_route_names(admin)


def test_bridge_websocket_auth_without_hook_admits_no_one() -> None:
    """
    Scenario: the bridge WebSocket adapter fails closed without websocket_user
      Given BridgeWebSocketAuth over an ExternalAuth with no websocket_user
      When  get_current_user is called for a handshake
      Then  it returns None and sets no user_key
    """
    adapter = BridgeWebSocketAuth(ExternalAuth(get_user=AsyncMock()))
    websocket: Any = SimpleNamespace(state=SimpleNamespace())

    assert anyio.run(adapter.get_current_user, websocket) is None
    assert not hasattr(websocket.state, "user_key")
