"""CRUD-notification subscribe protocol on the realtime WebSocket (#312).

Drives the real ``make_ws_handler`` through Starlette's ``TestClient`` with an
in-memory ``PubSubBackend``.
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any

import pytest
from fastapi import FastAPI
from sqlalchemy.ext.asyncio import create_async_engine
from starlette.applications import Starlette
from starlette.routing import WebSocketRoute
from starlette.testclient import TestClient

from hyperadmin.core.app import Admin
from hyperadmin.core.settings import HyperAdminSettings
from hyperadmin.realtime import (
    ConnectionRegistry,
    InMemoryPubSub,
    RealtimeAction,
    RealtimeEvent,
    RealtimeSettings,
    crud_channel,
)
from hyperadmin.realtime.ws import MAX_NOTIFICATION_CHANNELS, make_ws_handler


@dataclass
class _User:
    id: int


class _Auth:
    async def get_current_user(self, websocket: Any) -> _User | None:
        return _User(id=int(websocket.query_params.get("u", "1")))


class _Harness:
    def __init__(self, allowed: set[str] | None = None, *, with_authorize: bool = True) -> None:
        self.pubsub = InMemoryPubSub()
        self.calls: list[tuple[int, str]] = []
        self.allowed = {"article"} if allowed is None else allowed

        async def authorize(user: Any, model: str) -> bool:
            self.calls.append((user.id, model))
            return model in self.allowed

        handler = make_ws_handler(
            ConnectionRegistry(),
            RealtimeSettings(),
            _Auth(),
            pubsub=self.pubsub,
            authorize=authorize if with_authorize else None,
        )
        self.client = TestClient(Starlette(routes=[WebSocketRoute("/ws", handler)]))
        self.client.__enter__()  # exposes the portal used by publish()

    def publish(self, model: str, pk: Any, action: RealtimeAction, actor: str | None = "7") -> None:
        event = RealtimeEvent(
            model, pk, action, actor_id=actor, actor_name=None if actor is None else "Ada"
        )
        self.client.portal.call(self.pubsub.publish, crud_channel(model), event.to_bytes())  # type: ignore[union-attr]


@pytest.fixture(autouse=True)
def _close_clients():
    clients: list[TestClient] = []
    orig = _Harness.__init__

    def init(self: _Harness, *a: Any, **k: Any) -> None:
        orig(self, *a, **k)
        clients.append(self.client)

    _Harness.__init__ = init  # type: ignore[method-assign]
    yield
    _Harness.__init__ = orig  # type: ignore[method-assign]
    for c in clients:
        c.__exit__(None, None, None)


def _sub(model: str) -> dict[str, str]:
    return {"type": "subscribe", "model": model}


def _wait_subscribed(h: _Harness, ws: Any, model: str = "article") -> None:
    """Two presence round-trips: the second starts after the earlier frames are fully handled."""
    for _ in range(2):
        ws.send_json({"type": "presence", "model": "x", "pk": "1", "mode": "viewing"})
        ws.receive_json()


def test_subscribe_forwards_crud_events() -> None:
    """
    Scenario: a permitted subscription receives crud frames
      Given an authenticated socket subscribed to article
      When  an article is created
      Then  the socket receives a crud frame with model, pk, action and actor_id
    """
    h = _Harness()
    with h.client.websocket_connect("/ws") as ws:
        ws.send_json(_sub("Article"))
        _wait_subscribed(h, ws)
        h.publish("article", 5, RealtimeAction.CREATED)
        msg = ws.receive_json()
    assert msg == {
        "type": "crud",
        "model": "article",
        "pk": "5",
        "action": "created",
        "actor_id": "7",
        "actor": "Ada",
    }


def test_unsubscribe_stops_events_and_unknown_unsubscribe_is_ignored() -> None:
    """
    Scenario: unsubscribe stops forwarding
      Given a socket subscribed to article
      When  it unsubscribes and an article is deleted
      Then  no crud frame arrives
    """
    h = _Harness()
    with h.client.websocket_connect("/ws") as ws:
        ws.send_json({"type": "unsubscribe", "model": "comment"})
        ws.send_json(_sub("article"))
        ws.send_json({"type": "unsubscribe", "model": "article"})
        _wait_subscribed(h, ws)
        h.publish("article", 5, RealtimeAction.DELETED)
        ws.send_json({"type": "presence", "model": "x", "pk": "1", "mode": "viewing"})
        assert ws.receive_json()["type"] == "presence"


@pytest.mark.parametrize(
    "frame",
    [
        "not json",
        "[1]",
        {"type": "subscribe"},
        {"type": "subscribe", "model": ""},
        {"type": "bogus", "model": "article"},
    ],
)
def test_malformed_frames_are_ignored(frame: Any) -> None:
    """
    Scenario: malformed frames create no subscription
      Given a socket
      When  it sends a malformed or unknown frame
      Then  nothing is subscribed and the authorizer is never asked
    """
    h = _Harness()
    with h.client.websocket_connect("/ws") as ws:
        if isinstance(frame, str):
            ws.send_text(frame)
        else:
            ws.send_json(frame)
        _wait_subscribed(h, ws)
    assert h.calls == []


def test_refused_subscriptions_receive_nothing() -> None:
    """
    Scenario: denied or unknown models are silently ignored
      Given the authorizer only permits article
      When  the socket subscribes to comment
      Then  it never receives comment events
    """
    h = _Harness()
    with h.client.websocket_connect("/ws") as ws:
        ws.send_json(_sub("comment"))
        _wait_subscribed(h, ws)
        h.publish("comment", 1, RealtimeAction.CREATED)
        _wait_subscribed(h, ws)
    assert h.calls == [(1, "comment")]


def test_no_authorizer_refuses_everything() -> None:
    """
    Scenario: without an authorizer no subscription is accepted
      Given make_ws_handler without authorize
      When  the socket subscribes to article
      Then  article events are not forwarded
    """
    h = _Harness(with_authorize=False)
    with h.client.websocket_connect("/ws") as ws:
        ws.send_json(_sub("article"))
        _wait_subscribed(h, ws)
        h.publish("article", 1, RealtimeAction.CREATED)
        _wait_subscribed(h, ws)


def test_authorize_is_cached_and_duplicates_ignored() -> None:
    """
    Scenario: authorization is cached per socket and model
      Given a socket subscribed to article
      When  it unsubscribes and subscribes again, then sends a duplicate subscribe
      Then  authorize ran once and only one frame per event arrives
    """
    h = _Harness()
    with h.client.websocket_connect("/ws") as ws:
        ws.send_json(_sub("article"))
        ws.send_json({"type": "unsubscribe", "model": "article"})
        ws.send_json(_sub("article"))
        ws.send_json(_sub("article"))
        _wait_subscribed(h, ws)
        h.publish("article", 1, RealtimeAction.UPDATED)
        assert ws.receive_json()["pk"] == "1"
        _wait_subscribed(h, ws)
    assert h.calls == [(1, "article")]


def test_deeply_nested_frame_does_not_crash_the_socket() -> None:
    """
    Scenario: a pathologically nested frame is ignored
      Given a socket
      When  it sends a frame nested deeper than the JSON parser allows
      Then  the socket stays open and keeps answering
    """
    h = _Harness()
    with h.client.websocket_connect("/ws") as ws:
        ws.send_text("[" * 200_000)
        _wait_subscribed(h, ws)
    assert h.calls == []


def test_authorize_failure_is_treated_as_denied() -> None:
    """
    Scenario: an authorizer error denies the subscription without closing the socket
      Given an authorizer that raises
      When  the socket subscribes to article
      Then  the socket stays open and receives no article events
    """
    pubsub = InMemoryPubSub()

    async def boom(user: Any, model: str) -> bool:
        raise RuntimeError("db down")

    handler = make_ws_handler(
        ConnectionRegistry(), RealtimeSettings(), _Auth(), pubsub=pubsub, authorize=boom
    )
    client = TestClient(Starlette(routes=[WebSocketRoute("/ws", handler)]))
    with client, client.websocket_connect("/ws") as ws:
        ws.send_json(_sub("article"))
        for _ in range(2):
            ws.send_json({"type": "presence", "model": "x", "pk": "1", "mode": "viewing"})
            assert ws.receive_json()["type"] == "presence"


def test_denials_are_not_cached() -> None:
    """
    Scenario: denied names do not accumulate per-socket state
      Given the authorizer only permits article
      When  the socket subscribes to the same unknown model twice
      Then  authorize is consulted each time, and grants stay cached
    """
    h = _Harness()
    with h.client.websocket_connect("/ws") as ws:
        ws.send_json(_sub("ghost"))
        ws.send_json(_sub("ghost"))
        _wait_subscribed(h, ws)
    assert h.calls == [(1, "ghost"), (1, "ghost")]


def test_subscription_cap() -> None:
    """
    Scenario: a socket follows at most MAX_NOTIFICATION_CHANNELS models
      Given a socket at the cap
      When  it subscribes to one more model
      Then  the extra model is refused
    """
    models = {f"m{i}" for i in range(MAX_NOTIFICATION_CHANNELS + 1)}
    h = _Harness(allowed=models)
    with h.client.websocket_connect("/ws") as ws:
        for i in range(MAX_NOTIFICATION_CHANNELS + 1):
            ws.send_json(_sub(f"m{i}"))
        _wait_subscribed(h, ws)
        h.publish(f"m{MAX_NOTIFICATION_CHANNELS}", 1, RealtimeAction.CREATED)
        h.publish("m0", 2, RealtimeAction.CREATED)
        assert ws.receive_json()["model"] == "m0"
    assert (1, f"m{MAX_NOTIFICATION_CHANNELS}") not in h.calls


def test_malformed_pubsub_payload_is_skipped() -> None:
    """
    Scenario: a garbage pubsub payload is skipped
      Given a subscribed socket
      When  a non-event payload then a real event are published
      Then  only the real event is forwarded
    """
    h = _Harness()
    with h.client.websocket_connect("/ws") as ws:
        ws.send_json(_sub("article"))
        _wait_subscribed(h, ws)
        h.client.portal.call(h.pubsub.publish, crud_channel("article"), b"garbage")  # type: ignore[union-attr]
        time.sleep(0.05)
        h.publish("article", 9, RealtimeAction.CREATED, actor=None)
        msg = ws.receive_json()
    assert msg["pk"] == "9"
    assert msg["actor_id"] is None


def _admin_with_notifications(
    checker: Any, models: set[str], *, with_realtime: bool = True
) -> Admin:
    admin = Admin(
        app=FastAPI(),
        engine=create_async_engine("sqlite+aiosqlite://"),
        settings=HyperAdminSettings(create_tables=False),
        realtime=RealtimeSettings(pubsub=InMemoryPubSub()) if with_realtime else None,
        permission_checker=checker,
    )
    admin._notification_models = models
    return admin


class _Checker:
    async def has_permission(self, user: Any, codename: str) -> bool:
        return codename == "view_article"


@pytest.mark.anyio
async def test_admin_authorize_requires_enabled_model_and_view_permission() -> None:
    """
    Scenario: Admin authorizes on enabled set plus view permission
      Given notifications enabled for article and comment, view only on article
      When  subscriptions are authorized
      Then  article passes; comment (no permission) and note (not enabled) fail
    """
    admin = _admin_with_notifications(_Checker(), {"article", "comment"})
    assert await admin._authorize_notification_subscription(_User(1), "Article") is True
    assert await admin._authorize_notification_subscription(_User(1), "comment") is False
    assert await admin._authorize_notification_subscription(_User(1), "note") is False


@pytest.mark.anyio
async def test_admin_authorize_without_permission_checker() -> None:
    """
    Scenario: auth disabled allows enabled models
      Given no permission checker
      When  an enabled model is authorized
      Then  it is allowed
    """
    admin = _admin_with_notifications(None, {"article"})
    assert await admin._authorize_notification_subscription(_User(1), "article") is True
