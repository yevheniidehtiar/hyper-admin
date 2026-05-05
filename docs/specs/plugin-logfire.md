# SDD: hyperadmin-logfire — first official plugin

| Field | Value |
|---|---|
| Author | Claude Code |
| Status | Draft |
| Issue | TBD |
| Milestone | v0.8.0 — Plugins |
| Created | 2026-05-05 |
| Last updated | 2026-05-05 |

---

## Problem

Admin perf problems hide until users complain — slow list queries, N+1, validation
bottlenecks. There is no first-party observability story for HyperAdmin. The plugin
registry SDD (`docs/specs/plugin-registry.md`) defines the contract; this SDD is the
**first consumer** of that contract and the **proof-of-concept that it works without
core modification**.

If this plugin requires any change to `core/` beyond the hooks defined in the registry
SDD, the registry SDD is wrong and must be revised. That is the design pressure on
this work.

## Goals

1. **One-call setup**: `instrument_admin(admin)` wires everything.
2. **Adapter spans**: `admin.adapter.<op>` spans with attributes `model`, `op`, paging
   and filter context — emitted via `on_before_adapter_call` / `on_after_adapter_call`.
3. **HTTP + SQL coverage**: leverage `logfire.instrument_fastapi(admin.app)` and
   `logfire.instrument_sqlalchemy(admin.engine)` for transparent HTTP/SQL spans
   parented under the adapter span.
4. **Validation events**: structured `admin.validation_error` events when admin form
   validation fails, with `model` and `field_errors` attributes.
5. **Auth events**: `admin.auth.login_success`, `admin.auth.login_failure`,
   `admin.auth.logout`, `admin.auth.permission_denied`.
6. **No-op when unconfigured**: if `logfire.configure()` was not called, the plugin
   logs a one-shot warning and emits nothing — never crashes.
7. **Zero changes to `src/hyperadmin/core/`** — proves the plugin contract.

## Non-Goals

- **In-admin perf dashboard widget** — RFC #276 Phase 2; deferred to v0.8.1+.
- **OTel-generic variant (`hyperadmin-otel`)** — defer until there's a user with a
  non-Logfire OTel backend who complains.
- **Sampling configuration** — defer; users configure sampling on their `logfire`
  client directly.
- **Custom span attributes per model** — `AdminOptions.observability_attrs` etc. is
  out of scope; if a user needs this, they wrap their own adapter.

## BDD Scenarios

```
Scenario: instrument_admin attaches the plugin and emits adapter spans
  Given logfire is configured to capture spans in a test sink
  And   instrument_admin(admin) has been called
  When  the admin.products list view is requested
  Then  the test sink contains a span named "admin.adapter.list" with attribute model="Product"

Scenario: validation failure emits a structured event
  Given logfire is configured to capture events
  When  POST /admin/products/create with an invalid payload
  Then  the sink contains an event "admin.validation_error" with attributes model="Product" and field_errors non-empty

Scenario: failed login emits an auth event
  Given logfire is configured to capture events
  When  POST /admin/login with username=alice password=wrong
  Then  the sink contains an event "admin.auth.login_failure" with attribute username="alice"

Scenario: plugin no-ops when logfire is not configured
  Given logfire.configure() was NOT called
  When  Admin is constructed and a list view is requested
  Then  no exceptions are raised
  And   a single warning log mentions hyperadmin-logfire requires logfire.configure()

Scenario: plugin is not loaded when disabled
  Given hyperadmin-logfire is installed
  When  Admin(app, engine=engine, disabled_plugins=["logfire"]) is constructed
  Then  no admin.adapter.* spans are emitted on subsequent requests
```

## Design

### Architecture

**Repo layout decision: monorepo subpath at `plugins/hyperadmin-logfire/`** with its
own `pyproject.toml`. Reasons:

- Atomic dual-PR with Epic 1 hook changes (any missing hook can be added in the same PR).
- Single CI matrix; no second repo to bootstrap.
- Promote to its own GitHub repo later (after v0.8.0) if community contribution warrants.

```
plugins/hyperadmin-logfire/
  pyproject.toml                           # name="hyperadmin-logfire", entry-point: logfire = "hyperadmin_logfire:LogfirePlugin"
  README.md
  src/hyperadmin_logfire/
    __init__.py                            # exports: LogfirePlugin, instrument_admin
    plugin.py                              # LogfirePlugin(Plugin) with all hook methods
    adapter_spans.py                       # span helpers — pure functions
    auth_events.py                         # auth event emit helpers
    _config_check.py                       # one-shot warning when logfire not configured
  tests/
    unit/
      test_plugin.py
      test_adapter_spans.py
      test_no_logfire_config.py
    e2e/
      test_end_to_end_spans.py
      test_disabled_plugin.py
```

Root `pyproject.toml` adds `plugins/hyperadmin-logfire` to `[tool.uv.workspace.members]`
so `uv sync --all-extras` picks it up for development. Published to PyPI separately.

### Hook usage (consumes only Epic 1 contract)

