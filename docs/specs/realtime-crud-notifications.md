# SDD: Real-Time CRUD Notifications

| Field | Value |
|---|---|
| Author | Claude Code |
| Status | Approved |
| Issue | #331 (stories #310, #311, #312, #313) |
| Milestone | v0.6.0b — Real-Time Pub/Sub & Live Notifications |
| Created | 2026-10-29 |
| Last updated | 2026-10-29 (review round 2: open questions resolved) |

---

## Problem

The real-time foundation is shipped: SSE/WebSocket endpoints, `ConnectionRegistry`,
`PubSubBackend` (`InMemoryPubSub`, `RedisPubSub`), the `RealtimeEvent` envelope (#308/#309) and
presence (Epic 6.2.4). Nothing publishes a `RealtimeEvent` yet, and no page listens for one. Two
admins working the same list still overwrite each other's mental picture: a row another user
deleted stays on screen until a manual reload.

The foundation also has a latent multi-worker bug. `make_ws_handler()` falls back to a fresh
process-local `InMemoryPubSub` (`realtime/ws.py`), and `Admin` never passes one. With
`RedisPresence` configured, the roster is stored in Redis, but it fans out only to sockets on the
worker that received the heartbeat.

The epic's original stories (#310–#312) put a `pubsub=` constructor argument on
`SQLModelAdapter` / `SQLAlchemyAdapter` and render row HTML inside the WebSocket layer. Both are
revised here. The adapters are the hotspot of the parallel dogfood epic (#701, #719), and
rendering one HTML fragment for every subscriber would bypass row-level scoping (the
`ModelAdmin.get_queryset` hook) and object permissions (v0.5.1). Multi-tenancy is not
implemented yet, but it will build on that same hook, so this design covers it once it lands.

## Goals

- Every successful create / update / delete made through an admin page publishes one
  `RealtimeEvent` on a per-model channel, after the commit, without delaying the response.
- Notifications are selectable per model. A global default in `RealtimeSettings` is overridden by
  each model's `AdminOptions.realtime_notifications`, so a host can turn them on for a few busy
  models only (or off for a few noisy ones). A disabled model behaves exactly as today: no
  wrapper, no subscription hook, no events.
- A list page re-renders its current table and pagination, including the "Showing x to y of N"
  total, when another user changes a row of that model. It keeps its own page, filters, sort and
  search. A hidden tab doesn't re-fetch; it marks the list stale and refreshes when it becomes
  visible again.
- Others' creates and deletes show a toast naming the actor; others' updates briefly highlight
  the changed row instead. Your own changes never toast.
- Every subscriber re-fetches through its own authenticated request, so row scoping, object
  permissions and sensitive-field masking apply exactly as for a normal page load.
- One `PubSubBackend` per `Admin`, shared by notifications and presence, selectable as
  in-memory (default) or Redis. This fixes cross-worker presence fan-out.
- Zero behaviour change when `Admin(realtime=None)` (the default).
- No edits to `adapters/sqlmodel.py`, `adapters/sqlalchemy.py` or `views/dynamic/*` CRUD
  handlers (dogfood conflict avoidance). Works unchanged for plain SQLAlchemy models once #719
  lands.

## Non-Goals

- Notifications over SSE. Bridge-mode hosts without `ExternalAuth.websocket_user` get no live
  list updates in this milestone; the WS route is already absent for them.
- Events for changes made outside the admin (host app writes, raw SQL, other services). Hosts can
  publish their own `RealtimeEvent` with `admin.publish_event()` (see API).
- Inline-row events. Inline children saved through `save_inline_rows()` emit one `updated` event
  for the parent only.
- Live updates on detail and edit pages. Presence covers "someone is editing"; conflict handling
  is OCC (v0.6.0a).
- Per-row HTML diffing or animations. The table body is re-fetched as a whole.

## BDD Scenarios

```
Scenario: create by another user refreshes the list and shows a toast
  Given users A and B both have the Article list open with realtime enabled
  When  A creates an Article
  Then  B's list shows the new row without a page reload
  And   B sees a toast "A created Article #<pk>"
  And   A sees no toast for their own change

Scenario: delete by another user removes the row
  Given users A and B both have the Article list open
  When  A deletes an Article that B can see
  Then  the row disappears from B's list without a reload
  And   B's pagination total drops by one

Scenario: create by another user updates the total counter
  Given B's Article list shows "Showing 1 to 10 of 42 results"
  When  A creates an Article
  Then  B's list shows "of 43 results" without a reload

Scenario: update by another user refreshes and highlights the row
  Given users A and B both have the Article list open
  When  A edits an Article's title
  Then  B's list shows the new title without a reload
  And   the changed row is briefly highlighted
  And   B sees no toast

Scenario: delete by another user shows a toast
  Given users A and B both have the Article list open
  When  A deletes an Article
  Then  B sees a toast "A deleted Article #<pk>"

Scenario: bursts collapse into one toast
  Given users A and B both have the Article list open
  When  A bulk-deletes 12 Articles
  Then  B's list re-fetches once
  And   B sees a single toast "A changed 12 Articles"

Scenario: hidden tab defers the refresh
  Given B's Article list is open in a background tab
  When  A creates an Article
  Then  B's tab sends no list request while hidden
  When  B switches back to the tab
  Then  the list re-fetches once and shows the new row

Scenario: only selected models notify
  Given RealtimeSettings(notifications=False)
  And   ArticleAdmin sets realtime_notifications=True
  When  A creates an Article and a Comment
  Then  B's Article list refreshes live
  And   B's Comment list renders no subscription hook and does not change until reloaded
  And   nothing is published on the Comment channel

Scenario: a noisy model can opt out
  Given RealtimeSettings() (notifications on by default)
  And   AuditLogAdmin sets realtime_notifications=False
  When  rows are written to AuditLog
  Then  nothing is published on the AuditLog channel

Scenario: B's list keeps its own view state
  Given B's Article list is on page 2, filtered by status=draft, sorted by title
  When  A creates an Article
  Then  B's refreshed list is still page 2, status=draft, sorted by title
  And   B's pagination total counts only the rows matching status=draft

Scenario: row scoping is respected
  Given ArticleAdmin.get_queryset limits each user to the Articles they own
  When  A creates an Article
  Then  B's refreshed list does not contain it
  And   B's pagination total is unchanged

Scenario: no subscription attempt without view permission
  Given B lacks the view permission on Article
  When  B opens any admin page
  Then  no page renders an Article subscription hook
  And   B's socket sends no subscribe frame for Article

Scenario: forged subscription is refused
  Given B lacks the view permission on Article
  When  B's socket sends a hand-crafted subscribe frame for Article
  Then  the server refuses it and B receives no Article events

Scenario: realtime disabled is a no-op
  Given Admin(realtime=None)
  When  any record is created, updated or deleted
  Then  nothing is published and list pages render no realtime hooks

Scenario: publish failure never fails the request
  Given the PubSubBackend raises on publish
  When  A saves an Article
  Then  A's save succeeds and the error is logged
```

## Design

### Architecture

```
views/dynamic/* ── adapter.create/update/delete ──▶ EventEmittingAdapter (realtime/emitting.py)
                                                     │ delegates to the real adapter
                                                     │ after success: schedule publish
                                                     ▼
                                   PubSubBackend  (one per Admin: InMemory | Redis)
                                                     │ channel crud_channel(model)
                                                     ▼
              realtime/ws.py  _NotificationSession: per-socket model subscriptions
                                                     │ JSON text frame {"type":"crud",…}
                                                     ▼
   static/js/realtime-status.js ── toast + debounced htmx.ajax(GET, location.href)
                                                     │  into #model-list (rows + pagination total)
                                                     ▼
   normal list_view request under B's own session / scope / permissions
```

New module: `realtime/emitting.py`. Changed: `realtime/config.py`, `realtime/events.py`,
`realtime/ws.py`, `realtime/__init__.py`, `core/app.py`, `core/options.py` (one new field),
`routing.py`, `static/js/realtime-status.js`, `templates/components/table.html`,
`templates/components/table_body.html` (`data-pk` on rows), `templates/components/toast.html`
(new), `static/css/_realtime.css`.

### Emission seam: `EventEmittingAdapter`

`routing.py` builds every model's adapter in exactly one place
(`adapter = admin_instance.adapter_class(model, **adapter_kwargs)`). When notifications are
enabled **for that model**, `routing.py` wraps it once:

```python
if emitter is not None and notifications_enabled(options, realtime_settings):
    adapter = EventEmittingAdapter(adapter, emitter)
```

`notifications_enabled()` (in `realtime/emitting.py`) returns `options.realtime_notifications`
when it is not `None`, else `realtime_settings.notifications`. Because the decision is made per
model at the wrapping site, a disabled model pays nothing at runtime: there is no proxy in its
call path. `Admin` keeps the set of enabled model names. The list template reads it to decide
whether to render the subscription hook, and the WS `authorize` callable reads it to refuse
subscriptions to disabled models.

`EventEmittingAdapter` is a delegating proxy. `create`, `update`, `delete` and
`save_inline_rows` await the wrapped call; after it returns (that is, after the adapter
committed), they schedule a publish. Every other attribute is forwarded with `__getattr__`, and
attribute writes go to the wrapped adapter with `__setattr__`, so `set_queryset_filter()`,
`admin_instance.adapter`, actions, bulk actions and `files.py` / `inline.py` all keep working and
emit too.

- PK for `create`: read through the adapter's existing `pk` info from the returned instance.
- Actor: `current_queryset_scope().request.state.user_key` (the request-scoped `ContextVar`
  already set for every admin request), stringified. `None` outside a request.
- Fire-and-forget: `RealtimeEmitter.schedule(event)` calls `asyncio.create_task(publish)`, holds
  a strong reference in a set until done, logs and swallows any exception. Response latency is
  unaffected.
- No `isinstance(adapter, …)` checks exist in `src/` today. A unit test guards that wrapped
  adapters still satisfy every `BaseAdapter` method the views call.

### Events and channels (`realtime/events.py`)

- `RealtimeEvent` gains `actor_id: str | None = None`. It is optional in `from_dict()`, so
  payloads from older publishers still parse.
- `html_fragment` stays in the envelope for host-published events and is ignored by the built-in
  client. Rendering happens per subscriber, by re-fetch.
- `crud_channel(model_name: str) -> str` returns `f"{prefix}crud:{model_name.lower()}"`, next to
  `presence_channel()`. `prefix` comes from `RealtimeSettings.channel_prefix` (default
  `"hyperadmin:"`), so two admins or apps sharing one Redis instance don't cross-talk.

### WebSocket protocol (`realtime/ws.py`)

New client → server frames, on the same socket and next to presence:

```json
{"type": "subscribe",   "model": "article"}
{"type": "unsubscribe", "model": "article"}
```

Permission is checked twice:

1. **Before the client subscribes (primary).** A subscription hook
   (`data-realtime-model`) is rendered only by the list page, only for a model with
   notifications enabled, and `list_view` renders only after
   `_check_permission(request, "view")` passes (`views/dynamic/list_view.py`). A user without
   `view`, or on a disabled model's list, never gets the hook, so their browser never sends a
   subscribe frame for that model. No wasted round-trip, and no failed subscription in the logs
   for normal use.
2. **On the server (defence in depth).** On `subscribe`, the server refuses models with
   notifications disabled, then re-checks `view` with the
   same `permission_checker.has_permission(user, codename)` call `list_view` uses, through an
   `authorize(user, model_name) -> Awaitable[bool]` callable that `Admin` injects into
   `make_ws_handler`. The result is cached per socket and model, so a re-subscribe after
   reconnect doesn't hit the checker again within the same socket. This catches hand-crafted
   frames.

Unknown model, denied permission, or more than `MAX_NOTIFICATION_CHANNELS` (20) subscriptions:
the frame is ignored and logged at `debug`. Allowed: subscribe to `crud_channel(model)` and
forward every event as:

```json
{"type": "crud", "model": "article", "pk": "42", "action": "created", "actor_id": "7"}
```

`_PresenceSession` and a new `_NotificationSession` share one small `_Follows` helper (subscribe,
forward task, unfollow), extracted from the existing `_PresenceSession` code with no behaviour
change. `close()` tears both down.

### Frontend

- `components/table.html` (only when realtime is on **and** the model has notifications
  enabled; the view passes `realtime_notifications` into the context): its root `#model-list` gets
  `data-realtime-model="{{ model_name|lower }}"`. That root is what the filter bar already
  targets, and for any HTMX request not targeting the `<tbody>` `list_view` serves
  `components/table.html`: rows **and** `components/pagination.html`, so the "Showing x to y of N
  results" total and the page count refresh together with the rows. Swapping it `outerHTML`
  keeps the attribute, because the response re-renders it. (`#model-list-body` is only
  the `<tbody>`, so targeting it would leave the total stale.) The navbar's realtime status
  element gets `data-realtime-self="{{ user_key }}"` so the client can recognise its own events on
  any page.
- `components/table_body.html`: each row gets `data-pk="{{ item_pk }}"` (always rendered; it's
  harmless without realtime) so the client can find the row to highlight.
- `realtime-status.js`: on socket open, send `subscribe` for every `[data-realtime-model]` on the
  page, and only for those. Re-send after each reconnect. On a `crud` frame:
  1. Buffer the event for its model and (re)start a 300 ms debounce timer. This coalesces bursts
     such as a bulk delete of 50 rows into one re-fetch and one toast.
  2. When the timer fires:
     - **Hidden tab** (`document.visibilityState === "hidden"`): don't re-fetch. Mark the model
       stale and keep the buffered events. On `visibilitychange` to visible, flush once (a
       single re-fetch and a single summary toast), however many events arrived meanwhile.
     - **Work in progress** (an inline cell editor is open, or rows are selected for a bulk
       action): don't re-fetch. Show a "List changed: refresh" pill that flushes on click.
     - Otherwise, re-fetch with `htmx.ajax("GET", location.href, {target: "#model-list",
       swap: "outerHTML"})`, the same target the filter bar uses. Using `location.href` at trigger
       time keeps the page, filters, sort and search the user has pushed since the page loaded.
  3. Feedback for the buffered events, ignoring events whose `actor_id === data-realtime-self`:
     - `created` / `deleted`: one toast. A single event names the record ("Ada created Article
       #42", "Ada deleted Article #42"). Several events collapse into one summary ("Ada changed
       12 Articles", or "3 people changed 12 Articles" when the actors differ).
     - `updated`: no toast. After the re-fetch swaps in, the rows whose `data-pk` matches get the
       `ha-row-flash` class for 1.5 s (a CSS background fade in `_realtime.css`, disabled under
       `prefers-reduced-motion`). Rows no longer on the page are ignored.
  4. Dispatch `ha:crud` on `document.body` with the event as `detail`, so host pages can hook in.
- `components/toast.html`: a `<template>` cloned by the JS into the existing
  `.ha-toast-container`, with `role="status"` and `aria-live="polite"`, auto-dismiss after 4 s,
  and `data-testid="realtime-toast"`. Strings go through `_()` (the single-record and summary
  forms above, with plural forms), so all locales get catalog entries. The highlighted row has no
  test id of its own; E2E tests find it by role and text, then assert the class through
  `data-realtime-flash="true"`, which the JS sets alongside it.
- Graceful degradation: no socket means no subscribe and no events. The page behaves exactly as
  today.

### Data Model Changes

No data model changes.

### API / Protocol Changes

- `RealtimeEvent.actor_id: str | None = None` (additive).
- `crud_channel(model_name) -> str` (new, exported from `hyperadmin.realtime`).
- `EventEmittingAdapter`, `RealtimeEmitter` (new, `hyperadmin.realtime.emitting`).
- `Admin.publish_event(event: RealtimeEvent) -> None` (new): publish a host-originated change,
  for example after a background job. A no-op when realtime is disabled or the event's model has
  notifications disabled (logged at `debug`).
- `AdminOptions.realtime_notifications: bool | None = None` (new, see Configuration).
- `make_ws_handler(..., authorize=None)` (new keyword; `None` refuses every subscription).
- WS frames `subscribe` / `unsubscribe` (client → server) and `crud` (server → client), as above.

### Configuration Changes

`RealtimeSettings` gains:

| Field | Default | Meaning |
|---|---|---|
| `pubsub` | `None` | Explicit `PubSubBackend`. |
| `pubsub_redis_url` | `None` | When set and `pubsub` is `None`: `RedisPubSub(url)` (`[redis]` extra). |
| `channel_prefix` | `"hyperadmin:"` | Prefix for notification channels. |
| `notifications` | `True` | Default for models that don't set `realtime_notifications`. `False` makes notifications opt-in per model (presence is unaffected). |

`AdminOptions` gains:

| Field | Default | Meaning |
|---|---|---|
| `realtime_notifications` | `None` | `True` / `False` overrides `RealtimeSettings.notifications` for this model; `None` follows it. Ignored when `Admin(realtime=None)`. |

Selecting a few models:

```python
admin = Admin(app, engine=engine, realtime=RealtimeSettings(notifications=False))

class OrderAdmin(ModelAdmin):
    options: ClassVar[AdminOptions] = AdminOptions(realtime_notifications=True)  # live
# every other model: no wrapper, no hook, no events
```

Excluding a noisy model:

```python
admin = Admin(app, engine=engine, realtime=RealtimeSettings())  # on by default

class AuditLogAdmin(ModelAdmin):
    options: ClassVar[AdminOptions] = AdminOptions(realtime_notifications=False)
```

The decision is made once, at registration, so it's fixed for the life of the process.

`resolve_pubsub()` mirrors `resolve_presence()`. `Admin` resolves the backend **once** and passes
it to `make_ws_handler` (fixing the presence fan-out bug) and to `RealtimeEmitter`. `Admin`
shutdown closes it after draining connections.

## Edge Cases & Error Handling

| Case | Handling |
|---|---|
| Publish raises (Redis down) | Logged at `warning` with the model and action; the request already succeeded. |
| Adapter call raises | No event (the publish is scheduled only after success). |
| Transaction rolled back by host middleware after the adapter commits | The adapters commit inside the call, so not applicable to the built-in adapters. Documented for custom adapters. |
| Bulk action on N rows | N events; the client's 300 ms debounce coalesces them into one re-fetch and one summary toast ("A changed N Articles"). |
| Tab hidden for an hour while hundreds of events arrive | No requests while hidden; one re-fetch and one summary toast on return. The buffer keeps only per-model counts and actor ids, not the events themselves, so memory stays flat. |
| Updated row moved off the page (e.g. a sort key changed) | Nothing to highlight; no toast for updates, so the change is silent. Acceptable: the list is still correct. |
| Model with notifications disabled, written by a relation from an enabled one | Only the model whose adapter was called emits. Inline children emit as the parent (see Non-Goals). |
| `realtime_notifications=True` on a model while `Admin(realtime=None)` | Ignored; no wrapper is installed. Logged once at `info` during registration so the misconfiguration is visible. |
| Composite-PK model | List-only, so it gets no create/update/delete routes and emits nothing. |
| Slow subscriber | `InMemoryPubSub` drops the oldest message per subscriber. A dropped event only means one missed re-fetch; the next event or a reload reconciles. |
| B is editing a form, not on the list | Not subscribed; nothing happens (detail and edit are non-goals). |
| B's list request fails during the re-fetch | Existing `error_toast.html` HTMX handling applies. |
| B's current page empties after deletes (e.g. the last row of the last page) | The re-fetched table shows the empty-state row with the new total and the pager's "previous" link. `list_view` does not clamp the page today, and clamping is out of scope here. |
| User loses view permission mid-session | Subscription persists until reconnect, but every re-fetch goes through `list_view` and returns 403, so no data leaks. Events carry only model, pk, action and actor id. |
| Isolated mount mode (two admins in one process) | Each `Admin` has its own resolved backend and prefix. |

## Migration & Backward Compatibility

No migration required. With `realtime=None`, no proxy is installed and no templates change.
With `realtime` set, notifications are on for every model by default. Hosts that upgrade and
want the previous behaviour set `RealtimeSettings(notifications=False)`. That is called out in
the changelog. Presence now uses the shared, resolved pub/sub, which is a behaviour fix
for multi-worker Redis deployments and unchanged for single-process ones.

## Delivery Plan

One PR per story, in order. Each PR is green and 100% patch-covered on its own.

1. **#310 + #311 (stacked as two commits on one PR)**: `RealtimeSettings.pubsub*`,
   `resolve_pubsub()`, shared backend in `Admin` / `make_ws_handler`, `crud_channel()`,
   `actor_id`, `RealtimeEmitter`, `EventEmittingAdapter`, `notifications_enabled()`,
   `AdminOptions.realtime_notifications`, the per-model wrap in `routing.py`,
   `Admin.publish_event()`. Unit tests in `tests/unit/test_adapter_events.py` (both
   `SQLModelAdapter` and `SQLAlchemyAdapter`, the no-emission path, and the
   global-default × per-model-override matrix) and `tests/unit/realtime/test_emitting.py`.
2. **#312**: WS `subscribe` / `crud` protocol with the enabled-model and permission checks, the
   `_Follows` extraction, JS (debounce, hidden-tab deferral, work-in-progress pill, toasts,
   update highlight), `toast.html`, `data-pk` on rows, list template hooks, i18n catalog entries.
3. **#313**: `tests/e2e/test_realtime_notifications.py` against the SQLModel example app,
   reusing `tests/e2e/_realtime_app.py`, with two browser contexts covering every scenario above.

## Open Questions

All resolved in review round 2 (2026-10-29):

- [x] Proxy seam (`EventEmittingAdapter` in `routing.py`), approved over the `pubsub=`
      constructor argument. It also gives per-model selection for free: only enabled models get
      wrapped.
- [x] Per-subscriber re-fetch, approved over server-rendered `hx-swap-oob` fragments, together
      with hidden-tab deferral.
- [x] Feedback: a toast on others' creates and deletes, a row highlight (no toast) on others'
      updates, bursts collapsed into one summary toast, and never a toast for your own changes.

## Decision Log

| Decision | Rationale | Alternatives considered |
|---|---|---|
| Emit from a delegating proxy installed in `routing.py` | One construction site, so it covers every view, action and custom adapter; touches no adapter or view file the dogfood epic is changing. | `pubsub=` on each adapter (two hotspot files, every third-party adapter must cooperate); emit at the ~13 view call sites (wide diff, easy to miss one). |
| Re-fetch the list per subscriber instead of pushing HTML | Row scoping, object permissions, masking, pagination, filters and i18n all apply for free; no Jinja environment in the WS layer; no rows leak across `get_queryset` scopes. | Server-rendered `hx-swap-oob` row fragments (renders as the publisher, so it leaks rows outside the subscriber's scope, ignores their filters and page, and leaves the total stale). |
| Re-fetch `#model-list`, not `#model-list-body` | The container includes the pagination, so the total counter stays correct. | `<tbody>` only (stale "of N results"); also re-fetching pagination with an `hx-swap-oob` (two swaps per event). |
| Per-model selection decided at the wrapping site (`AdminOptions.realtime_notifications` over `RealtimeSettings.notifications`) | Disabled models carry no proxy at all; one switch drives emission, the template hook and the server's subscribe check; matches existing per-model `AdminOptions` flags like `can_delete`. | A model allow-list on `RealtimeSettings` only (keeps per-model config away from the model's admin); a runtime check inside the proxy (every model pays for the wrapper). |
| Hidden-tab deferral | Background tabs make no list queries; the cost of re-fetch scales with visible viewers, not open tabs. | Re-fetch in every tab (load grows with idle tabs). |
| Toast on create/delete, highlight on update | Delete is the case where a silently vanishing row confuses; an update is visible in place, so a toast would be noise. | Create-only toast (original story #312); toast on all three. |
| Check permission before subscribing, then again on the server | The list page is already permission-gated, so only permitted pages render a subscription hook; the server check only catches forged frames. | Server check only (every page subscribes and gets refused); client check only (forgeable). |
| Reuse the existing socket in `realtime-status.js` instead of the htmx `ws` extension | One connection per tab (already shared with presence); reconnect logic and auth already exist. | `hx-ext="ws"` (second socket, new vendored dependency, duplicate reconnect handling). |
| One resolved `PubSubBackend` per `Admin` | Required for cross-worker fan-out; fixes presence too. | Keep the per-handler `InMemoryPubSub` (silently single-worker). |
| Actor from the queryset-scope `ContextVar` | Already set for every admin request; no signature change. | Pass `request` into adapter calls (API change in hotspot files). |
