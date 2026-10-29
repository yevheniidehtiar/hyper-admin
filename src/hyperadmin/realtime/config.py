"""Configuration for the real-time connection foundation."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from hyperadmin.realtime.events import DEFAULT_CHANNEL_PREFIX
from hyperadmin.realtime.presence import DEFAULT_PRESENCE_TTL, InMemoryPresence, PresenceBackend
from hyperadmin.realtime.presence_redis import RedisPresence
from hyperadmin.realtime.pubsub import InMemoryPubSub, PubSubBackend
from hyperadmin.realtime.pubsub_redis import RedisPubSub


class RealtimeSettings(BaseModel):
    """Opt-in configuration for real-time SSE / WebSocket endpoints.

    Pass an instance to ``Admin(realtime=...)`` to enable real-time. Leaving
    the kwarg as ``None`` (the default) disables every code path in the
    ``realtime`` module — fully backward compatible.
    """

    # ``PresenceBackend`` is a runtime-checkable Protocol: pydantic validates
    # ``presence`` with ``isinstance`` and rejects anything that lacks the methods.
    model_config = ConfigDict(arbitrary_types_allowed=True)

    heartbeat_interval: float = Field(
        default=15.0,
        gt=0,
        description=(
            "Seconds between heartbeats on both SSE (`:keepalive` comments) and "
            "WS (zero-byte ping). Default 15 s sits comfortably under the 60 s "
            "nginx `proxy_read_timeout` default."
        ),
    )
    max_connections: int | None = Field(
        default=None,
        ge=1,
        description=(
            "Optional cap on simultaneous connections per process. ``None`` "
            "(default) means unlimited; the cap exists as a circuit-breaker for "
            "deployments that want to fail-fast under unexpected load."
        ),
    )
    enable_test_endpoints: bool = Field(
        default=False,
        description=(
            "When ``True``, mounts ``/_test/realtime/*`` endpoints used by the "
            "Playwright suite to introspect the registry and simulate server-"
            "initiated drops. Must remain ``False`` in production."
        ),
    )
    presence: PresenceBackend | None = Field(
        default=None,
        description=(
            "Backend that tracks who is viewing / editing which record. ``None`` "
            "(default) resolves to the zero-config ``InMemoryPresence``; pass a "
            "``RedisPresence`` (``[redis]`` extra) for multi-worker deployments."
        ),
    )
    presence_ttl: float = Field(
        default=DEFAULT_PRESENCE_TTL,
        gt=0,
        description=(
            "Seconds a presence entry survives without a heartbeat. Only used to "
            "build the default ``InMemoryPresence``; an explicit ``presence`` "
            "backend carries its own TTL."
        ),
    )

    presence_redis_url: str | None = Field(
        default=None,
        description=(
            "Convenience selector for multi-worker deployments: when set (and no "
            "explicit ``presence`` backend is given) presence is stored in Redis at "
            "this URL via ``RedisPresence`` (``[redis]`` extra)."
        ),
    )

    pubsub: PubSubBackend | None = Field(
        default=None,
        description=(
            "Pub/sub backend that fans CRUD events out to every worker. ``None`` "
            "(default) resolves to the zero-config ``InMemoryPubSub``; pass a "
            "``RedisPubSub`` (``[redis]`` extra) for multi-worker deployments."
        ),
    )
    pubsub_redis_url: str | None = Field(
        default=None,
        description=(
            "Convenience selector for multi-worker deployments: when set (and no "
            "explicit ``pubsub`` backend is given) events travel over Redis at "
            "this URL via ``RedisPubSub`` (``[redis]`` extra)."
        ),
    )
    channel_prefix: str = Field(
        default=DEFAULT_CHANNEL_PREFIX,
        description=(
            "Prefix of every CRUD pub/sub channel (``<prefix>crud:<model>``). Set "
            "it to isolate several apps sharing one Redis."
        ),
    )
    notifications: bool = Field(
        default=True,
        description=(
            "Default for emitting CRUD events from every model's write paths. "
            "``AdminOptions.realtime_notifications`` overrides it per model."
        ),
    )

    def resolve_pubsub(self) -> PubSubBackend:
        """The configured ``pubsub`` backend, else Redis (when a URL is set), else in-memory."""
        if self.pubsub is not None:
            return self.pubsub
        if self.pubsub_redis_url is not None:
            return RedisPubSub(self.pubsub_redis_url)
        return InMemoryPubSub()

    def resolve_presence(self) -> PresenceBackend:
        """The configured ``presence`` backend, else Redis (when a URL is set), else in-memory."""
        if self.presence is not None:
            return self.presence
        if self.presence_redis_url is not None:
            return RedisPresence(self.presence_redis_url, default_ttl=self.presence_ttl)
        return InMemoryPresence(default_ttl=self.presence_ttl)
