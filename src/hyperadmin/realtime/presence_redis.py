"""Redis-backed ``PresenceBackend`` for multi-worker deployments.

Requires the optional extra: ``pip install 'hyper-admin[redis]'``. The
``redis`` package is imported lazily, so importing this module never fails —
constructing ``RedisPresence`` from a URL without the extra raises an
``ImportError`` that names the extra to install.

Each user on a channel is one Redis ``HASH`` at ``{channel}:{user_id}`` (the
channel already carries the ``presence:`` prefix, see ``presence_channel``).
The key's own expiry is the entry TTL — a heartbeat re-sets the hash and pushes
the expiry out, a crashed tab simply lapses. ``get_presence`` finds a channel's
users with ``SCAN`` on ``{channel}:*``.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any, Final, cast

from hyperadmin.realtime.presence import DEFAULT_PRESENCE_TTL, PresenceEntry, PresenceMode

if TYPE_CHECKING:
    from redis.asyncio import Redis

DEFAULT_REDIS_URL: Final = "redis://localhost:6379/0"

_GLOB_SPECIALS: Final = frozenset("\\*?[]")


def _redis_from_url(url: str) -> Redis:
    try:
        from redis.asyncio import Redis  # noqa: PLC0415 - optional extra, imported lazily
    except ImportError as exc:
        msg = "RedisPresence requires the 'redis' package. Install it with: pip install 'hyper-admin[redis]'"
        raise ImportError(msg) from exc
    return Redis.from_url(url)


def _escape_glob(text: str) -> str:
    return "".join(f"\\{ch}" if ch in _GLOB_SPECIALS else ch for ch in text)


def _text(value: bytes | str) -> str:
    # Clients built with ``decode_responses=True`` hand back ``str``.
    return value.decode() if isinstance(value, bytes) else value


class RedisPresence:
    """``PresenceBackend`` backed by one expiring Redis hash per user and channel.

    Pass either a ``url`` (the client is created lazily and closed by
    ``close()``) or an existing ``redis.asyncio.Redis`` ``client`` (owned by
    the caller and left open).
    """

    def __init__(
        self,
        url: str = DEFAULT_REDIS_URL,
        *,
        client: Redis | None = None,
        default_ttl: float = DEFAULT_PRESENCE_TTL,
    ) -> None:
        if default_ttl <= 0:
            msg = "default_ttl must be > 0"
            raise ValueError(msg)
        self.default_ttl = default_ttl
        self._owns_client = client is None
        self._client: Redis = _redis_from_url(url) if client is None else client
        self._closed = False

    def _ensure_open(self) -> None:
        if self._closed:
            msg = "RedisPresence is closed"
            raise RuntimeError(msg)

    @staticmethod
    def _key(channel: str, user_id: str) -> str:
        return f"{channel}:{user_id}"

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
        key = self._key(channel, user_id)
        now = datetime.now(timezone.utc)
        existing = await self._client.hget(key, "since")
        since = datetime.fromisoformat(_text(existing)) if existing else now
        await self._client.hset(
            key,
            mapping={
                "display_name": display_name,
                "mode": mode,
                "since": since.isoformat(),
                "last_seen": now.isoformat(),
            },
        )
        await self._client.pexpire(key, max(1, round(ttl * 1000)))
        return PresenceEntry(
            user_id=user_id, display_name=display_name, mode=mode, since=since, last_seen=now
        )

    async def get_presence(self, channel: str) -> list[PresenceEntry]:
        self._ensure_open()
        prefix = f"{channel}:"
        entries: list[PresenceEntry] = []
        async for raw_key in self._client.scan_iter(match=f"{_escape_glob(prefix)}*"):
            fields: dict[Any, Any] = await self._client.hgetall(raw_key)
            if not fields:  # expired between SCAN and HGETALL
                continue
            data = {_text(k): _text(v) for k, v in fields.items()}
            entries.append(
                PresenceEntry(
                    user_id=_text(raw_key)[len(prefix) :],
                    display_name=data["display_name"],
                    mode=cast("PresenceMode", data["mode"]),
                    since=datetime.fromisoformat(data["since"]),
                    last_seen=datetime.fromisoformat(data["last_seen"]),
                )
            )
        return sorted(entries, key=lambda e: e.since)

    async def remove_presence(self, channel: str, user_id: str) -> None:
        self._ensure_open()
        await self._client.delete(self._key(channel, user_id))

    async def close(self) -> None:
        if self._closed:
            return
        self._closed = True
        if self._owns_client:
            await self._client.aclose()
