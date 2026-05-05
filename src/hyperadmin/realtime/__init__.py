"""Real-time connection foundation for HyperAdmin.

Provides SSE (Server-Sent Events) and WebSocket endpoints with zero business
payload — the MVP only carries protocol-level heartbeats. Both transports
are gated by the existing session auth, enroll with a shared
``ConnectionRegistry`` for observability and shutdown drain, and reconnect
gracefully on the client side via ``static/js/realtime-status.js``.

Subscribing to events / fan-out lives in the PubSub stories (see
``epic-621-websocket-infrastructure-pubsub-backends/epic.md``).
"""

from hyperadmin.realtime.config import RealtimeSettings
from hyperadmin.realtime.registry import ConnectionRegistry, RealtimeConnection

__all__ = ["ConnectionRegistry", "RealtimeConnection", "RealtimeSettings"]
