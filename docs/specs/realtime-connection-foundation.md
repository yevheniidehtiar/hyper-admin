# SDD: Real-Time Connection Foundation

| Field | Value |
|---|---|
| Author | Claude Code |
| Status | Draft |
| Issue | Epic #330 (slice) |
| Milestone | v0.6.0 — Real-Time Layer |
| Created | 2026-05-05 |
| Last updated | 2026-05-05 |

---

## Problem

HyperAdmin has no real-time channel today. Every operator-visible feature on the v0.6.0 roadmap (CRUD live notifications, presence tracking, optimistic-concurrency conflict dialog) needs a long-lived browser-to-server connection. The original Epic 6.2.1 collapsed three concerns into one `size:L` story — connection layer, PubSub, and HTMX `hx-ws` integration — which is hard to review and risky to land in one shot.

This SDD scopes a thinner first slice: a connection foundation with **zero business logic**, just the plumbing required for both transports to be lifecycle-correct (clean connect, clean disconnect on browser close/navigation, automatic reconnect after refresh or transient drop, no leaked tasks/sockets on the server). Once this lands, the existing PubSub stories (#302–#305) plug a `subscribe(...)` async iterator into the WS handler with a small follow-up diff, and Epic 6.2.2 (CRUD events / toasts) can build on top.

## Goals

- Two parallel transports under `{admin_prefix}/realtime/`: SSE (`GET /sse`) and WebSocket (`WS /ws`).
- Both endpoints reject unauthenticated callers (HTTP 401 for SSE, WS close code 4401).
- Heartbeats keep idle connections alive through proxies (configurable interval).
- A `ConnectionRegistry` tracks open connections for observability and shutdown drain.
- A small status widget (navbar dot) opens both transports on every admin page and reconnects with exponential backoff + jitter.
- Backward compatibility: passing no `realtime=` kwarg leaves HyperAdmin behaviour identical to v0.5.x.

## Non-Goals

- PubSub fan-out (lives in #302–#305, layered on after this slice).
- CRUD event emission, toasts, hx-ws row swaps (Epic 6.2.2).
- Redis or any cross-process backend (in-memory only for the MVP).
- Presence tracking (Epic 6.2.4 / v0.6.3).
- Optimistic concurrency conflict dialog.
- Per-channel subscription / routing — the MVP holds a single global "are you alive" stream per transport.

## BDD Scenarios

Pulled verbatim from the implementation stories — keep this section in sync.

```
Scenario: register increases count
  Given an empty ConnectionRegistry
  When  a connection is registered for user 42
  Then  count() returns 1
  And   users() returns {42}

Scenario: drain closes all connections
  Given a registry with N connections (mix of SSE + WS)
  When  drain() is awaited
  Then  every connection's close hook is called exactly once
  And   count() returns 0 after drain

Scenario: authenticated SSE client receives heartbeats
  Given an authenticated session
  When  the client opens EventSource('/admin/realtime/sse')
  Then  the response status is 200
  And   Content-Type is text/event-stream
  And   the client receives at least one :keepalive comment within 2× heartbeat-interval

Scenario: unauthenticated SSE request is rejected
  Given no valid session cookie
  When  the client GETs /admin/realtime/sse
  Then  the response is 401

Scenario: authenticated WS handshake succeeds
  Given an authenticated session cookie
  When  the client opens new WebSocket('ws://.../admin/realtime/ws')
  Then  the handshake completes with status 101
  And   ConnectionRegistry.count() is ≥ 1

Scenario: unauthenticated WS handshake is closed with 4401
  Given no valid session cookie
  When  the client opens the WebSocket
  Then  the server accepts then immediately closes with code 4401

Scenario: server shutdown closes the socket with 1001
  Given an open WebSocket
  When  the server lifespan shuts down
  Then  the client observes a close with code 1001 (going away)

Scenario: dot turns green when both transports are open
  Given an authenticated admin page
  When  the page loads and both connections are established
  Then  window.__rt.state reads "connected"
  And   the navbar dot has data-testid="realtime-status" and class is-connected

Scenario: server restart triggers reconnect
  Given an open connection
  When  the server is killed and restarted within 5 s
  Then  the dot transitions green → yellow → green
  And   the page is NOT reloaded
```

## Design

### Architecture

New top-level module per CONSTITUTION.md §1 ("new feature = new module"):

```
src/hyperadmin/realtime/
├── __init__.py          # public exports: ConnectionRegistry, RealtimeSettings
├── registry.py          # ConnectionRegistry (in-memory, async-safe)
├── config.py            # RealtimeSettings (Pydantic BaseModel)
├── sse.py               # SSE handler factory (GET /realtime/sse)
└── ws.py                # WS handler factory (WS /realtime/ws)
```

Dependency direction (CONSTITUTION.md §2):

```
core/app.py ─► realtime/   (Admin imports the module to register handlers)
realtime/  ─► auth/        (handlers ask auth_backend.get_current_user)
realtime/  has no inbound deps.
```

`realtime/` does NOT import `views/` or `adapters/`.

### Wiring

`Admin.__init__` (`src/hyperadmin/core/app.py:44`) gains one optional kwarg:

```python
def __init__(
    self,
    app: FastAPI,
    ...,
    realtime: RealtimeSettings | None = None,
) -> None:
    ...
    self.realtime = realtime
    self._registry: ConnectionRegistry | None = (
        ConnectionRegistry() if realtime is not None else None
    )
```

`Admin.mount(path)` (line 382) gains one helper call before `include_router(...)`:

```python
if self.realtime is not None:
    self._register_realtime_routes(path)
self.templates.env.globals["realtime_enabled"] = self.realtime is not None
```

`_register_realtime_routes` registers the SSE route on `self.router` (so it sits under the admin prefix and goes through `include_router`'s middleware chain) and the WS route directly on `self.app` via `app.add_websocket_route(f"{path}/realtime/ws", ws_handler)` (because `APIRouter.add_api_websocket_route` does not prefix-mount cleanly through `include_router` on every Starlette version we support).

A FastAPI lifespan startup/shutdown hook drains the registry:

```python
@app.on_event("shutdown")
async def _realtime_drain() -> None:
    if self._registry is not None:
        await self._registry.drain()
```

### Auth

- **SSE** is HTTP, so the existing `AuthenticationMiddleware` (BaseHTTPMiddleware) runs and `request.state.user` is populated. Handler returns `Response(status_code=401)` when `user is None`.
- **WebSocket** is *not* covered by `BaseHTTPMiddleware` (Starlette only dispatches WS through pure ASGI middleware). The handler must call `auth_backend.get_current_user(websocket)` itself after `await websocket.accept()` (the `SessionMiddleware` is ASGI-pure and *does* populate `websocket.session`). On `None`, close with code `4401`.

### Heartbeat

- SSE: server emits `:keepalive\n\n` every `heartbeat_interval` seconds inside the streaming generator.
- WS: server task awaits `asyncio.sleep(heartbeat_interval)` then `await websocket.send_bytes(b"")` (zero-byte ping). The handler's main coroutine is `await websocket.receive_text()` in a loop; either loop exiting cancels the other.

### ConnectionRegistry shape

```python
@dataclass
class _Conn:
    user_id: int
    transport: Literal["sse", "ws"]
    close: Callable[[], Awaitable[None]]

class ConnectionRegistry:
    def __init__(self) -> None: ...
    async def register(self, conn: _Conn) -> None: ...   # raises if drained
    async def unregister(self, conn: _Conn) -> None: ...
    def count(self) -> int: ...
    def users(self) -> set[int]: ...
    async def drain(self) -> None: ...   # idempotent
```

All mutations protected by `asyncio.Lock`. `drain()` flips a `_closed` flag, calls `close()` on every connection concurrently with `asyncio.gather(..., return_exceptions=True)`, then clears the set.

### Data Model Changes

No data model changes.

### API / Protocol Changes

| Path | Method | Auth | Behaviour |
|---|---|---|---|
| `{admin_prefix}/realtime/sse` | GET | session | text/event-stream of `:keepalive` comments |
| `{admin_prefix}/realtime/ws` | WebSocket | session | accept + ping/pong, close 4401 if anon, 1001 on shutdown |

No changes to existing endpoints.

### Configuration Changes

```python
class RealtimeSettings(BaseModel):
    heartbeat_interval: float = 15.0    # seconds
    max_connections: int | None = None  # None = unlimited
```

`Admin(realtime=RealtimeSettings())` opts in. Default (`None`) is fully backward compatible.

### Frontend

- `src/hyperadmin/static/js/realtime-status.js` — vanilla JS module loaded once at the bottom of `_base.html` only when `realtime_enabled` is truthy. Opens `EventSource(...)` and `WebSocket(...)`, exposes `window.__rt = { state, restart() }`. Reconnect: `delay = min(10000, 250 * 2 ** attempt) * (0.7 + Math.random() * 0.6)`.
- `_navbar.html` — adds `<span data-testid="realtime-status" class="ha-rt-dot is-disconnected" aria-live="polite"></span>` that the JS toggles between `is-connected` / `is-reconnecting` / `is-disconnected`.

## Edge Cases & Error Handling

| Case | Handling |
|---|---|
| Reverse-proxy idle timeout | Default heartbeat 15 s < typical 60 s nginx `proxy_read_timeout`. Documented in module docstring. |
| Uvicorn `--reload` cycle leaks tasks | `drain()` is registered on the FastAPI shutdown event; reload triggers a clean shutdown before re-spawning. |
| Reconnect storm after server restart | Backoff `250 ms × 2ⁿ` capped at 10 s with ±30 % jitter. |
| Auth bypass on WS scope | Handler calls `auth_backend.get_current_user(websocket)` itself after `accept()`; no reliance on HTTP middleware. |
| `register()` after `drain()` (race during shutdown) | Raises `RuntimeError`; the SSE/WS handler catches and exits cleanly without enrolling. |
| Browser tab closed without `close()` frame | Server-side `await websocket.receive_text()` raises `WebSocketDisconnect`; SSE generator's `request.is_disconnected()` returns True on the next heartbeat tick. Both branches `unregister()` in a `finally`. |
| Two tabs from the same user | Each tab gets its own `_Conn`; `count()` reflects both, `users()` still `{user_id}`. |
| `Admin()` constructed without `realtime=` | `ConnectionRegistry` not created, no routes registered, no JS injected, no template global set. Verified by integration test. |

## Migration & Backward Compatibility

Backward compatible — no migration required. The new `realtime` kwarg is optional; the default `None` disables every code path added in this slice. No existing test or example needs to change.

When the PubSub stories (#302–#305) land, `realtime/ws.py` will get a small diff to subscribe to `pubsub_backend.subscribe(channel)` and forward messages — the public surface stays the same.

## Open Questions

- [x] SSE + WS or pick one? → **Both** (user decision 2026-05-05).
- [x] New Epic 6.2.0 or reshape 6.2.1? → **Reshape 6.2.1** (user decision 2026-05-05).
- [ ] Should `RealtimeSettings` move under `HyperAdminSettings` later? Defer until after PubSub backends land — that's when the surface stabilises.

## Decision Log

| Decision | Rationale | Alternatives considered |
|---|---|---|
| Ship both SSE and WS | SSE is one-way and cheap (browser-native reconnect via `EventSource`); WS is needed by 6.2.2's HTMX `hx-ws`. Keeping both from day one means consumers don't have to retrofit later. | WS-only (smaller surface, blocks one-way push UX); SSE-only (simpler, but blocks `hx-ws`). |
| In-memory `ConnectionRegistry` only | The MVP has no fan-out; tracking is for observability + shutdown drain. Cross-process tracking belongs with the Redis PubSub backend. | Persisted in Redis from day one (premature; couples MVP to optional dep). |
| Auth check inside WS handler | `BaseHTTPMiddleware` does not cover WS scope; relying on it would silently allow anonymous WS connections. | Wrap `AuthenticationMiddleware` as pure ASGI (larger refactor than the MVP needs). |
| Opt-in via `realtime=` kwarg, default `None` | Keeps zero-config backward compatibility and matches the existing pattern for `auth_backend`, `storage`, `otp_service`. | Auto-enable when any feature requests it (implicit, surprising). |
| WS route registered directly on `self.app` | `APIRouter.add_api_websocket_route` + `include_router(prefix=...)` has had subtle path-prefix bugs across Starlette versions. Direct `app.add_websocket_route(f"{prefix}/realtime/ws", ...)` is unambiguous. | Use `APIRouter` for both; revisit if/when middleware ordering needs the WS to live behind a router-level middleware. |
| Vanilla JS for the status widget | One file, no build step, fits the existing CDN-Alpine/HTMX stack. The MVP doesn't justify a bundler. | Alpine component (cute but adds reactivity we don't need); ship via `htmx-ws` extension (couples MVP to fan-out semantics). |
