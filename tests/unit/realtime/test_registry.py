"""Unit tests for hyperadmin.realtime.registry.ConnectionRegistry.

Each test corresponds 1:1 to a BDD scenario in
docs/specs/realtime-connection-foundation.md.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from typing import Literal

import pytest

from hyperadmin.realtime import ConnectionRegistry, RealtimeConnection

pytestmark = pytest.mark.anyio


@dataclass
class _FakeConn:
    """Minimal stand-in for a real SSE/WS connection.

    The registry only requires ``user_id``, ``transport`` and an awaitable
    ``close()``; everything else is opaque to it.
    """

    user_id: int
    transport: Literal["sse", "ws"] = "sse"
    closed: int = 0
    raise_on_close: bool = False
    _on_close: list[asyncio.Event] = field(default_factory=list)

    async def close(self) -> None:
        self.closed += 1
        if self.raise_on_close:
            raise RuntimeError("boom")


def _conn(user_id: int = 1, transport: Literal["sse", "ws"] = "sse") -> RealtimeConnection:
    fake = _FakeConn(user_id=user_id, transport=transport)
    return RealtimeConnection(user_id=user_id, transport=transport, close=fake.close)


async def test_register_increases_count() -> None:
    # Given an empty ConnectionRegistry
    reg = ConnectionRegistry()

    # When a connection is registered for user 42
    await reg.register(_conn(user_id=42))

    # Then count() returns 1 and users() returns {42}
    assert reg.count() == 1
    assert reg.users() == {42}


async def test_unregister_decreases_count() -> None:
    # Given a registry with two connections for user 42
    reg = ConnectionRegistry()
    c1 = _conn(user_id=42)
    c2 = _conn(user_id=42)
    await reg.register(c1)
    await reg.register(c2)

    # When one connection is unregistered
    await reg.unregister(c1)

    # Then count() returns 1 and 42 is still in users()
    assert reg.count() == 1
    assert reg.users() == {42}


async def test_unregistering_last_connection_removes_user() -> None:
    # Given a registry with one connection for user 42
    reg = ConnectionRegistry()
    c = _conn(user_id=42)
    await reg.register(c)

    # When that connection is unregistered
    await reg.unregister(c)

    # Then count() is 0 and users() is empty
    assert reg.count() == 0
    assert reg.users() == set()


async def test_drain_closes_all_connections() -> None:
    # Given a registry with N connections (mix of SSE + WS)
    reg = ConnectionRegistry()
    closed_calls: list[str] = []

    async def make_close(tag: str):
        async def _close() -> None:
            closed_calls.append(tag)

        return _close

    conns = [
        RealtimeConnection(user_id=1, transport="sse", close=await make_close("sse-1")),
        RealtimeConnection(user_id=2, transport="ws", close=await make_close("ws-2")),
        RealtimeConnection(user_id=2, transport="sse", close=await make_close("sse-2")),
    ]
    for c in conns:
        await reg.register(c)

    # When drain() is awaited
    await reg.drain()

    # Then every connection's close hook is called exactly once and count() is 0
    assert sorted(closed_calls) == ["sse-1", "sse-2", "ws-2"]
    assert reg.count() == 0


async def test_register_after_drain_raises() -> None:
    # Given a registry that has been drained
    reg = ConnectionRegistry()
    await reg.drain()

    # When a new connection is registered, Then RuntimeError is raised
    with pytest.raises(RuntimeError):
        await reg.register(_conn())


async def test_drain_is_idempotent() -> None:
    # Given a drained registry
    reg = ConnectionRegistry()
    await reg.drain()

    # When drain() is awaited again, Then it does not raise
    await reg.drain()
    assert reg.count() == 0


async def test_drain_swallows_close_exceptions() -> None:
    # Given a registry whose connection raises on close
    reg = ConnectionRegistry()
    fake = _FakeConn(user_id=1, raise_on_close=True)
    conn = RealtimeConnection(user_id=1, transport="ws", close=fake.close)
    await reg.register(conn)

    # When drain() is awaited
    # Then it does not propagate the close exception, and count() is 0
    await reg.drain()
    assert reg.count() == 0
    assert fake.closed == 1


async def test_concurrent_register_unregister_is_safe() -> None:
    # Given an empty registry
    reg = ConnectionRegistry()

    async def churn(i: int) -> None:
        c = _conn(user_id=i % 7)
        await reg.register(c)
        await asyncio.sleep(0)
        await reg.unregister(c)

    # When 100 concurrent register-then-unregister coroutines run
    await asyncio.gather(*(churn(i) for i in range(100)))

    # Then the final count() is 0 and no exceptions propagated
    assert reg.count() == 0
    assert reg.users() == set()


async def test_unregister_unknown_is_noop() -> None:
    # Given an empty registry
    reg = ConnectionRegistry()

    # When an unknown connection is unregistered
    # Then it does not raise and count() stays 0
    await reg.unregister(_conn())
    assert reg.count() == 0
