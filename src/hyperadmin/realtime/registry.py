"""In-memory tracker for active SSE / WebSocket connections.

The registry has two jobs:

1. Observability — let operators / tests inspect how many connections (and
   for which users) are currently open.
2. Shutdown drain — close every open connection once when the FastAPI
   lifespan shuts down, so neither uvicorn ``--reload`` nor a graceful
   restart leaves orphaned tasks.

It is deliberately *not* a pubsub: cross-process fan-out lives behind the
``PubSubBackend`` protocol introduced in Epic 6.2.1's PubSub stories.
"""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Literal

Transport = Literal["sse", "ws"]


@dataclass(frozen=True, eq=False)
class RealtimeConnection:
    """Opaque handle the registry stores for each open connection.

    Equality is identity-based (``eq=False`` keeps the default ``object``
    comparison) so two connections from the same user are tracked as
    separate entries.
    """

    user_id: int
    transport: Transport
    close: Callable[[], Awaitable[None]]


class ConnectionRegistry:
    """Async-safe set of open ``RealtimeConnection`` instances."""

    def __init__(self) -> None:
        self._conns: set[RealtimeConnection] = set()
        self._lock = asyncio.Lock()
        self._closed = False

    async def register(self, conn: RealtimeConnection) -> None:
        async with self._lock:
            if self._closed:
                msg = "ConnectionRegistry is shut down"
                raise RuntimeError(msg)
            self._conns.add(conn)

    async def unregister(self, conn: RealtimeConnection) -> None:
        async with self._lock:
            self._conns.discard(conn)

    def count(self) -> int:
        return len(self._conns)

    def users(self) -> set[int]:
        return {c.user_id for c in self._conns}

    def snapshot(self) -> tuple[RealtimeConnection, ...]:
        """Return a stable snapshot of the live connections."""
        return tuple(self._conns)

    async def close_where(self, predicate: Callable[[RealtimeConnection], bool]) -> int:
        """Close every connection matching ``predicate``.

        Used by the test-only debug router to simulate server-initiated
        drops (one transport, all of one user) without shutting the
        registry down. Returns the number of connections closed. Exceptions
        from individual ``close()`` callbacks are swallowed.
        """
        async with self._lock:
            to_close = [c for c in self._conns if predicate(c)]
            for c in to_close:
                self._conns.discard(c)
        if to_close:
            await asyncio.gather(*(c.close() for c in to_close), return_exceptions=True)
        return len(to_close)

    async def drain(self) -> None:
        """Close every open connection and reject future registrations.

        Idempotent — calling ``drain()`` twice is a no-op the second time.
        Exceptions raised by individual ``close()`` callbacks are swallowed
        so one misbehaving connection cannot block shutdown of the rest.
        """
        async with self._lock:
            if self._closed:
                return
            self._closed = True
            to_close = list(self._conns)
            self._conns.clear()
        if to_close:
            await asyncio.gather(*(c.close() for c in to_close), return_exceptions=True)
