---
type: story
id: st-v058-byoa-26
title: "feat(core): lifecycle with opt-in create_tables, startup/shutdown/lifespan, first-request guard and init-db CLI"
status: todo
priority: high
assignee: null
labels:
  - size:M
  - planned
  - area:core
  - layer:logic
estimate: null
epic_ref:
  id: ep-v058-byoa-01
created_at: 2026-09-28T00:00:00Z
updated_at: 2026-09-28T00:00:00Z
---

## Summary

Add `core/lifecycle.py` and the public `Admin.startup()`, `shutdown()`, `lifespan()` and `create_tables(scope=)`. Change `create_tables` to default to `False`, except in demo mode. Add the `_StartupGuard`, remove every `on_event`/`on_startup` use, and add the `hyperadmin init-db` command. Keep the private aliases for one release.

**Spec:** [`docs/specs/bring-your-own-app.md`](../../../../docs/specs/bring-your-own-app.md) — section: C.2

## Files to Change

- `src/hyperadmin/core/lifecycle.py`
- `src/hyperadmin/core/settings.py`
- `src/hyperadmin/core/app.py`
- `src/hyperadmin/management/commands/initdb.py`
- `src/hyperadmin/__main__.py`
- `examples/erp/main.py`
- `tests/unit/test_lifecycle.py`

## Scenarios

```
Scenario: tables are not created by default
  Given Admin with a host engine and default settings
  When  the app starts
  Then  no CREATE TABLE is executed

Scenario: demo mode still works
  Given Admin(app) with no engine and no session factory
  When  GET /admin/ is requested
  Then  the status is 200

Scenario: permission sync under a host lifespan
  Given FastAPI(lifespan=host_lifespan) with built-in auth
  When  the first admin request arrives
  Then  permissions are synced exactly once

Scenario: init-db creates only hyperadmin tables
  Given an empty DB and host SQLModel models imported
  When  hyperadmin init-db --database-url URL runs
  Then  only hyperadmin_* tables exist
```

## Acceptance Criteria

- [ ] tables are not created by default
- [ ] demo mode still works
- [ ] permission sync under a host lifespan
- [ ] init-db creates only hyperadmin tables
- [ ] `poe lint` and `poe test:unit` pass

## Blocked by

- `refactorauth-lazy-auth-package-exports-and-auth-metadata` (st-v058-byoa-17)
- `featcore-session-factory-seam-on-baseadapter-adapters-and-au` (st-v058-byoa-21)

## Parent

- Epic: `epic-v058-bring-your-own-app` (v0.5.8 — Bring Your Own App)
