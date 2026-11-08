---
type: story
id: st-perf-05
title: "feat(auth): resolve a user's permissions once per request"
status: todo
priority: medium
assignee: null
labels:
  - size:S
  - area:auth
  - performance
estimate: null
epic_ref:
  id: fkINeqAy7AVG
created_at: 2026-11-08T00:00:00Z
updated_at: 2026-11-08T00:00:00Z
---

## Summary

`ModelPermissionChecker.has_permission` runs two SELECTs (direct permissions, then group permissions, each in its own session) for every non-superuser check, and nothing remembers the answer within a request. The sidebar filter (`core/app.py`, one `view_<model>` check per registered model) plus the route guard and the list view's `change_` and `delete_` checks mean a page costs about two queries per registered model, plus a few more. The count test below measures the real figure first. `st-perf-04` caches across requests and is off by default; this story removes the repeat inside one request with no staleness and no setting.

Resolve the user's full permission set once and answer every later check in the same request from it. The user object is created per request by `get_current_user`, so the set can live on that instance.

## Files to Change

- **Modified:** `src/hyperadmin/auth/permissions.py`
- **New:** `tests/unit/test_permission_query_count.py`

## Scenarios

```
Scenario: many checks in one request cost two queries
  Given a staff user with a group permission and 20 registered models
  When  GET /admin/invoice/
  Then  the permission step runs 2 SQL statements in total

Scenario: a new request sees a changed permission
  Given a staff user whose permission was just revoked
  When  the next request arrives
  Then  the revoked permission is denied

Scenario: a superuser costs nothing
  Given a signed-in superuser
  When  GET /admin/invoice/
  Then  the permission step runs 0 SQL statements
```

## Acceptance Criteria

- [ ] `get_user_permissions` resolves both sources at most once per user object, in one session
- [ ] A SQL-counting test asserts the 2-statement bound on a list page with many registered models
- [ ] Revoking or granting a permission is visible on the next request (no cross-request state)
- [ ] The permissions matrix save invalidates the set for the user object it may hold in the same request
- [ ] `uv run poe test:cov-diff` reports 100% of changed lines
- [ ] Load-test number for `pg-9cpu-400u` recorded in the PR

## Blocked by

- none (independent of `featauth-optional-short-ttl-cache-for-the-current-user`, which this complements)

## Parent

- Epic: `epic-adapter-query-performance-selectinload-pagination-count`
