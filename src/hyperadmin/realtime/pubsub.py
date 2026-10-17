"""Publish/subscribe fan-out for real-time features.

``PubSubBackend`` is the small, stable contract every backend implements
(``InMemoryPubSub`` here, ``RedisPubSub`` in the ``[redis]`` extra). Messages
are opaque ``bytes``; serialisation belongs to the event layer above.

Usage::

    async with backend.subscribe("crud:article") as messages:
        async for payload in messages:
            ...

The subscription is registered when the ``async with`` block is entered, so
anything published afterwards is delivered. Leaving the block — normally, by
exception or by task cancellation — unsubscribes. ``close()`` ends every
active iteration and rejects further ``publish()`` / ``subscribe()`` calls.
"""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from contextlib import AbstractAsyncContextManager, asynccontextmanager
from typing import Final, Protocol, cast, runtime_checkable

DEFAULT_MAX_QUEUE_SIZE: Final = 100

_CLOSED: Final = object()


@runtime_checkable
class PubSubBackend(Protocol):
    """Channel-based fan-out of ``bytes`` messages."""

    async def publish(self, channel: str, message: bytes) -> None:
        """Deliver ``message`` to every current subscriber of ``channel``."""

    def subscribe(self, channel: str) -> AbstractAsyncContextManager[AsyncIterator[bytes]]:
        """Subscribe to ``channel``; the context yields an async iterator of messages."""
        raise NotImplementedError

    async def close(self) -> None:
        """End all subscriptions and release resources. Idempotent."""


class _Subscription:
    """One subscriber's bounded queue, consumed as an async iterator."""

    def __init__(self, maxsize: int) -> None:
        self._queue: asyncio.Queue[object] = asyncio.Queue(maxsize)
        self._done = False

    def push(self, item: object) -> None:
        # Overflow policy: drop the oldest queued message so a slow consumer
        # never blocks the publisher or other subscribers.
        if self._queue.full():
            self._queue.get_nowait()
        self._queue.put_nowait(item)

    def __aiter__(self) -> _Subscription:
        return self

    async def __anext__(self) -> bytes:
        if self._done:
            raise StopAsyncIteration
        item = await self._queue.get()
        if item is _CLOSED:
            self._done = True
            raise StopAsyncIteration
        return cast("bytes", item)


class InMemoryPubSub:
    """Single-process ``PubSubBackend`` backed by one ``asyncio.Queue`` per subscriber.

    Zero-config default for single-worker deployments; messages do not cross
    process boundaries. Each subscriber gets its own queue bounded by
    ``max_queue_size``. When a subscriber falls behind and its queue is full,
    the **oldest** pending message for that subscriber is dropped — publishing
    never blocks and other subscribers are unaffected.
    """

    def __init__(self, max_queue_size: int = DEFAULT_MAX_QUEUE_SIZE) -> None:
        if max_queue_size < 1:
            msg = "max_queue_size must be >= 1"
            raise ValueError(msg)
        self._max_queue_size = max_queue_size
        self._channels: dict[str, set[_Subscription]] = {}
        self._closed = False

    def _ensure_open(self) -> None:
        if self._closed:
            msg = "InMemoryPubSub is closed"
            raise RuntimeError(msg)

    async def publish(self, channel: str, message: bytes) -> None:
        self._ensure_open()
        for sub in self._channels.get(channel, ()):
            sub.push(message)

    @asynccontextmanager
    async def subscribe(self, channel: str) -> AsyncIterator[AsyncIterator[bytes]]:
        self._ensure_open()
        sub = _Subscription(self._max_queue_size)
        self._channels.setdefault(channel, set()).add(sub)
        try:
            yield sub
        finally:
            subs = self._channels.get(channel)
            if subs is not None:
                subs.discard(sub)
                if not subs:
                    del self._channels[channel]

    async def close(self) -> None:
        if self._closed:
            return
        self._closed = True
        for subs in self._channels.values():
            for sub in subs:
                sub.push(_CLOSED)

    def subscriber_count(self, channel: str) -> int:
        """Number of active subscribers on ``channel`` (observability / tests)."""
        return len(self._channels.get(channel, ()))

    def channels(self) -> frozenset[str]:
        """Channels that currently have at least one subscriber."""
        return frozenset(self._channels)
