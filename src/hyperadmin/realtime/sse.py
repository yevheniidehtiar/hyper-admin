"""Server-Sent Events endpoint for the real-time MVP.

Holds the connection open with periodic ``:keepalive`` comments. Carries no
business payload — fan-out lives in the PubSub stories.
"""

from __future__ import annotations

import asyncio
import logging
from collections.abc import AsyncIterator, Awaitable, Callable

from starlette.requests import Request
from starlette.responses import Response, StreamingResponse

from hyperadmin.realtime.config import RealtimeSettings
from hyperadmin.realtime.registry import ConnectionRegistry, RealtimeConnection

logger = logging.getLogger("hyperadmin.realtime.sse")

_KEEPALIVE_FRAME = b":keepalive\n\n"
_DISCONNECT_POLL = 1.0  # seconds — how often to check for client disconnect


def make_sse_handler(
    registry: ConnectionRegistry,
    settings: RealtimeSettings,
) -> Callable[[Request], Awaitable[Response]]:
    """Return a Starlette handler bound to the supplied registry + settings."""

    async def sse_endpoint(request: Request) -> Response:
        user = getattr(request.state, "user", None)
        if user is None:
            return Response(status_code=401)

        stop = asyncio.Event()

        async def _close() -> None:
            stop.set()

        conn = RealtimeConnection(user_id=user.id, transport="sse", close=_close)

        async def event_stream() -> AsyncIterator[bytes]:
            try:
                await registry.register(conn)
            except RuntimeError:
                # Server is draining — don't enroll, just emit one frame and exit
                # so the client sees a clean stream end rather than a 500.
                yield _KEEPALIVE_FRAME
                return
            try:
                # First frame primes the EventSource state immediately so the
                # browser's `onopen` fires without waiting for the heartbeat.
                yield _KEEPALIVE_FRAME
                while True:
                    timeout = settings.heartbeat_interval
                    elapsed = 0.0
                    # Poll for client disconnect at a finer interval than the
                    # heartbeat so we react quickly to navigation / tab close.
                    while elapsed < timeout:
                        if stop.is_set() or await request.is_disconnected():
                            return
                        step = min(_DISCONNECT_POLL, timeout - elapsed)
                        await asyncio.sleep(step)
                        elapsed += step
                    yield _KEEPALIVE_FRAME
            finally:
                await registry.unregister(conn)

        return StreamingResponse(
            event_stream(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache, no-transform",
                "X-Accel-Buffering": "no",
            },
        )

    return sse_endpoint
