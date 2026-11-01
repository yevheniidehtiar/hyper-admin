"""The realtime WebSocket path when the ASGI server cannot upgrade to WebSocket.

Plain ``uvicorn`` (without ``websockets`` or ``wsproto``) hands the upgrade request
to the app as an ordinary HTTP GET. Without a fallback route the router answers
404 and nothing explains why live notifications never arrive.
"""

from __future__ import annotations

import logging
from collections.abc import Iterator

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import create_async_engine

from hyperadmin import Admin, HyperAdminSettings
from hyperadmin.realtime import RealtimeSettings
from hyperadmin.realtime import ws as ws_module
from hyperadmin.realtime.pubsub import InMemoryPubSub

UPGRADE_HEADERS = {
    "Connection": "Upgrade",
    "Upgrade": "websocket",
    "Sec-WebSocket-Version": "13",
    "Sec-WebSocket-Key": "dGhlIHNhbXBsZSBub25jZQ==",
}


@pytest.fixture(autouse=True)
def _reset_warning() -> Iterator[None]:
    ws_module._warn_ws_unsupported.cache_clear()
    yield
    ws_module._warn_ws_unsupported.cache_clear()


def _client() -> TestClient:
    app = FastAPI()
    admin = Admin(
        app=app,
        engine=create_async_engine("sqlite+aiosqlite://"),
        settings=HyperAdminSettings(create_tables=False),
        realtime=RealtimeSettings(pubsub=InMemoryPubSub()),
    )
    admin.mount("/admin")
    return TestClient(app)


def test_upgrade_request_over_plain_http_explains_the_missing_websocket_support(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """
    Scenario: a server without WebSocket support gets a clear answer
      Given realtime is enabled and the server delivers the upgrade as plain HTTP
      When  the browser requests /admin/realtime/ws
      Then  the response is 426 Upgrade Required naming the missing WebSocket library
      And   one warning in the server log says how to fix it
    """
    client = _client()

    with caplog.at_level(logging.WARNING, logger="hyperadmin.realtime.ws"):
        first = client.get("/admin/realtime/ws", headers=UPGRADE_HEADERS)
        second = client.get("/admin/realtime/ws", headers=UPGRADE_HEADERS)

    assert first.status_code == 426
    assert first.headers["upgrade"] == "websocket"
    assert "uvicorn[standard]" in first.text
    assert second.status_code == 426
    warnings = [r for r in caplog.records if r.name == "hyperadmin.realtime.ws"]
    assert len(warnings) == 1
    assert "uvicorn[standard]" in warnings[0].getMessage()


def test_plain_get_without_upgrade_is_not_found(caplog: pytest.LogCaptureFixture) -> None:
    """
    Scenario: an ordinary GET on the WebSocket path stays a 404
      Given realtime is enabled
      When  a client GETs /admin/realtime/ws without asking for an upgrade
      Then  the response is 404 and nothing is logged
    """
    client = _client()

    with caplog.at_level(logging.WARNING, logger="hyperadmin.realtime.ws"):
        response = client.get("/admin/realtime/ws")

    assert response.status_code == 404
    assert not [r for r in caplog.records if r.name == "hyperadmin.realtime.ws"]


def test_websocket_handshake_still_reaches_the_websocket_route() -> None:
    """
    Scenario: a server with WebSocket support is unaffected
      Given realtime is enabled and the server supports WebSocket
      When  the browser opens /admin/realtime/ws
      Then  the WebSocket handshake is accepted
    """
    client = _client()

    with client.websocket_connect("/admin/realtime/ws") as websocket:
        websocket.send_json({"type": "unsubscribe", "model": "article"})
