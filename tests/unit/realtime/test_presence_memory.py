"""Unit tests for hyperadmin.realtime.presence (PresenceBackend + InMemoryPresence).

Covers GitHub #322: set / get / remove presence, heartbeat refresh, TTL
expiry, channel isolation, ``close()`` semantics and the ``RealtimeSettings``
backend selection (#323).
"""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from hyperadmin.realtime import (
    DEFAULT_PRESENCE_TTL,
    InMemoryPresence,
    PresenceBackend,
    PresenceEntry,
    RealtimeSettings,
    presence_channel,
)

pytestmark = pytest.mark.anyio


class FakeClock:
    """Deterministic monotonic clock so TTL tests never sleep."""

    def __init__(self) -> None:
        self.now = 1_000.0

    def __call__(self) -> float:
        return self.now

    def advance(self, seconds: float) -> None:
        self.now += seconds


@pytest.fixture
def clock() -> FakeClock:
    return FakeClock()


@pytest.fixture
def presence(clock: FakeClock) -> InMemoryPresence:
    return InMemoryPresence(default_ttl=30.0, clock=clock)


def test_in_memory_presence_satisfies_protocol() -> None:
    # Given an InMemoryPresence
    # Then it structurally satisfies the PresenceBackend protocol
    assert isinstance(InMemoryPresence(), PresenceBackend)


def test_default_ttl_is_module_default() -> None:
    # Given no explicit TTL
    # Then the backend uses the documented default
    assert InMemoryPresence().default_ttl == DEFAULT_PRESENCE_TTL


@pytest.mark.parametrize("ttl", [0, -1.0])
def test_invalid_default_ttl_rejected(ttl: float) -> None:
    # Given / When a non-positive TTL is passed
    # Then construction fails fast
    with pytest.raises(ValueError, match="default_ttl"):
        InMemoryPresence(default_ttl=ttl)


def test_presence_channel_is_keyed_by_model_and_pk() -> None:
    # Given a model name and a primary key
    # When the presence channel key is built
    # Then it is stable and namespaced per record
    assert presence_channel("article", 42) == "presence:article:42"
    assert presence_channel("article", "abc-123") == "presence:article:abc-123"


async def test_set_presence_stores_entry(presence: InMemoryPresence) -> None:
    # Given an empty backend
    # When a user announces presence on a record channel
    entry = await presence.set_presence(
        "presence:article:1", "u1", display_name="Ada", mode="editing"
    )

    # Then the entry is stored and returned with its timestamps
    assert isinstance(entry, PresenceEntry)
    assert entry.user_id == "u1"
    assert entry.display_name == "Ada"
    assert entry.mode == "editing"
    assert entry.since.tzinfo is timezone.utc
    assert entry.last_seen == entry.since
    assert await presence.get_presence("presence:article:1") == [entry]


async def test_get_presence_returns_entries_in_arrival_order(
    presence: InMemoryPresence, clock: FakeClock
) -> None:
    # Given two users on the same record
    await presence.set_presence("ch", "u1", display_name="Ada", mode="viewing")
    clock.advance(1)
    await presence.set_presence("ch", "u2", display_name="Bob", mode="editing")

    # When presence is read
    entries = await presence.get_presence("ch")

    # Then both are returned, oldest first
    assert [(e.user_id, e.mode) for e in entries] == [("u1", "viewing"), ("u2", "editing")]


async def test_get_presence_on_unknown_channel_is_empty(presence: InMemoryPresence) -> None:
    # Given no presence anywhere
    # When an unknown channel is read
    # Then an empty list is returned and nothing is retained
    assert await presence.get_presence("nobody") == []
    assert presence.channels() == frozenset()


async def test_set_presence_refreshes_existing_entry(
    presence: InMemoryPresence, clock: FakeClock
) -> None:
    # Given a user viewing a record
    first = await presence.set_presence("ch", "u1", display_name="Ada", mode="viewing")
    clock.advance(5)

    # When the same user heartbeats with a new mode
    second = await presence.set_presence("ch", "u1", display_name="Ada", mode="editing")

    # Then the entry is updated in place: ``since`` is kept, ``last_seen`` and mode move on
    assert second.since == first.since
    assert second.last_seen > first.last_seen
    assert second.mode == "editing"
    assert await presence.get_presence("ch") == [second]
    assert presence.user_count("ch") == 1


