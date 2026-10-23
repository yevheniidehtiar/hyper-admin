"""WebSocket endpoint for the real-time MVP.

Rejects a handshake from a foreign ``Origin`` before accepting it (cross-site
WebSocket hijacking: the browser sends the admin's cookies with any page's
handshake), then accepts, enforces auth inside the handler (Starlette's
``BaseHTTPMiddleware`` and FastAPI route dependencies do not run on WS scope),
and exchanges ping/pong heartbeats.

Presence over the same socket
-----------------------------
The browser keeps "who is viewing / editing this record" alive by sending a JSON
text frame every few seconds (and once on page load)::

    {"type": "presence", "model": "article", "pk": "42", "mode": "editing"}

``mode`` is ``"viewing"``, ``"editing"`` or ``"leave"`` (the user navigated
away; also implied by closing the socket). ``model`` and ``pk`` are non-empty
strings (``pk`` may also be an integer). Frames with another ``type`` (reserved
for notifications) and malformed frames are ignored.

On every presence frame the server (1) updates the ``PresenceBackend`` — the
entry's TTL is refreshed, so a tab that disappears without a close simply
expires — and (2) publishes the record's full roster on the ``PubSubBackend``
channel ``presence_channel(model, pk)``. Each socket that has sent a presence
frame for that record is subscribed to the channel and receives the roster as a
text frame::

    {
        "type": "presence",
        "model": "article",
        "pk": "42",
        "users": [
            {
                "user_id": "7",
                "display_name": "Ada",
                "mode": "editing",
                "since": "2026-10-23T09:00:00+00:00",
                "last_seen": "2026-10-23T09:00:15+00:00",
            }
        ],
    }

``users`` lists *every* live user on the record, the sender included, oldest
first, and is empty once the last user leaves. Clients drop their own
``user_id`` when rendering. A socket may follow at most ``MAX_PRESENCE_CHANNELS``
records at once.

Limitations: when a user holds two tabs on one record, closing one removes the
user until the other tab's next heartbeat; presence is not authorised per model
(any authenticated admin user may follow any record).
"""

from __future__ import annotations

import asyncio
import contextlib
import json
import logging
from collections.abc import Awaitable, Callable, Hashable
from dataclasses import dataclass
from typing import Any, Final

from starlette.requests import HTTPConnection
from starlette.websockets import WebSocket, WebSocketDisconnect, WebSocketState

from hyperadmin.realtime.config import RealtimeSettings
from hyperadmin.realtime.presence import (
    PresenceBackend,
    PresenceEntry,
    PresenceMode,
    presence_channel,
)
from hyperadmin.realtime.pubsub import InMemoryPubSub, PubSubBackend
from hyperadmin.realtime.registry import ConnectionRegistry, RealtimeConnection

logger = logging.getLogger("hyperadmin.realtime.ws")

WS_CLOSE_UNAUTHORIZED = 4401
WS_CLOSE_GOING_AWAY = 1001

MAX_PRESENCE_CHANNELS: Final = 20
_MAX_FIELD_LEN: Final = 200
_PRESENCE_MODES: Final = ("viewing", "editing")


def make_ws_handler(
    registry: ConnectionRegistry,
    settings: RealtimeSettings,
    auth_backend: Any,
    origin_allowed: Callable[[HTTPConnection], bool] | None = None,
    presence: PresenceBackend | None = None,
    pubsub: PubSubBackend | None = None,
) -> Callable[[WebSocket], Awaitable[None]]:
    """Return a Starlette WebSocket handler bound to the supplied collaborators.

    ``auth_backend`` must implement ``get_current_user(websocket)`` returning
    a user, or ``None`` for anonymous callers. The connection is keyed on
    ``websocket.state.user_key`` when the backend sets it (the bridge does),
    else on ``user.id`` (built-in auth).

    ``origin_allowed`` vets the handshake before it is accepted and before any
    auth runs; a refused handshake is rejected (closed while still connecting)
    with ``WS_CLOSE_UNAUTHORIZED``.

    ``presence`` defaults to ``settings.resolve_presence()`` (resolved once, so
    every socket shares one backend) and ``pubsub`` to a process-local
    ``InMemoryPubSub``.
    """
    presence = presence if presence is not None else settings.resolve_presence()
    pubsub = pubsub if pubsub is not None else InMemoryPubSub()

    async def ws_endpoint(websocket: WebSocket) -> None:
        if origin_allowed is not None and not origin_allowed(websocket):
            # Closing before ``accept()`` refuses the handshake (HTTP 403 under
            # uvicorn): a cross-site page never sees ``onopen`` fire.
            await websocket.close(code=WS_CLOSE_UNAUTHORIZED)
            return
        await websocket.accept()
        user = await auth_backend.get_current_user(websocket) if auth_backend else None
        if user is None:
            await websocket.close(code=WS_CLOSE_UNAUTHORIZED)
            return
        user_key: Hashable = getattr(websocket.state, "user_key", None)
        if user_key is None:
            user_key = user.id

        async def _close() -> None:
            if websocket.client_state != WebSocketState.DISCONNECTED:
                with contextlib.suppress(RuntimeError):
                    await websocket.close(code=WS_CLOSE_GOING_AWAY)

        conn = RealtimeConnection(user_id=user_key, transport="ws", close=_close)
        try:
            await registry.register(conn)
        except RuntimeError:
            await websocket.close(code=WS_CLOSE_GOING_AWAY)
            return

        session = _PresenceSession(
            websocket, presence, pubsub, str(user_key), _display_name(user, user_key)
        )
        websocket.state.presence_session = session
        heartbeat = asyncio.create_task(_heartbeat_loop(websocket, settings))
        try:
            await _receive_loop(websocket)
        except WebSocketDisconnect:
            pass
        finally:
            heartbeat.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await heartbeat
            await session.close()
            await registry.unregister(conn)
            if websocket.client_state != WebSocketState.DISCONNECTED:
                with contextlib.suppress(RuntimeError):
                    await websocket.close()

    return ws_endpoint


