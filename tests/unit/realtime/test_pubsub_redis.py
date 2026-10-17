"""Unit tests for hyperadmin.realtime.pubsub_redis (RedisPubSub).

Covers GitHub #304 / #305 against an in-process fake of ``redis.asyncio`` — no
live Redis needed: publish routing, subscribe confirmation and delivery,
unsubscribe cleanup, error propagation, channel isolation, overflow, ``close()``
semantics and the lazy-import guard for the ``[redis]`` extra.
"""

from __future__ import annotations

import asyncio
import sys
from typing import Any
from unittest.mock import AsyncMock

import pytest
from redis.asyncio import Redis
from redis.exceptions import ConnectionError as RedisConnectionError

from hyperadmin.realtime import PubSubBackend
from hyperadmin.realtime.pubsub_redis import RedisPubSub

pytestmark = pytest.mark.anyio


async def _next(messages: object, timeout: float = 1.0) -> bytes:
    return await asyncio.wait_for(messages.__anext__(), timeout)  # type: ignore[attr-defined]


class FakePubSub:
    """Minimal stand-in for ``redis.asyncio.client.PubSub``."""

    def __init__(self, server: FakeRedis) -> None:
        self._server = server
        self.inbox: asyncio.Queue[Any] = asyncio.Queue()
        self.channels: set[str] = set()
        self.closed = False

    async def subscribe(self, channel: str) -> None:
        if self._server.subscribe_error is not None:
            raise self._server.subscribe_error
        self.channels.add(channel)
        # Real Redis may interleave a nil read before the ack; exercise that path.
        self.inbox.put_nowait(None)
        self.inbox.put_nowait({"type": "subscribe", "channel": channel.encode(), "data": 1})

    async def get_message(
        self, ignore_subscribe_messages: bool = False, timeout: float | None = 0.0
    ) -> dict[str, Any] | None:
        assert timeout is None
        item = await self.inbox.get()
        if isinstance(item, Exception):
            raise item
        if ignore_subscribe_messages and item is not None and item["type"] == "subscribe":
            return None
        return item

    async def aclose(self) -> None:
        self.closed = True
        self.channels.clear()


class FakeRedis:
    """Minimal stand-in for ``redis.asyncio.Redis`` routing PUBLISH to fake PUBSUBs."""

    def __init__(self) -> None:
        self.pubsubs: list[FakePubSub] = []
        self.closed = False
        self.subscribe_error: Exception | None = None

    def pubsub(self) -> FakePubSub:
        ps = FakePubSub(self)
        self.pubsubs.append(ps)
        return ps

    async def publish(self, channel: str, message: bytes | str) -> int:
        receivers = [ps for ps in self.pubsubs if channel in ps.channels]
        for ps in receivers:
            ps.inbox.put_nowait({"type": "message", "channel": channel.encode(), "data": message})
        return len(receivers)

    async def aclose(self) -> None:
        self.closed = True


@pytest.fixture
def fake() -> FakeRedis:
    return FakeRedis()


@pytest.fixture
def backend(fake: FakeRedis) -> RedisPubSub:
    return RedisPubSub(client=fake)  # type: ignore[arg-type]


def test_redis_pubsub_satisfies_protocol(backend: RedisPubSub) -> None:
    # Given a RedisPubSub
    # Then it structurally satisfies the PubSubBackend protocol
    assert isinstance(backend, PubSubBackend)


def test_invalid_max_queue_size_rejected(fake: FakeRedis) -> None:
    # Given / When a non-positive queue bound is passed
    # Then construction fails fast
    with pytest.raises(ValueError, match="max_queue_size"):
        RedisPubSub(client=fake, max_queue_size=0)  # type: ignore[arg-type]


def test_missing_redis_extra_raises_helpful_import_error(monkeypatch: pytest.MonkeyPatch) -> None:
    # Given the redis package is not installed
    monkeypatch.setitem(sys.modules, "redis.asyncio", None)

    # When a RedisPubSub is built from a URL
    # Then the ImportError names the extra to install
    with pytest.raises(ImportError, match=r"hyper-admin\[redis\]"):
        RedisPubSub("redis://localhost:6379/0")


async def test_url_builds_owned_client_closed_on_close() -> None:
    # Given a RedisPubSub built from a URL (no connection is opened yet)
    backend = RedisPubSub("redis://example.invalid:6379/3")
    client = backend._client
    assert isinstance(client, Redis)
    client.aclose = AsyncMock()  # type: ignore[method-assign]

    # When it is closed
    await backend.close()

    # Then the client it created is closed too
    client.aclose.assert_awaited_once()


async def test_publish_calls_redis_publish_on_channel() -> None:
    # Given a RedisPubSub over a mocked client
    client = AsyncMock()
    backend = RedisPubSub(client=client)

    # When a message is published
    await backend.publish("crud:article", b"payload")

    # Then redis PUBLISH is called on that channel with the raw bytes
    client.publish.assert_awaited_once_with("crud:article", b"payload")


async def test_subscriber_receives_published_messages_in_order(backend: RedisPubSub) -> None:
    # Given a subscriber on "ch"
    async with backend.subscribe("ch") as messages:
        # When messages are published to "ch"
        for payload in (b"1", b"2", b"3"):
            await backend.publish("ch", payload)

        # Then they arrive in publish order
        assert [await _next(messages) for _ in range(3)] == [b"1", b"2", b"3"]