async def test_remove_presence_removes_entry(presence: InMemoryPresence) -> None:
    # Given two users on a record
    await presence.set_presence("ch", "u1", display_name="Ada", mode="viewing")
    await presence.set_presence("ch", "u2", display_name="Bob", mode="viewing")

    # When one leaves
    await presence.remove_presence("ch", "u1")

    # Then only the other remains
    assert [e.user_id for e in await presence.get_presence("ch")] == ["u2"]


async def test_remove_last_user_cleans_up_channel(presence: InMemoryPresence) -> None:
    # Given a single user on a record
    await presence.set_presence("ch", "u1", display_name="Ada", mode="viewing")

    # When they leave
    await presence.remove_presence("ch", "u1")

    # Then the channel entry is removed (no leak)
    assert presence.channels() == frozenset()


async def test_remove_presence_is_noop_for_unknown_user(presence: InMemoryPresence) -> None:
    # Given a user on a record
    await presence.set_presence("ch", "u1", display_name="Ada", mode="viewing")

    # When an unknown user or channel is removed
    await presence.remove_presence("ch", "ghost")
    await presence.remove_presence("other", "u1")

    # Then nothing changes and nothing raises
    assert presence.user_count("ch") == 1


async def test_entry_expires_after_ttl(presence: InMemoryPresence, clock: FakeClock) -> None:
    # Given a user with a 10 s TTL
    await presence.set_presence("ch", "u1", display_name="Ada", mode="editing", ttl=10)

    # When less than the TTL has elapsed
    clock.advance(9.9)
    # Then the entry is still visible
    assert presence.user_count("ch") == 1

    # When the TTL has elapsed
    clock.advance(0.1)
    # Then the entry is gone and the channel is cleaned up
    assert await presence.get_presence("ch") == []
    assert presence.channels() == frozenset()


async def test_default_ttl_applies_when_not_given(
    presence: InMemoryPresence, clock: FakeClock
) -> None:
    # Given a user announced without an explicit TTL (backend default 30 s)
    await presence.set_presence("ch", "u1", display_name="Ada", mode="viewing")

    # When 30 s elapse
    clock.advance(30)

    # Then the entry has expired
    assert await presence.get_presence("ch") == []


async def test_heartbeat_extends_ttl(presence: InMemoryPresence, clock: FakeClock) -> None:
    # Given a user with a 10 s TTL who heartbeats at 8 s
    await presence.set_presence("ch", "u1", display_name="Ada", mode="viewing", ttl=10)
    clock.advance(8)
    await presence.set_presence("ch", "u1", display_name="Ada", mode="viewing", ttl=10)

    # When the original deadline passes
    clock.advance(8)

    # Then the entry is still present because the heartbeat moved the deadline
    assert presence.user_count("ch") == 1


@pytest.mark.parametrize("ttl", [0, -3.0])
async def test_invalid_ttl_rejected(presence: InMemoryPresence, ttl: float) -> None:
    # Given / When a non-positive per-call TTL is passed
    # Then the call fails fast
    with pytest.raises(ValueError, match="ttl"):
        await presence.set_presence("ch", "u1", display_name="Ada", mode="viewing", ttl=ttl)


async def test_expired_entries_do_not_hide_live_ones(
    presence: InMemoryPresence, clock: FakeClock
) -> None:
    # Given one short-lived and one long-lived entry on the same channel
    await presence.set_presence("ch", "short", display_name="S", mode="viewing", ttl=5)
    await presence.set_presence("ch", "long", display_name="L", mode="viewing", ttl=60)

    # When the short TTL passes
    clock.advance(5)

    # Then only the live entry is returned
    assert [e.user_id for e in await presence.get_presence("ch")] == ["long"]


async def test_channel_isolation(presence: InMemoryPresence) -> None:
    # Given presence on ch-A and ch-B
    await presence.set_presence("ch-A", "u1", display_name="Ada", mode="editing")
    await presence.set_presence("ch-B", "u2", display_name="Bob", mode="viewing")

    # When each channel is read
    # Then presence in ch-A is not visible in ch-B and vice versa
    assert [e.user_id for e in await presence.get_presence("ch-A")] == ["u1"]
    assert [e.user_id for e in await presence.get_presence("ch-B")] == ["u2"]
    assert presence.channels() == frozenset({"ch-A", "ch-B"})


