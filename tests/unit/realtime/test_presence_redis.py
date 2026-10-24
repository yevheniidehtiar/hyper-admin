"""Unit tests for hyperadmin.realtime.presence_redis (RedisPresence).

Covers GitHub #324 / #325 against an in-process fake of ``redis.asyncio`` — no
live Redis needed: HASH + per-key expiry, SCAN by channel, removal, expiry,
heartbeat semantics, ``close()`` ownership and the lazy-import guard for the
``[redis]`` extra.
"""

from __future__ import annotations

import re
import sys
from collections.abc import AsyncIterator
from typing import Any

import pytest
from redis.asyncio import Redis

from hyperadmin.realtime import PresenceBackend, RealtimeSettings, presence_channel
from hyperadmin.realtime.presence_redis import RedisPresence

pytestmark = pytest.mark.anyio


def _glob_to_regex(pattern: str) -> str:
    """Redis glob subset: ``\\x`` is a literal, ``*`` matches anything."""
    out: list[str] = []
    chars = iter(pattern)
    for ch in chars:
        if ch == "\\":
            out.append(re.escape(next(chars)))
        elif ch == "*":
            out.append(".*")
        else:
            out.append(re.escape(ch))
    return "".join(out)


class FakeRedis:
    """Minimal stand-in for ``redis.asyncio.Redis``: hashes with millisecond expiry."""

    def __init__(self, *, decode: bool = False) -> None:
        self.now_ms = 0
        self.hashes: dict[str, dict[str, str]] = {}
        self.expiry: dict[str, int] = {}
        self.closed = False
        self._decode = decode

    def advance(self, seconds: float) -> None:
        self.now_ms += int(seconds * 1000)

    def _live(self, key: str) -> bool:
        return key in self.hashes and self.expiry.get(key, self.now_ms + 1) > self.now_ms

    def _out(self, value: str) -> Any:
        return value if self._decode else value.encode()

    async def hget(self, key: str, field: str) -> Any:
        if not self._live(key) or field not in self.hashes[key]:
            return None
        return self._out(self.hashes[key][field])

    async def hset(self, key: str, mapping: dict[str, str]) -> int:
        self.hashes.setdefault(key, {}).update(mapping)
        return len(mapping)

    async def pexpire(self, key: str, ms: int) -> bool:
        self.expiry[key] = self.now_ms + ms
        return True

    async def hgetall(self, key: Any) -> dict[Any, Any]:
        key = key.decode() if isinstance(key, bytes) else key
        if not self._live(key):
            return {}
        return {self._out(f): self._out(v) for f, v in self.hashes[key].items()}

    async def scan_iter(self, match: str) -> AsyncIterator[Any]:
        for key in list(self.hashes):
            if re.fullmatch(_glob_to_regex(match), key):
                yield self._out(key)

    async def delete(self, key: str) -> int:
        self.expiry.pop(key, None)
        return 1 if self.hashes.pop(key, None) is not None else 0

    async def aclose(self) -> None:
        self.closed = True


def _presence(fake: FakeRedis, **kwargs: Any) -> RedisPresence:
    return RedisPresence(client=fake, **kwargs)  # type: ignore[arg-type]


async def test_satisfies_protocol() -> None:
    """Scenario: RedisPresence is a drop-in PresenceBackend."""
    assert isinstance(_presence(FakeRedis()), PresenceBackend)


async def test_set_presence_stores_hash_with_expiry() -> None:
    """Scenario: set_presence writes one HASH per user and expires it after the TTL."""
    # Given
    fake = FakeRedis()
    presence = _presence(fake)
    channel = presence_channel("article", 42)

    # When
    entry = await presence.set_presence(channel, "u1", display_name="Ada", mode="editing", ttl=5)

    # Then
    key = f"{channel}:u1"
    assert fake.hashes[key]["display_name"] == "Ada"
    assert fake.hashes[key]["mode"] == "editing"
    assert fake.expiry[key] == 5000
    assert entry.user_id == "u1"
    assert entry.since == entry.last_seen


async def test_default_ttl_applies() -> None:
    """Scenario: without an explicit ttl the backend default_ttl is used."""
    fake = FakeRedis()
    presence = _presence(fake, default_ttl=12)
    await presence.set_presence("c", "u1", display_name="Ada", mode="viewing")
    assert fake.expiry["c:u1"] == 12000


async def test_heartbeat_keeps_since_and_updates_mode() -> None:
    """Scenario: a repeat call is a heartbeat — since is kept, mode and expiry move on."""
    # Given
    fake = FakeRedis()
    presence = _presence(fake)
    first = await presence.set_presence("c", "u1", display_name="Ada", mode="viewing", ttl=5)
    fake.advance(3)

    # When
    second = await presence.set_presence("c", "u1", display_name="Ada L.", mode="editing", ttl=5)

    # Then
    assert second.since == first.since
    assert second.last_seen >= first.last_seen
    assert (second.display_name, second.mode) == ("Ada L.", "editing")
    assert fake.expiry["c:u1"] == 8000


