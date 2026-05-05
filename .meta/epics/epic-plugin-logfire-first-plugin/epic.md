---
type: epic
id: Plo-enMpTWhB
title: "epic(plugin-logfire): hyperadmin-logfire — first official plugin"
status: todo
priority: high
owner: null
labels:
  - size:L
  - planned
  - plugins
  - observability
milestone_ref:
  id: XnHVJphQRoMf
created_at: 2026-05-05T00:00:00Z
updated_at: 2026-05-05T00:00:00Z
---

## Overview

Ship `hyperadmin-logfire` — a separate package that instruments HyperAdmin with
Pydantic Logfire for per-model CRUD spans, query performance, validation
failure rates, and auth event tracing. **The first official HyperAdmin plugin
and the proof-of-concept for the plugin registry contract.**

If this plugin requires changes to `src/hyperadmin/core/` beyond the hooks
defined in the registry SDD, the registry SDD must be revised. That is the
design pressure on this work.

**Repo layout:** monorepo subpath `plugins/hyperadmin-logfire/` with its own
`pyproject.toml` and PyPI release pipeline.

**SDD:** [`docs/specs/plugin-logfire.md`](../../../docs/specs/plugin-logfire.md)
(required — separate package + cross-repo coordination + new hooks).

## Tracks

### Track A: Package scaffold
- `plugins/hyperadmin-logfire/pyproject.toml` with `[project.entry-points."hyperadmin.plugins"]`.
- Source layout: `src/hyperadmin_logfire/{__init__.py, plugin.py, adapter_spans.py, auth_events.py, _config_check.py}`.
- Workspace integration: root `pyproject.toml` adds `plugins/hyperadmin-logfire` to `[tool.uv.workspace.members]`.

### Track B: Adapter + HTTP + SQL spans
- `LogfirePlugin.on_before_adapter_call` opens `admin.adapter.<op>` span (carried in `contextvars`).
- `on_after_adapter_call` closes the span with the result.
- `instrument_admin(admin)` calls `logfire.instrument_fastapi(admin.app)` and
  `logfire.instrument_sqlalchemy(admin.engine)` — HTTP and SQL spans nested under adapter spans.

### Track C: Validation + auth events
- `on_validation_error` (new hook in registry SDD) emits `admin.validation_error` events.
- `on_auth_event` (new hook in registry SDD) emits `admin.auth.{login_success,login_failure,logout,permission_denied}` events.

### Track D: CI + docs
- `.github/workflows/*.yml` — add `plugins/hyperadmin-logfire` to test matrix.
- README + main-docs link.

## Scenarios

**Scenario: instrument_admin attaches the plugin and emits adapter spans**
  Given logfire is configured to capture spans in a test sink
  And   instrument_admin(admin) has been called
  When  the admin.products list view is requested
  Then  the test sink contains a span named "admin.adapter.list" with attribute model="Product"

**Scenario: validation failure emits a structured event**
  Given logfire is configured to capture events
  When  POST /admin/products/create with an invalid payload
  Then  the sink contains an event "admin.validation_error" with attributes model="Product" and field_errors non-empty

**Scenario: failed login emits an auth event**
  Given logfire is configured to capture events
  When  POST /admin/login with username=alice password=wrong
  Then  the sink contains an event "admin.auth.login_failure" with attribute username="alice"

**Scenario: plugin no-ops when logfire is not configured**
  Given logfire.configure() was NOT called
  When  Admin is constructed and a list view is requested
  Then  no exceptions are raised
  And   a single warning log mentions hyperadmin-logfire requires logfire.configure()

**Scenario: plugin is not loaded when disabled**
  Given hyperadmin-logfire is installed
  When  Admin(app, engine=engine, disabled_plugins=["logfire"]) is constructed
  Then  no admin.adapter.* spans are emitted on subsequent requests

## Acceptance Criteria

- [ ] `instrument_admin(admin)` attaches plugin and emits adapter spans
- [ ] Validation failure emits a structured `admin.validation_error` event
- [ ] Failed login emits a `admin.auth.login_failure` event
- [ ] Plugin no-ops with a one-shot warning when `logfire.configure()` not called
- [ ] Plugin is not loaded when disabled via `disabled_plugins=["logfire"]`
- [ ] Unit + E2E tests for all five scenarios
- [ ] Package published to PyPI as `hyperadmin-logfire`
- [ ] README and main-docs link
- [ ] **Zero changes to `src/hyperadmin/core/`** beyond the hooks added to the registry SDD

## Cross-epic dependency

This epic adds two new hooks (`on_validation_error`, `on_auth_event`) to the
registry SDD. They must be added before the registry SDD is approved. If they
slip, this epic re-plans how validation/auth events get emitted (likely option:
direct middleware listener, ugly).

## Blocked by

- `epic-plugins-registry-and-lifecycle-hooks` (Plugin contract must exist)
