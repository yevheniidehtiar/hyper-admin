---
type: story
id: st-v058-byoa-20
title: "refactor(db): lazy default engine; deprecate hyperadmin.db.engine"
status: todo
priority: high
assignee: null
labels:
  - size:S
  - planned
  - area:core
  - layer:domain
estimate: null
epic_ref:
  id: ep-v058-byoa-01
created_at: 2026-09-28T00:00:00Z
updated_at: 2026-09-28T00:00:00Z
---

## Summary

Stop `db.py` from creating an engine when it is imported. Add `get_default_engine(settings)`, which is built lazily from `settings.database_url` and cached per URL. A module-level `__getattr__('engine')` keeps the old import working with a `DeprecationWarning`. Stop importing `default_engine` at the top of `core/app.py`.

**Spec:** [`docs/specs/bring-your-own-app.md`](../../../../docs/specs/bring-your-own-app.md) — section: C.3

## Files to Change

- `src/hyperadmin/db.py`
- `src/hyperadmin/core/app.py`
- `tests/unit/test_db_lazy_engine.py`

## Scenarios

```
Scenario: importing hyperadmin creates no engine
  Given a fresh interpreter
  When  import hyperadmin runs
  Then  create_async_engine has not been called

Scenario: legacy engine import still works
  Given a fresh interpreter
  When  from hyperadmin.db import engine runs
  Then  an AsyncEngine is returned
  And   a DeprecationWarning is emitted
```

## Acceptance Criteria

- [ ] importing hyperadmin creates no engine
- [ ] legacy engine import still works
- [ ] `poe lint` and `poe test:unit` pass

## Review amendments (2026-09-28)

- Remove `core/app.py:17` (`from hyperadmin.db import engine as default_engine`, used at `:85`). `Admin.__init__` calls `get_default_engine()` lazily, only in demo mode. Otherwise the deprecated `__getattr__("engine")` fires on every `import hyperadmin`, and the scenario "importing hyperadmin creates no engine" fails.
- Add `db.create_tables(engine, tables)`, `db.resolve_bind(session_factory)` and `db.is_sqlite_url(url)`. The DDL lives here, not in `core/`.

## Blocked by

- `reviewspec-approve-byoa-sdd` (st-v058-byoa-00)

## Parent

- Epic: `epic-v058-bring-your-own-app` (v0.5.8 — Bring Your Own App)