@pytest.mark.parametrize("decode", [False, True])
async def test_get_presence_scans_channel_and_orders_by_since(decode: bool) -> None:
    """Scenario: get_presence returns only the channel's entries, oldest first."""
    # Given
    fake = FakeRedis(decode=decode)
    presence = _presence(fake)
    await presence.set_presence("c1", "u1", display_name="Ada", mode="viewing")
    await presence.set_presence("c1", "u2", display_name="Bob", mode="editing")
    await presence.set_presence("c10", "u3", display_name="Eve", mode="viewing")
    await presence.set_presence("c1", "u0", display_name="Zed", mode="viewing")
    fake.hashes["c1:u0"]["since"] = "2000-01-01T00:00:00+00:00"

    # When
    entries = await presence.get_presence("c1")

    # Then
    assert [e.user_id for e in entries] == ["u0", "u1", "u2"]
    assert entries[2].mode == "editing"
    assert entries[1].display_name == "Ada"


async def test_get_presence_escapes_glob_characters_in_channel() -> None:
    """Scenario: glob characters in a channel never match other channels."""
    fake = FakeRedis()
    presence = _presence(fake)
    await presence.set_presence("a*", "u1", display_name="Ada", mode="viewing")
    await presence.set_presence("ab", "u2", display_name="Bob", mode="viewing")
    assert [e.user_id for e in await presence.get_presence("a*")] == ["u1"]


async def test_expired_entries_are_not_returned() -> None:
    """Scenario: a lapsed heartbeat makes the user disappear without remove_presence."""
    fake = FakeRedis()
    presence = _presence(fake)
    await presence.set_presence("c", "u1", display_name="Ada", mode="viewing", ttl=5)
    fake.advance(6)
    assert await presence.get_presence("c") == []


async def test_key_expiring_between_scan_and_read_is_skipped() -> None:
    """Scenario: a key that expires after SCAN but before HGETALL is ignored."""
    fake = FakeRedis()
    presence = _presence(fake)
    await presence.set_presence("c", "u1", display_name="Ada", mode="viewing", ttl=5)

    async def hgetall_after_expiry(key: Any) -> dict[Any, Any]:
        fake.advance(10)
        return await FakeRedis.hgetall(fake, key)

    fake.hgetall = hgetall_after_expiry  # type: ignore[method-assign]
    assert [e.user_id for e in await presence.get_presence("c")] == []


async def test_remove_presence_deletes_key_and_is_idempotent() -> None:
    """Scenario: remove_presence deletes the user's key; removing again is a no-op."""
    fake = FakeRedis()
    presence = _presence(fake)
    await presence.set_presence("c", "u1", display_name="Ada", mode="viewing")
    await presence.remove_presence("c", "u1")
    await presence.remove_presence("c", "u1")
    assert fake.hashes == {}


async def test_invalid_ttl_rejected() -> None:
    """Scenario: non-positive TTLs are refused."""
    presence = _presence(FakeRedis())
    with pytest.raises(ValueError, match="ttl must be > 0"):
        await presence.set_presence("c", "u1", display_name="Ada", mode="viewing", ttl=0)
    with pytest.raises(ValueError, match="default_ttl must be > 0"):
        _presence(FakeRedis(), default_ttl=0)


async def test_tiny_ttl_rounds_up_to_one_millisecond() -> None:
    """Scenario: a sub-millisecond ttl never becomes PEXPIRE 0."""
    fake = FakeRedis()
    await _presence(fake).set_presence("c", "u1", display_name="Ada", mode="viewing", ttl=0.0001)
    assert fake.expiry["c:u1"] == 1


async def test_close_leaves_caller_owned_client_open_and_blocks_use() -> None:
    """Scenario: close() is idempotent, keeps a caller-owned client open, rejects later calls."""
    fake = FakeRedis()
    presence = _presence(fake)
    await presence.close()
    await presence.close()
    assert not fake.closed
    with pytest.raises(RuntimeError, match="closed"):
        await presence.get_presence("c")


async def test_close_closes_client_created_from_url() -> None:
    """Scenario: a client RedisPresence created from a URL is closed with it."""
    presence = RedisPresence("redis://localhost:6379/0")
    assert isinstance(presence._client, Redis)
    fake = FakeRedis()
    presence._client = fake  # type: ignore[assignment]
    await presence.close()
    assert fake.closed


async def test_missing_redis_extra_raises_helpful_error(monkeypatch: pytest.MonkeyPatch) -> None:
    """Scenario: constructing from a URL without the extra names the extra to install."""
    monkeypatch.setitem(sys.modules, "redis.asyncio", None)
    with pytest.raises(ImportError, match=r"hyper-admin\[redis\]"):
        RedisPresence("redis://localhost:6379/0")


async def test_settings_select_redis_presence_from_url() -> None:
    """Scenario: RealtimeSettings(presence_redis_url=...) resolves to RedisPresence."""
    settings = RealtimeSettings(presence_redis_url="redis://localhost:6379/1", presence_ttl=9)
    backend = settings.resolve_presence()
    assert isinstance(backend, RedisPresence)
    assert backend.default_ttl == 9
    await backend.close()


async def test_explicit_presence_wins_over_redis_url() -> None:
    """Scenario: an explicit presence backend takes precedence over presence_redis_url."""
    explicit = _presence(FakeRedis())
    settings = RealtimeSettings(presence=explicit, presence_redis_url="redis://localhost:6379/1")
    assert settings.resolve_presence() is explicit
