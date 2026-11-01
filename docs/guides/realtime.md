# Realtime

With realtime on, the admin keeps an open connection to every signed-in browser. It uses it for
three things:

- **Connection status:** a dot in the navbar shows whether the browser is connected.
- **Presence:** the edit page shows who else is viewing or editing the same record.
- **Live CRUD notifications:** when someone else creates, updates or deletes a row, open list
  pages refresh themselves, flash the changed row and show a short toast.

Realtime is off by default. Leaving `Admin(realtime=None)` disables every realtime code path.

## Requirements

The browser opens two connections under the admin prefix:

| Path | Transport | Carries |
|------|-----------|---------|
| `/admin/realtime/sse` | Server-Sent Events | connection status |
| `/admin/realtime/ws` | WebSocket | presence and CRUD notifications |

**Your ASGI server must support WebSocket.** HyperAdmin leaves the choice of server to your app,
and the most common one, plain `uvicorn`, has no WebSocket support on its own. Install one of:

```bash
pip install "hyperadmin[realtime]"   # adds `websockets`, which uvicorn picks up automatically
pip install "uvicorn[standard]"      # or uvicorn with its standard extras
```

Hypercorn and Granian support WebSocket out of the box and need nothing extra.

Without WebSocket support the status dot still connects (SSE works), but presence and
notifications never arrive. See [Troubleshooting](#troubleshooting).

Behind a reverse proxy, forward the WebSocket upgrade (`Upgrade` and `Connection` headers) on the
`/admin/realtime/ws` path, and keep read timeouts above the 15-second heartbeat.

## Turn it on

```python
from fastapi import FastAPI
from sqlalchemy.ext.asyncio import create_async_engine

from hyperadmin import Admin, HyperAdminSettings
from hyperadmin.realtime import RealtimeSettings

admin = Admin(
    app=FastAPI(),
    engine=create_async_engine("sqlite+aiosqlite:///app.db"),
    settings=HyperAdminSettings(),
    realtime=RealtimeSettings(),
)
admin.mount("/admin")
```

If you mount the admin into an existing app, compose `admin.lifespan()` into your app's lifespan
so open connections are drained on shutdown. See
[Existing FastAPI App](existing-app.md#4-compose-the-admin-lifespan).

## Live CRUD notifications

Every model emits notifications by default. Turn them off globally and opt models in one by one:

```python
from typing import ClassVar

from hyperadmin.core.model import ModelAdmin
from hyperadmin.core.options import AdminOptions
from hyperadmin.realtime import RealtimeSettings

realtime = RealtimeSettings(notifications=False)


class OrderAdmin(ModelAdmin):
    options: ClassVar[AdminOptions] = AdminOptions(realtime_notifications=True)
```

`AdminOptions.realtime_notifications` overrides `RealtimeSettings.notifications` for one model:
`True` or `False` force it, `None` (the default) follows the global setting. Turn it off for
high-volume models such as journal lines or audit logs.

A browser only subscribes to a model when its user has the `view_<model>` permission, and the
server checks the permission again before it forwards any event. Your own changes never toast.

To announce a change made outside the admin (a background job, an import), publish it yourself:

```python
from hyperadmin.realtime import RealtimeAction, RealtimeEvent

admin.publish_event(
    RealtimeEvent(model_name="order", pk=order.id, action=RealtimeAction.UPDATED)
)
```

`publish_event` is a no-op when realtime is off or the model has notifications disabled.

## Several workers

Events and presence live in memory by default, so they only reach browsers connected to the same
worker process. With more than one worker (or several instances), move both to Redis:

```bash
pip install "hyperadmin[redis]"
```

```python
realtime = RealtimeSettings(
    pubsub_redis_url="redis://localhost:6379/0",
    presence_redis_url="redis://localhost:6379/0",
)
```

Set `channel_prefix` when several apps share one Redis.

## Settings

| Setting | Default | Purpose |
|---------|---------|---------|
| `notifications` | `True` | Emit CRUD events for every model (override per model) |
| `heartbeat_interval` | `15.0` | Seconds between SSE keepalives and WebSocket pings |
| `max_connections` | `None` | Per-process connection cap (`None` = unlimited) |
| `pubsub` / `pubsub_redis_url` | in-memory | Where CRUD events fan out |
| `presence` / `presence_redis_url` | in-memory | Where presence is stored |
| `presence_ttl` | `30.0` | Seconds a presence entry survives without a heartbeat |
| `channel_prefix` | `"hyperadmin:"` | Prefix of every pub/sub channel |
| `enable_test_endpoints` | `False` | Test-only endpoints; keep `False` in production |

## Troubleshooting

**The browser console shows `WebSocket connection to '…/admin/realtime/ws' failed`, and the
server answers 426 or 404.**
The ASGI server has no WebSocket support, so it passed the upgrade to the app as plain HTTP.
HyperAdmin answers it with `426 Upgrade Required` and logs one warning:
`HyperAdmin realtime: the ASGI server passed a WebSocket upgrade request to the app as plain
HTTP…`. Install `hyperadmin[realtime]` or `uvicorn[standard]` and restart.

**Notifications reach some browsers but not others.**
You run several workers with the in-memory backends. Configure Redis as in
[Several workers](#several-workers).

**The WebSocket closes right after it opens.**
The handshake was refused: the user is not signed in, or the page's `Origin` is not trusted. Add
your public origin to `HyperAdminSettings.csrf_trusted_origins`. In bring-your-own-auth mode,
set `ExternalAuth.websocket_user`; without it the WebSocket route is not registered at all.
