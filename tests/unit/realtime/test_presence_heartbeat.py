"""Presence heartbeat handling on the realtime WebSocket (Epic 6.2.4, #326/#327).

Drives the real ``make_ws_handler`` through Starlette's ``TestClient`` with an
in-memory ``PresenceBackend`` / ``PubSubBackend`` so each test maps to one
scenario of the heartbeat contract documented in ``realtime/ws.py``.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import pytest
from starlette.applications import Starlette
from starlette.routing import WebSocketRoute
from starlette.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

from hyperadmin.realtime import (
    ConnectionRegistry,
    InMemoryPresence,
    InMemoryPubSub,
    RealtimeSettings,
    presence_channel,
)
from hyperadmin.realtime.ws import MAX_PRESENCE_CHANNELS, make_ws_handler, presence_payload


@dataclass
class _User:
    id: int
    username: str = ""


class _Auth:
    """Resolves the user from the ``?u=<id>`` query param (``0`` -> anonymous)."""

    async def get_current_user(self, websocket: Any) -> _User | None:
        uid = int(websocket.query_params.get("u", "1"))
        if uid == 0:
            return None
        return _User(id=uid, username=websocket.query_params.get("name", ""))


class _Harness:
    def __init__(self) -> None:
        self.presence = InMemoryPresence()
        handler = make_ws_handler(
            ConnectionRegistry(),
            RealtimeSettings(),
            _Auth(),
            presence=self.presence,
            pubsub=InMemoryPubSub(),
        )
        self.client = TestClient(Starlette(routes=[WebSocketRoute("/ws", handler)]))


def _beat(model: str = "article", pk: Any = "42", mode: str = "viewing") -> dict[str, Any]:
    return {"type": "presence", "model": model, "pk": pk, "mode": mode}


def _users(msg: dict[str, Any]) -> list[tuple[str, str, str]]:
    return [(u["user_id"], u["display_name"], u["mode"]) for u in msg["users"]]


@pytest.fixture
def h() -> _Harness:
    return _Harness()


def test_heartbeat_sets_presence_and_broadcasts_roster(h: _Harness) -> None:
    # Given an authenticated socket
    with h.client.websocket_connect("/ws?u=7&name=Ada") as ws:
        # When it sends an editing heartbeat for article 42
        ws.send_json(_beat(mode="editing"))
        msg = ws.receive_json()

        # Then it receives the roster with itself in it
        assert msg["type"] == "presence"
        assert (msg["model"], msg["pk"]) == ("article", "42")
        assert _users(msg) == [("7", "Ada", "editing")]
        assert {"since", "last_seen"} <= msg["users"][0].keys()


def test_heartbeat_broadcast_reaches_other_viewers(h: _Harness) -> None:
    # Given Ada is viewing article 42
    with h.client.websocket_connect("/ws?u=7&name=Ada") as ada:
        ada.send_json(_beat())
        ada.receive_json()
        # When Bob starts editing the same record
        with h.client.websocket_connect("/ws?u=8&name=Bob") as bob:
            bob.send_json(_beat(mode="editing"))
            # Then both receive a roster with both users
            for ws in (ada, bob):
                msg = ws.receive_json()
                assert _users(msg) == [("7", "Ada", "viewing"), ("8", "Bob", "editing")]


def test_repeat_heartbeat_updates_mode_and_integer_pk(h: _Harness) -> None:
    with h.client.websocket_connect("/ws?u=7&name=Ada") as ws:
        ws.send_json(_beat(pk=5, mode="viewing"))
        ws.receive_json()
        # When the same user re-sends with a new mode
        ws.send_json(_beat(pk=5, mode="editing"))
        # Then the roster still has one entry, now editing
        assert _users(ws.receive_json()) == [("7", "Ada", "editing")]


def test_other_records_are_not_notified(h: _Harness) -> None:
    with h.client.websocket_connect("/ws?u=7&name=Ada") as ada:
        ada.send_json(_beat(pk="1"))
        ada.receive_json()
        with h.client.websocket_connect("/ws?u=8&name=Bob") as bob:
            bob.send_json(_beat(pk="2"))
            assert _users(bob.receive_json()) == [("8", "Bob", "viewing")]
        # Ada's next message is her own roster for record 1, free of Bob
        ada.send_json(_beat(pk="1"))
        assert _users(ada.receive_json()) == [("7", "Ada", "viewing")]


def test_disconnect_removes_presence_and_broadcasts(h: _Harness) -> None:
    with h.client.websocket_connect("/ws?u=7&name=Ada") as ada:
        ada.send_json(_beat())
        ada.receive_json()
        with h.client.websocket_connect("/ws?u=8&name=Bob") as bob:
            bob.send_json(_beat())
            ada.receive_json()
            bob.receive_json()
        # When Bob's socket closes, Ada gets a roster without him
        assert _users(ada.receive_json()) == [("7", "Ada", "viewing")]
    # And once Ada is gone too, the backend holds nothing
    assert h.presence.user_count(presence_channel("article", "42")) == 0


def test_leave_removes_presence_and_stops_updates(h: _Harness) -> None:
    with h.client.websocket_connect("/ws?u=7&name=Ada") as ws:
        ws.send_json(_beat())
        ws.receive_json()
        # When the user leaves the record
        ws.send_json(_beat(mode="leave"))
        # Then the (now empty) roster is broadcast and presence is gone
        assert ws.receive_json()["users"] == []
        assert h.presence.user_count(presence_channel("article", "42")) == 0
        # And leaving an unknown record is a no-op
        ws.send_json(_beat(pk="999", mode="leave"))
        # Re-joining works again
        ws.send_json(_beat())
        assert _users(ws.receive_json()) == [("7", "Ada", "viewing")]


def test_display_name_falls_back_to_user_key(h: _Harness) -> None:
    with h.client.websocket_connect("/ws?u=7") as ws:
        ws.send_json(_beat())
        assert _users(ws.receive_json()) == [("7", "7", "viewing")]


@pytest.mark.parametrize(
    "frame",
    [
        "not json",
        "[1, 2]",
        '{"type": "notification"}',
        '{"type": "presence", "model": "", "pk": "1", "mode": "viewing"}',
        '{"type": "presence", "model": "a", "pk": null, "mode": "viewing"}',
        '{"type": "presence", "model": "a", "pk": true, "mode": "viewing"}',
        '{"type": "presence", "model": "a", "pk": "1", "mode": "dancing"}',
        '{"type": "presence", "model": "a", "pk": "' + "x" * 201 + '", "mode": "viewing"}',
    ],
)
def test_malformed_frames_are_ignored(h: _Harness, frame: str) -> None:
    with h.client.websocket_connect("/ws?u=7&name=Ada") as ws:
        ws.send_text(frame)
        # The socket survives; a binary frame is ignored too
        ws.send_bytes(b"\x00")
        ws.send_json(_beat())
        assert _users(ws.receive_json()) == [("7", "Ada", "viewing")]


def test_followed_records_are_capped(h: _Harness) -> None:
    with h.client.websocket_connect("/ws?u=7&name=Ada") as ws:
        for i in range(MAX_PRESENCE_CHANNELS):
            ws.send_json(_beat(pk=str(i)))
            ws.receive_json()
        # Beyond the cap the frame is ignored; existing records still work
        ws.send_json(_beat(pk="extra"))
        ws.send_json(_beat(pk="0"))
        assert ws.receive_json()["pk"] == "0"
    assert h.presence.user_count(presence_channel("article", "extra")) == 0


def test_anonymous_socket_never_touches_presence(h: _Harness) -> None:
    with h.client.websocket_connect("/ws?u=0") as ws, pytest.raises(WebSocketDisconnect):
        ws.receive_json()
    assert h.presence.channels() == frozenset()


def test_default_backends_come_from_settings() -> None:
    # Given no explicit backends, the handler resolves presence from settings once
    backend = InMemoryPresence()
    handler = make_ws_handler(ConnectionRegistry(), RealtimeSettings(presence=backend), _Auth())
    client = TestClient(Starlette(routes=[WebSocketRoute("/ws", handler)]))
    with client.websocket_connect("/ws?u=7&name=Ada") as ws:
        ws.send_json(_beat())
        ws.receive_json()
        assert backend.user_count(presence_channel("article", "42")) == 1


def test_presence_payload_shape() -> None:
    assert presence_payload("article", "1", []) == (
        b'{"type":"presence","model":"article","pk":"1","users":[]}'
    )
