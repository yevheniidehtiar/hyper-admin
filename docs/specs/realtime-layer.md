# SDD: Real-Time Layer

| Field | Value |
|---|---|
| Author | Claude Code |
| Status | Draft |
| Issue | Milestone 11 |
| Milestone | v0.6.0 — Real-Time Layer |
| Created | 2026-04-02 |
| Last updated | 2026-04-02 |

---

## Problem

HyperAdmin is a multi-user admin panel, but all views are request/response. When Admin A
creates a record, Admin B must manually refresh to see it. When two admins edit the same
record simultaneously, the last save silently overwrites the first — a classic lost-update bug.

These two problems require:
1. **Live notifications** — CRUD changes broadcast to connected browsers in real time.
2. **Optimistic Concurrency Control (OCC)** — detect and resolve conflicting edits.

Without this, HyperAdmin is unsuitable for teams with more than one concurrent admin user.

## Goals

- WebSocket infrastructure with pluggable PubSub backends (InMemory for dev, Redis for prod)
- Zero-config default: real-time works out of the box with InMemoryPubSub
- Live CRUD notifications via HTMX `hx-ws` + out-of-band swaps (no custom JS)
- OCC with automatic version field detection and conflict resolution UI
- Fully backward compatible: existing apps without real-time config are unaffected

## Non-Goals

- Server-Sent Events (SSE) as alternative transport (future consideration)
- Presence tracking / "User X is editing" banners (v0.6.1 milestone)
- Custom real-time channels beyond CRUD model events
- Client-side conflict resolution (three-way merge, field-level diff)
- Rate limiting or throttling of WebSocket messages
- Authentication/authorization on WebSocket connections beyond session middleware
- NATS, RabbitMQ, or Kafka backends (Redis covers multi-worker; others are future)

## BDD Scenarios

### Real-Time Notifications

```
Scenario: single-process app broadcasts messages without configuration
  Given an Admin instance with default settings (no pubsub_backend specified)
  When  a CRUD operation occurs
  Then  InMemoryPubSub is used and connected browsers receive the event

Scenario: multi-worker app uses Redis for cross-process messaging
  Given an Admin instance with pubsub_backend=RedisPubSub(redis_url)
  When  Worker A emits a CRUD event
  Then  browsers connected to Worker B also receive the event

Scenario: WebSocket endpoint accepts browser connections
  Given a running HyperAdmin app
  When  a browser connects to GET /admin/ws?channel=admin:product
  Then  the connection is registered and receives messages for that channel

Scenario: WebSocket endpoint rejects connections without channel
  Given a running HyperAdmin app
  When  a browser sends WS upgrade to /admin/ws (no channel param)
  Then  the connection is closed with code 4001

Scenario: created record appears in second browser without reload
  Given Session A and Session B both have /admin/product/ list open
  When  Session A creates a new product "Widget"
  Then  Session B sees a toast notification and the new row appears without reload

Scenario: deleted record disappears from second browser
  Given Session A and Session B both have /admin/product/ list open
  When  Session A deletes product #5
  Then  row #5 disappears from Session B's list without reload

Scenario: updated record reflects changes in second browser
  Given Session A and Session B both view the product list
  When  Session A updates product #5's name to "New Name"
  Then  Session B's row #5 shows "New Name" via hx-swap-oob without reload

Scenario: event emission is fire-and-forget
  Given an adapter with pubsub configured but the backend is temporarily unreachable
  When  adapter.create(data) is called
  Then  the CRUD operation still succeeds (event failure is non-blocking)

Scenario: toast notification is accessible
  Given a notification toast is displayed
  When  inspected by a screen reader
  Then  it has role="alert" and aria-live="polite" and auto-dismisses after 4 seconds
```

### Optimistic Concurrency Control

```
Scenario: concurrent edits are detected
  Given User A and User B open the edit form for the same record
  When  User A saves, then User B saves
  Then  User B sees a conflict dialog (the record was modified since they opened it)

Scenario: user can reload fresh data after conflict
  Given a conflict dialog is displayed
  When  the user clicks "Reload"
  Then  the form refreshes with the latest saved data

Scenario: user can force-save after conflict
  Given a conflict dialog is displayed
  When  the user clicks "Save Anyway"
  Then  the save proceeds, overwriting the other user's changes

Scenario: models without version field are unaffected
  Given a model that has no updated_at, modified_at, or version field
  When  the edit form is rendered and submitted
  Then  no OCC logic is applied (fully backward compatible)

Scenario: explicit version_field overrides convention detection
  Given a ModelAdmin with version_field="revision"
  When  detect_version_field() is called
  Then  it returns "revision" regardless of other fields present

Scenario: integer version field is auto-incremented
  Given a model with an integer "version" field at value 3
  When  a successful update occurs
  Then  the version field becomes 4

Scenario: datetime version field is auto-updated
  Given a model with a datetime "updated_at" field
  When  a successful update occurs
  Then  updated_at is set to the current UTC time
```

