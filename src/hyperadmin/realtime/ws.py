"""WebSocket endpoint for the real-time MVP.

Accepts the handshake, enforces session auth inside the handler (Starlette's
``BaseHTTPMiddleware`` does not run on WS scope), and exchanges ping/pong
heartbeats. No business payload — that arrives once the PubSub layer is
plugged in.
"""

from __future__ import annotations

import asyncio
import contextlib
import logging
from collections.abc import Awaitable, Callable
from typing import Any

from starlette.websockets import WebSocket, WebSocketDisconnect, WebSocketState

from hyperadmin.realtime.config import RealtimeSettings
from hyperadmin.realtime.registry import ConnectionRegistry, RealtimeConnection

logger = logging.getLogger("hyperadmin.realtime.ws")

WS_CLOSE_UNAUTHORIZED = 4401
WS_CLOSE_GOING_AWAY = 1001


def make_ws_handler(
    registry: ConnectionRegistry,
    settings: RealtimeSettings,
    auth_backend: Any,
) -> Callable[[WebSocket], Awaitable[None]]:
    """Return a Starlette WebSocket handler bound to the supplied collaborators.

    ``auth_backend`` must implement ``get_current_user(scope)`` returning a
    user object with an ``id`` attribute, or ``None`` for anonymous callers.
    """

    async def ws_endpoint(websocket: WebSocket) -> None:
        await websocket.accept()
        user = await auth_backend.get_current_user(websocket) if auth_backend else None
        if user is None:
            await websocket.close(code=WS_CLOSE_UNAUTHORIZED)
            return

        async def _close() -> None:
            if websocket.client_state != WebSocketState.DISCONNECTED:
                with contextlib.suppress(RuntimeError):
                    await websocket.close(code=WS_CLOSE_GOING_AWAY)

        conn = RealtimeConnection(user_id=user.id, transport="ws", close=_close)
        try:
            await registry.register(conn)
        except RuntimeError:
            await websocket.close(code=WS_CLOSE_GOING_AWAY)
            return

        heartbeat = asyncio.create_task(_heartbeat_loop(websocket, settings))
        try:
            await _receive_loop(websocket)
        except WebSocketDisconnect:
            pass
        finally:
            heartbeat.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await heartbeat
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
    """Drain incoming frames so the connection stays alive.

    The MVP does not interpret client messages — we only need to keep
    awaiting so that ``WebSocketDisconnect`` propagates promptly when the
    peer goes away.
    """
    while True:
        await websocket.receive()
