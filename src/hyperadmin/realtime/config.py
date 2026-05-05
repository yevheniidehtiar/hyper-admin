"""Configuration for the real-time connection foundation."""

from __future__ import annotations

from pydantic import BaseModel, Field


class RealtimeSettings(BaseModel):
    """Opt-in configuration for real-time SSE / WebSocket endpoints.

    Pass an instance to ``Admin(realtime=...)`` to enable real-time. Leaving
    the kwarg as ``None`` (the default) disables every code path in the
    ``realtime`` module — fully backward compatible.
    """

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