| Plugin behaviour | Hook used |
|---|---|
| Adapter span open + close | `on_before_adapter_call` / `on_after_adapter_call` |
| Validation error event | New hook **not yet in registry SDD**: `on_validation_error(admin, model, field_errors)`. **Action: add to Epic 1 SDD before merging.** Alternative: emit directly from `instrument_admin` by patching `PydanticForm.validate()` — rejected (violates "no core changes"). |
| Auth events | New hook **not yet in registry SDD**: `on_auth_event(admin, event_type, user, **context)`. **Action: add to Epic 1 SDD before merging.** Alternative: ASGI middleware that listens on the existing auth response codes — possible but fragile (can't distinguish login_success from any other 302). |
| `instrument_admin(admin)` | Calls `logfire.instrument_fastapi(admin.app)` and `logfire.instrument_sqlalchemy(admin.engine)` directly. These are public Logfire APIs — no HyperAdmin hook needed. |

**Net effect on Epic 1 SDD**: two hooks must be added (`on_validation_error`,
`on_auth_event`) before this epic's SDD is approved. They are uncontroversial additions
(observer-pattern hooks like the rest), but the dependency is explicit.

### Data Model Changes

No data model changes.

### API / Protocol Changes

New public API in the plugin package:

```python
# hyperadmin_logfire/__init__.py
def instrument_admin(admin: "Admin") -> None:
    """One-call setup. Idempotent.

    1. logfire.instrument_fastapi(admin.app)
    2. logfire.instrument_sqlalchemy(admin.engine)
    3. (Plugin already discovered and on_register'd; no further action needed.)
    """

class LogfirePlugin:
    name = "logfire"
    def on_register(self, admin): ...
    def on_before_adapter_call(self, admin, model, op, kwargs): ...
    def on_after_adapter_call(self, admin, model, op, result): ...
    def on_validation_error(self, admin, model, field_errors): ...
    def on_auth_event(self, admin, event_type, user, **ctx): ...
```

The plugin uses `contextvars` to carry the open `logfire.span` between
`on_before_adapter_call` and `on_after_adapter_call`. Failure to find an open span
in `on_after_*` is logged at WARNING and otherwise ignored.

### Configuration Changes

`pip install hyperadmin-logfire` (or `pip install hyperadmin[logfire]` if we add a
`[project.optional-dependencies].logfire = ["hyperadmin-logfire>=0.1"]` extra to root —
recommended for discoverability).

No new env vars. Logfire's own configuration (`LOGFIRE_TOKEN`, etc.) is unchanged.

## Edge Cases & Error Handling

| Case | Handling |
|---|---|
| `logfire.configure()` not called | One-shot WARNING logged on first hook fire; all subsequent hooks no-op. Tracked via module-level `_warned` flag. |
| `logfire` not installed | Plugin entry point won't import; `PluginRegistry.discover` logs ERROR and skips. (Per Epic 1 contract — no special handling here.) |
| Open span lost (e.g. exception between before/after hook) | `on_after_adapter_call` notices missing context, logs WARNING, no-ops. |
| `instrument_admin` called twice | Logfire's `instrument_fastapi` / `instrument_sqlalchemy` are idempotent — second call no-ops at their layer. We add no extra guard. |
| Plugin disabled via `disabled_plugins=["logfire"]` | Per Epic 1 contract — plugin not loaded; `instrument_admin` called by user is also a no-op (we check `"logfire" in admin.plugins` before doing the FastAPI/SQLAlchemy instrumentation). |
| Auth event fired before `admin.user` available | `user` arg may be `None` for `login_failure`; documented in the hook signature. |
| Validation errors contain non-serialisable objects | Stringified before logging. |

## Migration & Backward Compatibility

Pure addition. No core changes (modulo the two new hooks added to Epic 1 SDD).

## Open Questions

- [ ] **Add `[project.optional-dependencies].logfire = ["hyperadmin-logfire>=0.1"]`
      to root `pyproject.toml`?** Recommend yes — `pip install hyperadmin[logfire]`
      is cleaner UX than two installs. Confirm at SDD review.
- [ ] **Span name convention** — `admin.adapter.list` vs `hyperadmin.adapter.list`?
      RFC #276 uses `admin.*`; recommend keeping that. Confirm.
- [ ] **Should `instrument_admin` also call `logfire.instrument_pydantic()`?** Tempting
      but noisy (instruments ALL Pydantic validation, not just admin forms). Recommend no.
- [ ] **Test sink fixture** — Logfire ships a test capture utility; confirm it works
      under our pytest-asyncio setup before story #8 is dispatched.

## Decision Log

| Decision | Rationale | Alternatives considered |
|---|---|---|
| Monorepo subpath `plugins/hyperadmin-logfire/` | Atomic dual-PR with Epic 1; single CI matrix; can promote later | Separate repo from day 1 — premature, slows iteration during the proof-of-concept window |
| Add two new hooks to Epic 1 SDD (`on_validation_error`, `on_auth_event`) | Avoids monkey-patching `PydanticForm` and parsing 302 redirects in middleware; matches the observer-hook pattern of the rest of the contract | (a) Patch `PydanticForm.validate()` — violates "no core changes"; (b) ASGI middleware sniffing auth responses — fragile, can't distinguish event types |
| Use `contextvars` to bridge before/after adapter hooks | Async-safe, request-scoped, doesn't require passing state through the hook signature | (a) `dict` keyed on `(thread_id, model, op)` — broken under asyncio; (b) Stash on `admin` — global mutable state |
| `instrument_admin()` does both Logfire instrumentation AND verifies plugin discovery | One call for users; clear failure mode if plugin disabled | Split into two functions — extra docs surface for no benefit |
| No span on `on_register` | One-shot; not interesting | Span — clutter in dashboards |