async def _heartbeat_loop(websocket: WebSocket, settings: RealtimeSettings) -> None:
    """Send a zero-byte frame at the configured interval until cancelled."""
    while True:
        await asyncio.sleep(settings.heartbeat_interval)
        if websocket.application_state != WebSocketState.CONNECTED:
            return
        with contextlib.suppress(RuntimeError, WebSocketDisconnect):
            await websocket.send_bytes(b"")


async def _receive_loop(websocket: WebSocket) -> None:
    """Read frames until the peer disconnects, routing text frames to the presence session."""
    session: _PresenceSession = websocket.state.presence_session
    while True:
        message = await websocket.receive()
        if message["type"] == "websocket.disconnect":
            return
        text = message.get("text")
        if text is not None:
            await session.handle(text)


def _display_name(user: Any, user_key: Hashable) -> str:
    for attr in ("display_name", "username", "email", "name"):
        value = getattr(user, attr, None)
        if isinstance(value, str) and value:
            return value
    return str(user_key)


def presence_payload(model: str, pk: str, entries: list[PresenceEntry]) -> bytes:
    """Serialise a record's roster for the PubSub channel (see module docstring)."""
    return json.dumps(
        {
            "type": "presence",
            "model": model,
            "pk": pk,
            "users": [
                {
                    "user_id": e.user_id,
                    "display_name": e.display_name,
                    "mode": e.mode,
                    "since": e.since.isoformat(),
                    "last_seen": e.last_seen.isoformat(),
                }
                for e in entries
            ],
        },
        separators=(",", ":"),
    ).encode()


def _valid_field(value: object) -> str | None:
    if isinstance(value, int) and not isinstance(value, bool):
        value = str(value)
    if isinstance(value, str) and 0 < len(value) <= _MAX_FIELD_LEN:
        return value
    return None


@dataclass(frozen=True, eq=False)
class _Follow:
    """One followed record: its fan-out subscription and forwarding task."""

    model: str
    pk: str
    stack: contextlib.AsyncExitStack
    task: asyncio.Task[None]


class _PresenceSession:
    """Presence state of one socket: the records it follows and their fan-out tasks."""

    def __init__(
        self,
        websocket: WebSocket,
        presence: PresenceBackend,
        pubsub: PubSubBackend,
        user_id: str,
        display_name: str,
    ) -> None:
        self._ws = websocket
        self._presence = presence
        self._pubsub = pubsub
        self._user_id = user_id
        self._display_name = display_name
        self._follows: dict[str, _Follow] = {}

    async def handle(self, text: str) -> None:
        try:
            data = json.loads(text)
        except ValueError:
            return
        if not isinstance(data, dict) or data.get("type") != "presence":
            return
        model = _valid_field(data.get("model"))
        pk = _valid_field(data.get("pk"))
        mode = data.get("mode")
        if model is None or pk is None:
            return
        channel = presence_channel(model, pk)
        if mode == "leave":
            await self._leave(channel)
        elif mode in _PRESENCE_MODES:
            await self._beat(channel, model, pk, mode)

    async def _beat(self, channel: str, model: str, pk: str, mode: PresenceMode) -> None:
        if channel not in self._follows:
            if len(self._follows) >= MAX_PRESENCE_CHANNELS:
                return
            # Subscribe before publishing so the sender sees its own roster.
            stack = contextlib.AsyncExitStack()
            messages = await stack.enter_async_context(self._pubsub.subscribe(channel))
            task = asyncio.create_task(self._forward(messages))
            self._follows[channel] = _Follow(model, pk, stack, task)
        await self._presence.set_presence(
            channel, self._user_id, display_name=self._display_name, mode=mode
        )
        await self._publish(channel, model, pk)

    async def _leave(self, channel: str) -> None:
        follow = self._follows.get(channel)
        if follow is None:
            return
        # Unsubscribe first so the roster below is sent exactly once, directly.
        await self._unfollow(channel)
        await self._presence.remove_presence(channel, self._user_id)
        payload = await self._publish(channel, follow.model, follow.pk)
        with contextlib.suppress(RuntimeError, WebSocketDisconnect):
            await self._ws.send_text(payload.decode())

    async def _unfollow(self, channel: str) -> None:
        follow = self._follows.pop(channel)
        follow.task.cancel()
        await follow.stack.aclose()

    async def _publish(self, channel: str, model: str, pk: str) -> bytes:
        entries = await self._presence.get_presence(channel)
        payload = presence_payload(model, pk, entries)
        await self._pubsub.publish(channel, payload)
        return payload

    async def _forward(self, messages: Any) -> None:
        with contextlib.suppress(RuntimeError, WebSocketDisconnect):
            async for payload in messages:
                await self._ws.send_text(payload.decode())

    async def close(self) -> None:
        """Remove this socket's presence everywhere and tell the remaining viewers."""
        for channel, follow in list(self._follows.items()):
            await self._unfollow(channel)
            with contextlib.suppress(Exception):
                await self._presence.remove_presence(channel, self._user_id)
                await self._publish(channel, follow.model, follow.pk)