async def test_non_message_frames_are_skipped(backend: RedisPubSub, fake: FakeRedis) -> None:
    # Given a subscriber
    async with backend.subscribe("ch") as messages:
        # When Redis delivers a nil read and a non-message frame before a message
        inbox = fake.pubsubs[0].inbox
        inbox.put_nowait(None)
        inbox.put_nowait({"type": "pong", "channel": None, "data": b""})
        await backend.publish("ch", b"real")

        # Then only the message payload is yielded
        assert await _next(messages) == b"real"


async def test_str_payloads_are_encoded(backend: RedisPubSub) -> None:
    # Given a client configured with decode_responses=True (payloads come back as str)
    async with backend.subscribe("ch") as messages:
        # When a str payload is delivered
        await backend._client.publish("ch", "héllo")

        # Then the subscriber still receives bytes
        assert await _next(messages) == "héllo".encode()


async def test_unsubscribe_closes_redis_pubsub(backend: RedisPubSub, fake: FakeRedis) -> None:
    # Given an active subscription
    async with backend.subscribe("ch"):
        ps = fake.pubsubs[0]
        assert ps.channels == {"ch"}
        assert len(backend._readers) == 1

    # When the block exits
    # Then the PUBSUB connection is closed and the reader task is gone
    assert ps.closed
    assert ps.channels == set()
    assert backend._readers == {}
    # And later publishes reach nobody
    assert await fake.publish("ch", b"late") == 0


async def test_cancelled_consumer_cleans_up(backend: RedisPubSub, fake: FakeRedis) -> None:
    # Given a consumer task blocked waiting for messages
    entered = asyncio.Event()

    async def consume() -> None:
        async with backend.subscribe("ch") as messages:
            entered.set()
            async for _ in messages:
                pass

    task = asyncio.create_task(consume())
    await entered.wait()

    # When the consumer is cancelled
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task

    # Then the subscription is torn down
    assert fake.pubsubs[0].closed
    assert backend._readers == {}


async def test_publish_connection_error_propagates() -> None:
    # Given a client whose PUBLISH fails
    client = AsyncMock()
    client.publish.side_effect = RedisConnectionError("connection refused")
    backend = RedisPubSub(client=client)

    # When / Then publishing raises the Redis error
    with pytest.raises(RedisConnectionError, match="connection refused"):
        await backend.publish("ch", b"x")


async def test_subscribe_connection_error_propagates_and_releases(
    backend: RedisPubSub, fake: FakeRedis
) -> None:
    # Given SUBSCRIBE fails
    fake.subscribe_error = RedisConnectionError("connection refused")

    # When / Then entering the subscription raises, and the PUBSUB is still released
    with pytest.raises(RedisConnectionError):
        async with backend.subscribe("ch"):
            pytest.fail("subscription must not be entered")
    assert fake.pubsubs[0].closed


async def test_reader_connection_error_raised_from_iterator(
    backend: RedisPubSub, fake: FakeRedis
) -> None:
    # Given an active subscription with one queued message
    async with backend.subscribe("ch") as messages:
        await backend.publish("ch", b"before")
        # When the connection drops while reading
        fake.pubsubs[0].inbox.put_nowait(RedisConnectionError("lost"))

        # Then pending messages are delivered first, then the error is raised
        assert await _next(messages) == b"before"
        with pytest.raises(RedisConnectionError, match="lost"):
            await _next(messages)
        # And the iterator is exhausted afterwards
        with pytest.raises(StopAsyncIteration):
            await _next(messages)


async def test_channels_are_independent(backend: RedisPubSub) -> None:
    # Given subscribers on two channels
    async with backend.subscribe("a") as on_a, backend.subscribe("b") as on_b:
        # When each channel gets its own message
        await backend.publish("a", b"for-a")
        await backend.publish("b", b"for-b")

        # Then each subscriber only sees its own channel
        assert await _next(on_a) == b"for-a"
        assert await _next(on_b) == b"for-b"
        with pytest.raises(asyncio.TimeoutError):
            await _next(on_a, timeout=0.05)


async def test_fan_out_to_multiple_subscribers(backend: RedisPubSub) -> None:
    # Given two subscribers on the same channel
    async with backend.subscribe("ch") as first, backend.subscribe("ch") as second:
        # When one message is published
        await backend.publish("ch", b"both")

        # Then both receive it
        assert await _next(first) == b"both"
        assert await _next(second) == b"both"


async def test_slow_consumer_drops_oldest(fake: FakeRedis) -> None:
    # Given a subscriber with room for two messages
    backend = RedisPubSub(client=fake, max_queue_size=2)  # type: ignore[arg-type]
    async with backend.subscribe("ch") as messages:
        # When three messages arrive before it reads
        for payload in (b"1", b"2", b"3"):
            await backend.publish("ch", payload)
        for _ in range(10):
            await asyncio.sleep(0)

        # Then the oldest one was dropped
        assert [await _next(messages) for _ in range(2)] == [b"2", b"3"]


async def test_close_ends_iteration_and_rejects_use(backend: RedisPubSub, fake: FakeRedis) -> None:
    # Given an active subscription
    async with backend.subscribe("ch") as messages:
        # When the backend is closed (twice — idempotent)
        await backend.close()
        await backend.close()

        # Then iteration ends
        with pytest.raises(StopAsyncIteration):
            await _next(messages)
        with pytest.raises(StopAsyncIteration):
            await _next(messages)

    # And further use is rejected
    with pytest.raises(RuntimeError, match="closed"):
        await backend.publish("ch", b"x")
    with pytest.raises(RuntimeError, match="closed"):
        async with backend.subscribe("ch"):
            pytest.fail("subscription must not be entered")
    # And an injected client is left open for its owner
    assert not fake.closed