## Design

### Architecture

The real-time layer introduces one new top-level module (`realtime/`) and two new core
contracts (`core/realtime.py`, `core/concurrency.py`).

```
                        ┌────────────────────────┐
                        │     views/             │
                        │  websocket.py (WS)     │
                        │  dynamic.py (OCC)      │
                        └────┬──────────┬────────┘
                             │          │
                    ┌────────▼──┐  ┌────▼────────────┐
                    │ realtime/ │  │ adapters/        │
                    │ manager   │  │ sqlmodel (events)│
                    │ memory    │  │ sqlalchemy (OCC) │
                    │ redis     │  └────┬─────────────┘
                    └────┬──────┘       │
                         │              │
                    ┌────▼──────────────▼────┐
                    │        core/           │
                    │  realtime.py (protocol)│
                    │  concurrency.py (OCC)  │
                    │  options.py (config)   │
                    └────────────────────────┘
```

Dependency direction: `views/ → realtime/ → core/` and `adapters/ → core/`. No reverse
imports. `core/` never imports from `realtime/`, `adapters/`, or `views/`.

**Why `realtime/` is a new top-level module (not under `adapters/`)**:
CONSTITUTION.md defines `adapters/` as "ORM-specific implementations of core contracts."
PubSub backends are messaging infrastructure, not ORM adapters. The constitution rule
"New feature = new module" applies. This mirrors `auth/` and `uploads/` as domain modules.

### Data Model Changes

No new ORM models. No schema migrations.

- `RealtimeAction` — `enum.StrEnum` with values `created`, `updated`, `deleted`
- `RealtimeEvent` — `@dataclass` with fields:
  - `model_name: str`
  - `pk: Any` (serialized as `str` in JSON)
  - `action: RealtimeAction`
  - `html_fragment: str | None`
  - Methods: `to_bytes() -> bytes`, `from_bytes(data: bytes) -> RealtimeEvent`
- `StaleRecordError(Exception)` — attributes: `current_version: Any`, `expected_version: Any`

### API / Protocol Changes

**New protocols in `core/realtime.py`:**

```python
class PubSubBackend(Protocol):
    async def publish(self, channel: str, message: bytes) -> None: ...
    async def subscribe(self, channel: str) -> AsyncIterator[bytes]: ...
    async def unsubscribe(self, channel: str) -> None: ...
    async def close(self) -> None: ...
```

**New functions in `core/concurrency.py`:**

```python
def detect_version_field(model_class: type, options: AdminOptions) -> str | None: ...
```

**Modified signatures:**

- `BaseAdapter.update(pk, data, *, expected_version: Any = None)` — new kwarg
- `Admin.__init__(..., pubsub_backend: PubSubBackend | None = None)` — new kwarg

**New endpoints:**

- `GET /admin/ws` — WebSocket upgrade. Query param: `channel` (required).
  Accepts: `admin:{model_name}` format.
  Close codes: 4001 (missing channel), 4003 (invalid channel format).

**New template components:**

- `components/toast.html` — `role="alert"`, `aria-live="polite"`, auto-dismiss 4s
- `components/conflict_dialog.html` — `role="alertdialog"`, Reload + Save Anyway buttons

### Configuration Changes

**`Admin()` constructor:**
- `pubsub_backend: PubSubBackend | None = None` — defaults to `InMemoryPubSub()` when None

**`AdminOptions` / `ModelAdmin`:**
- `version_field: str | None = None` — explicit OCC version field name. When None,
  auto-detected from convention list: `[updated_at, modified_at, last_modified, version]`.

**No new environment variables.** No new `HyperAdminSettings` fields.
PubSub backend is configured programmatically in `Admin()`, not via env vars, because
the backend choice requires different constructor args (Redis URL vs nothing for InMemory).

## Edge Cases & Error Handling

