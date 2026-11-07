---
type: story
id: st-perf-01
title: "feat(auth): load the current user without eager-loading groups and permissions"
status: done
priority: high
assignee: null
labels:
  - size:S
  - area:auth
  - performance
estimate: null
epic_ref:
  id: fkINeqAy7AVG
created_at: 2026-11-07T00:00:00Z
updated_at: 2026-11-07T00:00:00Z
---

## Summary

`SessionAuthBackend.get_current_user` runs 3 SELECTs per request because `User.user_groups` and `User.user_permissions` are `lazy="selectin"`. Load the user with `noload` on both, so an authenticated request runs one auth query. The model default stays, so downstream apps are unaffected.

## Files to Change

- **Modified:** `src/hyperadmin/auth/session.py`
- **New:** `tests/unit/test_auth_query_count.py`

## Scenarios

```
Scenario: a superuser's request loads the user once
  Given a signed-in superuser
  When  GET /admin/invoice/
  Then  the auth step runs 1 SQL statement

Scenario: a staff user's permissions still resolve
  Given a staff user with a group permission
  When  GET /admin/invoice/
  Then  the page renders and the permission is honoured
```

## Acceptance Criteria

- [ ] Audit: nothing in `src/` or `examples/` reads `user.user_groups` / `user.user_permissions` from the object `get_current_user` returns
- [ ] A SQL-counting test asserts the auth step runs 1 statement
- [ ] `uv run poe test:cov-diff` reports 100% of changed lines
- [ ] Load-test number for `pg-9cpu-400u` recorded in the PR

## Blocked by

- none

## Parent

- Epic: `epic-adapter-query-performance-selectinload-pagination-count`
