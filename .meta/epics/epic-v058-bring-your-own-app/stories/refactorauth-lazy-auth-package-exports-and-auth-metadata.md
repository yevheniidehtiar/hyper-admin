---
type: story
id: st-v058-byoa-17
title: "refactor(auth): lazy auth package exports and auth.metadata()"
status: todo
priority: high
assignee: null
labels:
  - size:S
  - planned
  - area:auth
  - layer:domain
estimate: null
epic_ref:
  id: ep-v058-byoa-01
created_at: 2026-09-28T00:00:00Z
updated_at: 2026-09-28T00:00:00Z
---

## Summary

Convert `auth/__init__.py` to PEP 562 lazy `__getattr__`, so that importing `hyperadmin.auth.bridge` or `hyperadmin.auth.middleware` does not register `hyperadmin_*` tables. Add `metadata()`, which returns only the `hyperadmin_*` tables for Alembic.

**Spec:** [`docs/specs/bring-your-own-app.md`](../../../../docs/specs/bring-your-own-app.md) — section: B.5

## Files to Change

- `src/hyperadmin/auth/__init__.py`
- `tests/unit/test_auth_lazy_imports.py`

## Scenarios

```
Scenario: importing auth submodules registers no tables
  Given a fresh interpreter (subprocess)
  When  hyperadmin.auth.middleware is imported
  Then  SQLModel.metadata has no hyperadmin_users table

Scenario: back-compat import
  Given a fresh interpreter
  When  from hyperadmin.auth import User runs
  Then  User is the built-in model

Scenario: metadata() returns only hyperadmin tables
  Given host SQLModel tables are registered
  When  hyperadmin.auth.metadata() is called
  Then  only hyperadmin_* tables are in the result
```

## Acceptance Criteria

- [ ] importing auth submodules registers no tables
- [ ] back-compat import
- [ ] metadata() returns only hyperadmin tables
- [ ] `poe lint` and `poe test:unit` pass

## Review amendments (2026-09-28)

- Document that `metadata()` is for built-in-auth hosts only. Calling it imports `auth/models.py`, which registers the `hyperadmin_*` tables on the global `SQLModel.metadata`. It logs a `WARNING` if an `Admin` in bridge mode was already constructed.

## Blocked by

- `reviewspec-approve-byoa-sdd` (st-v058-byoa-00)

## Parent

- Epic: `epic-v058-bring-your-own-app` (v0.5.8 — Bring Your Own App)
