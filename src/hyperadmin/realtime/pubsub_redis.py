"""Redis-backed ``PubSubBackend`` for multi-worker deployments.

Requires the optional extra: ``pip install 'hyper-admin[redis]'``. The
``redis`` package is imported lazily, so importing this module never fails —
constructing ``RedisPubSub`` from a URL without the extra raises an
``ImportError`` that names the extra to install.

Each ``subscribe()`` opens its own Redis ``PUBSUB`` connection and a reader
task that pumps messages into a bounded per-subscriber queue, mirroring the
``InMemoryPubSub`` semantics: the subscription is confirmed by Redis before
the ``async with`` block is entered, a slow consumer drops its **oldest**
pending message instead of blocking, and ``close()`` ends every active
iteration. A Redis error in the reader is re-raised from the iterator.
"""

from __future__ import annotations

import asyncio
import contextlib
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import TYPE_CHECKING, Any, Final, cast

from hyperadmin.realtime.pubsub import DEFAULT_MAX_QUEUE_SIZE

if TYPE_CHECKING:
    from redis.asyncio import Redis
    from redis.asyncio.client import PubSub

DEFAULT_REDIS_URL: Final = "redis://localhost:6379/0"

_CLOSED: Final = object()


def _redis_from_url(url: str) -> Redis:
    try:
        from redis.asyncio import Redis  # noqa: PLC0415 - optional extra, imported lazily
    except ImportError as exc:
        msg = "RedisPubSub requires the 'redis' package. Install it with: pip install 'hyper-admin[redis]'"
        raise ImportError(msg) from exc
    return Redis.from_url(url)


class _RedisSubscription:
    """One subscriber's bounded queue, fed by a reader task, consumed as an async iterator."""

    def __init__(self, maxsize: int) -> None:
        self._queue: asyncio.Queue[object] = asyncio.Queue(maxsize)
        self._done = False

    def push(self, item: object) -> None:
        # Overflow policy (same as InMemoryPubSub): drop the oldest queued message.
        if self._queue.full():
            self._queue.get_nowait()
        self._queue.put_nowait(item)

    def __aiter__(self) -> _RedisSubscription:
        return self

    async def __anext__(self) -> bytes:
        if self._done:
            raise StopAsyncIteration
        item = await self._queue.get()
        if item is _CLOSED:
            self._done = True
            raise StopAsyncIteration
        if isinstance(item, BaseException):
            self._done = True
            raise item
        return cast("bytes", item)


async def _confirm_subscribed(pubsub: PubSub) -> None:
    # SUBSCRIBE is acknowledged asynchronously; wait for the ack so anything
    # published after ``subscribe()`` returns is guaranteed to be delivered.
    while True:
        message = await pubsub.get_message(timeout=None)
        if message is not None and message["type"] == "subscribe":
            return


async def _pump(pubsub: PubSub, sub: _RedisSubscription) -> None:
    try:
        while True:
            message: dict[str, Any] | None = await pubsub.get_message(
                ignore_subscribe_messages=True, timeout=None
            )
            if message is None or message["type"] != "message":
                continue
            data = message["data"]
            # Clients built with ``decode_responses=True`` hand back ``str``.
            sub.push(data.encode() if isinstance(data, str) else data)
    except Exception as exc:
        sub.push(exc)


class RedisPubSub:
    """``PubSubBackend`` backed by Redis ``PUBLISH`` / ``SUBSCRIBE``.

    Pass either a ``url`` (the client is created lazily and closed by
    ``close()``) or an existing ``redis.asyncio.Redis`` ``client`` (owned by
    the caller and left open). Messages are opaque ``bytes``.
    """

    def __init__(
        self,
        url: str = DEFAULT_REDIS_URL,
        *,
        client: Redis | None = None,
        max_queue_size: int = DEFAULT_MAX_QUEUE_SIZE,
    ) -> None:
        if max_queue_size < 1:
            msg = "max_queue_size must be >= 1"
            raise ValueError(msg)
        self._owns_client = client is None
        self._client: Redis = _redis_from_url(url) if client is None else client
        self._max_queue_size = max_queue_size
        self._readers: dict[_RedisSubscription, asyncio.Task[None]] = {}
        self._closed = False

    def _ensure_open(self) -> None:
        if self._closed:
            msg = "RedisPubSub is closed"
            raise RuntimeError(msg)

    async def publish(self, channel: str, message: bytes) -> None:
        self._ensure_open()
        await self._client.publish(channel, message)

    @asynccontextmanager
    async def subscribe(self, channel: str) -> AsyncIterator[AsyncIterator[bytes]]:
        self._ensure_open()
        pubsub = self._client.pubsub()
        try:
            await pubsub.subscribe(channel)
            await _confirm_subscribed(pubsub)
            sub = _RedisSubscription(self._max_queue_size)
            reader = asyncio.create_task(_pump(pubsub, sub))
            self._readers[sub] = reader
            try:
                yield sub
            finally:
                self._readers.pop(sub, None)
                reader.cancel()
                with contextlib.suppress(asyncio.CancelledError):
                    await reader
        finally:
            # Resets and releases the PUBSUB connection (implicitly unsubscribes).
            await pubsub.aclose()

    async def close(self) -> None:
        if self._closed:
            return
        self._closed = True
        for sub, reader in self._readers.items():
            reader.cancel()
            sub.push(_CLOSED)
        if self._owns_client:
            await self._client.aclose()
