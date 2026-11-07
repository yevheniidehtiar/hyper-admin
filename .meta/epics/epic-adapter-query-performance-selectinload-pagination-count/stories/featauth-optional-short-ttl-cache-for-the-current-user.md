---
type: story
id: st-perf-04
title: "feat(auth): optional short-TTL cache for the current user and permissions"
status: todo
priority: medium
assignee: null
labels:
  - size:M
  - area:auth
  - performance
estimate: null
epic_ref:
  id: fkINeqAy7AVG
created_at: 2026-11-07T00:00:00Z
updated_at: 2026-11-07T00:00:00Z
---

## Summary

Add `user_cache_ttl` (seconds, default 0 = off). When set, `AuthenticationMiddleware` keeps the user and permission set in a per-worker TTL cache keyed by session user id. Writes to users and permissions drop the entry on the same worker. Other workers may serve a stale user for up to the TTL, so the docs state the tradeoff.

## Files to Change

- **Modified:** `src/hyperadmin/core/settings.py`, `src/hyperadmin/auth/middleware.py`, `src/hyperadmin/auth/permissions.py`
- **Modified:** `docs/` security notes, `docker-compose.loadtest-matrix.yml` (enable at 5 s)
- **New:** `tests/unit/test_user_cache.py`

## Scenarios

```
Scenario: repeated requests load the user once
  Given user_cache_ttl is 5
  When  100 requests arrive in one second from one session
  Then  the user is loaded once

Scenario: a deactivated user is locked out after the TTL
  Given the user is cached and then deactivated
  When  the TTL has passed and the next request arrives
  Then  the response redirects to login

Scenario: TTL 0 keeps today's behaviour
  Given user_cache_ttl is 0
  When  two requests arrive
  Then  the user is loaded twice
```

## Acceptance Criteria

- [ ] `HyperAdminSettings.user_cache_ttl: int = 0` (`ge=0`, env `HYPERADMIN_USER_CACHE_TTL`) documented
- [ ] Permission or user writes on the same worker invalidate the entry
- [ ] Docs state the multi-worker staleness window
- [ ] `uv run poe test:cov-diff` reports 100% of changed lines
- [ ] Load-test number for `pg-9cpu-400u` recorded in the PR

## Blocked by

- `refactorcore-convert-the-http-middleware-to-plain-asgi` (st-perf-03), same file
- `featauth-slim-the-per-request-user-load` (st-perf-01)

## Parent

- Epic: `epic-adapter-query-performance-selectinload-pagination-count`
