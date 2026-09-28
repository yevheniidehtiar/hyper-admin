---
type: story
id: st-v058-byoa-21
title: "feat(core): session_factory seam on BaseAdapter, adapters and auth services"
status: todo
priority: high
assignee: null
labels:
  - size:M
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

Add the typing-only `SessionFactory` alias to `BaseAdapter.__init__(model, engine=None, *, session_factory=None)` along with `_session()`. Move all 20 `AsyncSession(self.engine)` sites to `self._session()`, add the same keyword to the auth services, and add `Admin(session_factory=...)`.

**Spec:** [`docs/specs/bring-your-own-app.md`](../../../../docs/specs/bring-your-own-app.md) — section: C.3

## Files to Change

- `src/hyperadmin/core/adapters.py`
- `src/hyperadmin/adapters/sqlmodel.py`
- `src/hyperadmin/adapters/sqlalchemy.py`
- `src/hyperadmin/auth/session.py`
- `src/hyperadmin/auth/permissions.py`
- `src/hyperadmin/auth/views.py`
- `src/hyperadmin/routing.py`
- `src/hyperadmin/core/app.py`
- `tests/unit/test_session_factory.py`

## Scenarios

```
Scenario: host session factory is used
  Given Admin(session_factory=host_sessionmaker)
  When  the user list page is requested
  Then  host_sessionmaker was called

Scenario: legacy engine-only adapter works
  Given a custom adapter calling super().__init__(model, engine)
  When  list() runs
  Then  rows are returned

Scenario: neither engine nor factory
  Given BaseAdapter(model) with neither argument
  When  it is constructed
  Then  ValueError is raised
```

## Acceptance Criteria

- [ ] host session factory is used
- [ ] legacy engine-only adapter works
- [ ] neither engine nor factory
- [ ] `poe lint` and `poe test:unit` pass

## Blocked by

- `refactordb-lazy-default-engine-deprecate-hyperadmin-db-engin` (st-v058-byoa-20)

## Parent

- Epic: `epic-v058-bring-your-own-app` (v0.5.8 — Bring Your Own App)
