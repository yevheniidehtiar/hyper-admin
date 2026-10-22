"""Presence tracking — who is viewing or editing which record.

``PresenceBackend`` is the small, stable contract every backend implements
(``InMemoryPresence`` here, ``RedisPresence`` in the ``[redis]`` extra, later).
Entries are keyed by a *channel* — one per record, built with
``presence_channel(model, pk)`` — and by ``user_id`` within that channel.
Every entry carries a TTL: a client keeps its presence alive by calling
``set_presence()`` again (a heartbeat); an entry whose TTL lapses disappears
without an explicit ``remove_presence()``, so a crashed tab never leaves a
ghost "Ada is editing" behind.

Usage::

    presence = InMemoryPresence()
    channel = presence_channel("article", 42)

    await presence.set_presence(channel, "u1", display_name="Ada", mode="editing")
    for entry in await presence.get_presence(channel):
        ...
    await presence.remove_presence(channel, "u1")

Transport (WebSocket heartbeat handling) and rendering (presence banner)
live in later Epic 6.2.4 stories.
"""

from __future__ import annotations

import time
from collections.abc import Callable
from dataclasses import dataclass, replace
from datetime import datetime, timezone
from typing import Final, Literal, Protocol, runtime_checkable

# Seconds an entry survives without a heartbeat (2x the default 15 s heartbeat).
DEFAULT_PRESENCE_TTL: Final = 30.0

PresenceMode = Literal["viewing", "editing"]


def presence_channel(model: str, pk: object) -> str:
    """Channel key for one record: ``presence:{model}:{pk}``."""
    return f"presence:{model}:{pk}"


@dataclass(frozen=True, slots=True)
class PresenceEntry:
    """One user's presence on one record channel."""

    user_id: str
    display_name: str
    mode: PresenceMode
    since: datetime  # when the user first appeared on the channel (UTC)
    last_seen: datetime  # when the user last heartbeat (UTC)


@runtime_checkable
class PresenceBackend(Protocol):
    """Per-channel registry of users with TTL-based expiry."""

    async def set_presence(
        self,
        channel: str,
        user_id: str,
        *,
        display_name: str,
        mode: PresenceMode,
        ttl: float | None = None,
    ) -> PresenceEntry:
        """Announce or refresh ``user_id`` on ``channel``; returns the stored entry.

        Calling again for the same user is a heartbeat: ``mode`` and
        ``display_name`` are updated, ``last_seen`` moves to now, the expiry
        deadline is pushed out by ``ttl`` (backend default when ``None``).
        """
        raise NotImplementedError

    async def get_presence(self, channel: str) -> list[PresenceEntry]:
        """Live (unexpired) entries on ``channel``, oldest first."""
        raise NotImplementedError

    async def remove_presence(self, channel: str, user_id: str) -> None:
        """Forget ``user_id`` on ``channel``. No-op when absent."""

    async def close(self) -> None:
        """Drop all state and release resources. Idempotent."""


@dataclass(slots=True)
class _Slot:
    entry: PresenceEntry
    expires_at: float


class InMemoryPresence:
    """Single-process ``PresenceBackend`` backed by plain dicts.

    Zero-config default for single-worker deployments; presence does not
    cross process boundaries. Expiry is lazy: expired entries are purged
    whenever their channel is read or written (and by ``sweep()``), so no
    background task is needed and nothing can leak. ``clock`` is the
    monotonic time source — injectable for deterministic tests.
    """

    def __init__(
        self,
        default_ttl: float = DEFAULT_PRESENCE_TTL,
        *,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        if default_ttl <= 0:
            msg = "default_ttl must be > 0"
            raise ValueError(msg)
        self.default_ttl = default_ttl
        self._clock = clock
        self._channels: dict[str, dict[str, _Slot]] = {}
        self._closed = False

    def _ensure_open(self) -> None:
        if self._closed:
            msg = "InMemoryPresence is closed"
            raise RuntimeError(msg)

    def _purge(self, channel: str) -> dict[str, _Slot]:
        """Drop expired slots on ``channel`` (and the channel itself when empty)."""
        slots = self._channels.get(channel)
        if slots is None:
            return {}
        now = self._clock()
        for user_id in [uid for uid, slot in slots.items() if slot.expires_at <= now]:
            del slots[user_id]
        if not slots:
            self._channels.pop(channel, None)
        return slots

    async def set_presence(
        self,
        channel: str,
        user_id: str,
        *,
        display_name: str,
        mode: PresenceMode,
        ttl: float | None = None,
    ) -> PresenceEntry:
        self._ensure_open()
        if ttl is None:
            ttl = self.default_ttl
        elif ttl <= 0:
            msg = "ttl must be > 0"
            raise ValueError(msg)
        slots = self._purge(channel)
        now = datetime.now(timezone.utc)
        existing = slots.get(user_id)
        if existing is None:
            entry = PresenceEntry(
                user_id=user_id, display_name=display_name, mode=mode, since=now, last_seen=now
            )
        else:
            entry = replace(existing.entry, display_name=display_name, mode=mode, last_seen=now)
        self._channels.setdefault(channel, slots)[user_id] = _Slot(entry, self._clock() + ttl)
        return entry

    async def get_presence(self, channel: str) -> list[PresenceEntry]:
        self._ensure_open()
        return [slot.entry for slot in self._purge(channel).values()]

    async def remove_presence(self, channel: str, user_id: str) -> None:
        self._ensure_open()
        slots = self._purge(channel)
        slots.pop(user_id, None)
        if not slots:
            self._channels.pop(channel, None)

    async def close(self) -> None:
        if self._closed:
            return
        self._closed = True
        self._channels.clear()

    def sweep(self) -> int:
        """Purge expired entries on every channel; returns how many were dropped."""
        before = sum(len(slots) for slots in self._channels.values())
        for channel in list(self._channels):
            self._purge(channel)
        return before - sum(len(slots) for slots in self._channels.values())

    def user_count(self, channel: str) -> int:
        """Number of live users on ``channel`` (observability / tests)."""
        return len(self._purge(channel))

    def channels(self) -> frozenset[str]:
        """Channels that currently have at least one live entry."""
        self.sweep()
        return frozenset(self._channels)