| Case | Handling |
|---|---|
| WebSocket connection without `channel` param | Close with code 4001, message "channel parameter required" |
| Invalid channel format (not `admin:{name}`) | Close with code 4003, message "invalid channel format" |
| Client disconnects mid-broadcast | Remove from ConnectionManager, log debug, continue broadcast to others |
| PubSub backend unreachable during event emit | Log warning, swallow exception (fire-and-forget) |
| Redis connection lost after subscribe | Subscriber iterator raises, ConnectionManager removes client |
| Two concurrent subscribes to same channel | Both get independent message streams (no dedup needed) |
| Model has no version field, OCC update called | `expected_version` is ignored, normal update proceeds |
| `__version` form field submitted for non-OCC model | Field is ignored (not passed to adapter) |
| Adapter update with stale version | `StaleRecordError` raised, view returns 409 + conflict dialog |
| `__force=true` in form submission | `expected_version=None` passed to adapter, version check skipped |
| Browser without WebSocket support | HTMX `hx-ext="ws"` degrades gracefully — page works normally without live updates |
| Multiple list views open for different models | Each connects to its own channel, no cross-contamination |

## Migration & Backward Compatibility

**Backward compatible — no migration required.**

- `Admin()` without `pubsub_backend` works exactly as before. InMemoryPubSub is instantiated
  as default but does nothing unless browsers connect via WebSocket.
- `BaseAdapter.update()` gains `expected_version=None` kwarg — existing callers are unaffected.
- Models without version fields: no OCC logic applied, no hidden form fields injected.
- `__init__.py` exports: no changes to existing exports. New exports (`InMemoryPubSub`,
  `RedisPubSub`, `ConnectionManager`, `StaleRecordError`) are additive — no semver bump needed.
- Templates: `hx-ext="ws"` is added to list views but only activates when `ws-connect` URL
  is present. Existing templates without WS support render identically.

## Open Questions

- [x] Should PubSub backends live under `adapters/pubsub/` or a new `realtime/` module?
  **Resolved**: New `realtime/` module per CONSTITUTION.md ("New feature = new module"
  and "adapters/ is for ORM-specific implementations").

- [ ] Should `ConnectionManager` also handle presence heartbeats, or should that be deferred
  to v0.6.1? **Proposed**: Defer. ConnectionManager in v0.6.0 only tracks connections and
  broadcasts. Presence (heartbeat, "who's editing") is v0.6.1 scope.

- [ ] Should the WebSocket endpoint require authentication (session cookie)?
  **Proposed**: Yes, reuse existing session middleware. If no valid session and auth is enabled,
  close with code 4003. Unauthenticated apps (no auth_backend) allow all WS connections.

## Decision Log

| Decision | Rationale | Alternatives considered |
|---|---|---|
| New `realtime/` top-level module | CONSTITUTION: `adapters/` is ORM-specific; PubSub is messaging | Put PubSub in `adapters/pubsub/` — rejected, violates module purpose |
| `InMemoryPubSub` as zero-config default | Django-admin philosophy: works out of the box | Require explicit configuration — rejected, breaks zero-config principle |
| `asyncio.Queue` per subscriber (not per channel) | Each subscriber needs independent iteration; shared queue would require fan-out | Single queue + fan-out — rejected, complex and error-prone |
| `redis.asyncio` (not `aioredis`) | `aioredis` is deprecated since redis-py 4.2 absorbed it | `aioredis` — rejected, unmaintained |
| Fire-and-forget event emission | Real-time notifications are best-effort; CRUD must never fail due to PubSub | Transactional outbox — rejected, over-engineered for admin panel |
| `hx-swap-oob` for row updates | Native HTMX, no custom JS, works with existing templates | Alpine.js reactive updates — rejected, new dependency |
| OCC via version field convention detection | Zero-config for common patterns (updated_at), opt-in override via `version_field` | Always require explicit `version_field` — rejected, not zero-config |
| HTTP 409 + HTML fragment for conflicts | HTMX can swap conflict dialog into form; no JS error handling needed | JSON error response — rejected, inconsistent with HTMX-first approach |
| Conflict dialog replaces form body (not modal) | Simpler, accessible, no overlay JS needed | Modal overlay — rejected, requires JS and z-index management |
| OCC independent of WebSocket track | No technical dependency; allows parallel development | Sequential after WebSocket — rejected, wastes calendar time |
