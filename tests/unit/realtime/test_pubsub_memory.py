"""Unit tests for hyperadmin.realtime.pubsub (PubSubBackend + InMemoryPubSub).

Covers GitHub #302: publish/subscribe/unsubscribe, fan-out to concurrent
subscribers, channel isolation, cleanup on unsubscribe / cancel, the bounded
queue overflow policy and ``close()`` semantics.
"""

from __future__ import annotations

import asyncio

import pytest

from hyperadmin.realtime import InMemoryPubSub, PubSubBackend

pytestmark = pytest.mark.anyio


async def _next(messages: object, timeout: float = 1.0) -> bytes:
    return await asyncio.wait_for(messages.__anext__(), timeout)  # type: ignore[attr-defined]


def test_in_memory_pubsub_satisfies_protocol() -> None:
    # Given an InMemoryPubSub
    # Then it structurally satisfies the PubSubBackend protocol
    assert isinstance(InMemoryPubSub(), PubSubBackend)


def test_invalid_max_queue_size_rejected() -> None:
    # Given / When a non-positive queue bound is passed
    # Then construction fails fast
    with pytest.raises(ValueError, match="max_queue_size"):
        InMemoryPubSub(max_queue_size=0)


async def test_subscriber_receives_published_message() -> None:
    # Given a subscriber on channel "ch"
    pubsub = InMemoryPubSub()
    async with pubsub.subscribe("ch") as messages:
        # When a message is published to "ch"
        await pubsub.publish("ch", b"hello")

        # Then the subscriber receives it
        assert await _next(messages) == b"hello"


async def test_messages_are_delivered_in_order() -> None:
    # Given a subscriber
    pubsub = InMemoryPubSub()
    async with pubsub.subscribe("ch") as messages:
        # When three messages are published
        for payload in (b"1", b"2", b"3"):
            await pubsub.publish("ch", payload)

        # Then they arrive in publish order
        assert [await _next(messages) for _ in range(3)] == [b"1", b"2", b"3"]


async def test_publish_without_subscribers_is_noop() -> None:
    # Given no subscribers
    pubsub = InMemoryPubSub()

    # When a message is published
    await pubsub.publish("nobody", b"lost")

    # Then nothing is retained for the channel
    assert pubsub.subscriber_count("nobody") == 0


async def test_multiple_subscribers_each_receive_message() -> None:
    # Given two concurrent subscribers on the same channel
    pubsub = InMemoryPubSub()
    async with pubsub.subscribe("ch") as a, pubsub.subscribe("ch") as b:
        assert pubsub.subscriber_count("ch") == 2

        # When one message is published
        await pubsub.publish("ch", b"fan-out")

        # Then every subscriber receives its own copy
        assert await _next(a) == b"fan-out"
        assert await _next(b) == b"fan-out"


async def test_concurrent_consumer_tasks_receive_message() -> None:
    # Given two consumer tasks blocked waiting on the same channel
    pubsub = InMemoryPubSub()
    ready = asyncio.Event()
    entered = 0

    async def consume() -> bytes:
        nonlocal entered
        async with pubsub.subscribe("ch") as messages:
            entered += 1
            if entered == 2:
                ready.set()
            return await _next(messages)

    tasks = [asyncio.create_task(consume()) for _ in range(2)]
    await asyncio.wait_for(ready.wait(), 1.0)

    # When a message is published
    await pubsub.publish("ch", b"wake")

    # Then both tasks return it and both subscriptions are released
    assert await asyncio.gather(*tasks) == [b"wake", b"wake"]
    assert pubsub.subscriber_count("ch") == 0


async def test_channel_isolation() -> None:
    # Given subscribers on ch-A and ch-B
    pubsub = InMemoryPubSub()
    async with pubsub.subscribe("ch-A") as a, pubsub.subscribe("ch-B") as b:
        # When a message is published on ch-A only
        await pubsub.publish("ch-A", b"only-a")
        await pubsub.publish("ch-B", b"only-b")

        # Then each subscriber only sees its own channel's message
        assert await _next(a) == b"only-a"
        assert await _next(b) == b"only-b"
        with pytest.raises(asyncio.TimeoutError):
            await _next(a, timeout=0.05)


async def test_unsubscribe_cleans_up_channel() -> None:
    # Given a subscriber that leaves its context
    pubsub = InMemoryPubSub()
    async with pubsub.subscribe("ch"):
        assert pubsub.subscriber_count("ch") == 1

    # Then the channel entry is removed (no leak)
    assert pubsub.subscriber_count("ch") == 0
    assert pubsub.channels() == frozenset()


async def test_unsubscribe_keeps_other_subscribers() -> None:
    # Given two subscribers, one of which leaves
    pubsub = InMemoryPubSub()
    async with pubsub.subscribe("ch") as stays:
        async with pubsub.subscribe("ch"):
            pass

        # When a message is published afterwards
        await pubsub.publish("ch", b"still-here")

        # Then the remaining subscriber still receives it
        assert pubsub.subscriber_count("ch") == 1
        assert await _next(stays) == b"still-here"


async def test_cancelled_consumer_unsubscribes() -> None:
    # Given a consumer task blocked in ``async for``
    pubsub = InMemoryPubSub()
    subscribed = asyncio.Event()

    async def consume() -> None:
        async with pubsub.subscribe("ch") as messages:
            subscribed.set()
            async for _ in messages:
                pass

    task = asyncio.create_task(consume())
    await asyncio.wait_for(subscribed.wait(), 1.0)
    assert pubsub.subscriber_count("ch") == 1

    # When the task is cancelled
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task

    # Then its subscription is removed
    assert pubsub.subscriber_count("ch") == 0


async def test_overflow_drops_oldest_message() -> None:
    # Given a slow subscriber with a queue bound of 2
    pubsub = InMemoryPubSub(max_queue_size=2)
    async with pubsub.subscribe("ch") as slow, pubsub.subscribe("ch") as fast:
        # When three messages are published without the slow one reading
        for payload in (b"1", b"2", b"3"):
            await pubsub.publish("ch", payload)
            if payload != b"3":
                assert await _next(fast) == payload

        # Then publish never blocks, the oldest is dropped for the slow
        # subscriber, and the fast subscriber is unaffected
        assert [await _next(slow) for _ in range(2)] == [b"2", b"3"]
        assert await _next(fast) == b"3"


async def test_close_ends_active_subscriptions() -> None:
    # Given an active subscriber with a full queue
    pubsub = InMemoryPubSub(max_queue_size=1)
    async with pubsub.subscribe("ch") as messages:
        await pubsub.publish("ch", b"pending")

        # When the backend is closed
        await pubsub.close()

        # Then iteration stops cleanly (and keeps stopping)
        assert [m async for m in messages] == []
        with pytest.raises(StopAsyncIteration):
            await messages.__anext__()

    assert pubsub.channels() == frozenset()


async def test_close_is_idempotent_and_rejects_further_use() -> None:
    # Given a closed backend
    pubsub = InMemoryPubSub()
    await pubsub.close()
    await pubsub.close()

    # Then publish and subscribe are rejected
    with pytest.raises(RuntimeError, match="closed"):
        await pubsub.publish("ch", b"x")
    with pytest.raises(RuntimeError, match="closed"):
        async with pubsub.subscribe("ch"):
            pass