async def test_same_user_on_two_records(presence: InMemoryPresence) -> None:
    # Given the same user on two different records
    await presence.set_presence("presence:article:1", "u1", display_name="Ada", mode="viewing")
    await presence.set_presence("presence:article:2", "u1", display_name="Ada", mode="editing")

    # When one is removed
    await presence.remove_presence("presence:article:1", "u1")

    # Then the other is unaffected
    assert presence.user_count("presence:article:1") == 0
    assert presence.user_count("presence:article:2") == 1


async def test_sweep_purges_expired_entries(presence: InMemoryPresence, clock: FakeClock) -> None:
    # Given expired and live entries across channels
    await presence.set_presence("a", "u1", display_name="Ada", mode="viewing", ttl=1)
    await presence.set_presence("b", "u2", display_name="Bob", mode="viewing", ttl=100)
    clock.advance(1)

    # When a sweep runs
    purged = presence.sweep()

    # Then the expired entry is dropped and reported, the live one survives
    assert purged == 1
    assert presence.channels() == frozenset({"b"})


async def test_close_clears_state_and_rejects_further_calls(presence: InMemoryPresence) -> None:
    # Given a backend with presence
    await presence.set_presence("ch", "u1", display_name="Ada", mode="viewing")

    # When it is closed (twice — idempotent)
    await presence.close()
    await presence.close()

    # Then state is gone and every operation is rejected
    assert presence.channels() == frozenset()
    with pytest.raises(RuntimeError, match="closed"):
        await presence.set_presence("ch", "u1", display_name="Ada", mode="viewing")
    with pytest.raises(RuntimeError, match="closed"):
        await presence.get_presence("ch")
    with pytest.raises(RuntimeError, match="closed"):
        await presence.remove_presence("ch", "u1")


def test_presence_entry_is_immutable() -> None:
    # Given a PresenceEntry
    now = datetime.now(timezone.utc)
    entry = PresenceEntry(
        user_id="u1", display_name="Ada", mode="viewing", since=now, last_seen=now
    )

    # When a field is reassigned
    # Then it is rejected (frozen dataclass)
    with pytest.raises(AttributeError):
        entry.mode = "editing"  # type: ignore[misc]


# --- RealtimeSettings backend selection (#323) -------------------------------


def test_settings_default_resolves_to_in_memory_presence() -> None:
    # Given RealtimeSettings with no explicit presence backend
    settings = RealtimeSettings()

    # When the backend is resolved
    backend = settings.resolve_presence()

    # Then the zero-config default is an InMemoryPresence using the configured TTL
    assert settings.presence is None
    assert isinstance(backend, InMemoryPresence)
    assert backend.default_ttl == settings.presence_ttl == DEFAULT_PRESENCE_TTL


def test_settings_presence_ttl_feeds_default_backend() -> None:
    # Given a custom presence TTL
    settings = RealtimeSettings(presence_ttl=5.0)

    # When the default backend is resolved
    # Then it carries that TTL
    assert settings.resolve_presence().default_ttl == 5.0


def test_settings_explicit_presence_backend_is_used_as_is() -> None:
    # Given an explicit backend instance
    custom = InMemoryPresence(default_ttl=99.0)
    settings = RealtimeSettings(presence=custom)

    # When resolved
    # Then the very same instance is returned
    assert settings.resolve_presence() is custom


def test_settings_rejects_non_presence_backend() -> None:
    # Given an object that does not implement PresenceBackend
    # Then validation fails
    with pytest.raises(ValueError, match="presence"):
        RealtimeSettings(presence=object())  # type: ignore[arg-type]


@pytest.mark.parametrize("ttl", [0, -1.0])
def test_settings_rejects_non_positive_presence_ttl(ttl: float) -> None:
    # Given a non-positive TTL
    # Then validation fails
    with pytest.raises(ValueError, match="presence_ttl"):
        RealtimeSettings(presence_ttl=ttl)
