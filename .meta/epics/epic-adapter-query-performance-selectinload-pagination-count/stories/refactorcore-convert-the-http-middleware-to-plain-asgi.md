---
type: story
id: st-perf-03
title: "refactor(core): convert the BaseHTTPMiddleware classes to plain ASGI"
status: todo
priority: high
assignee: null
labels:
  - size:L
  - area:core
  - area:auth
  - performance
estimate: null
epic_ref:
  id: fkINeqAy7AVG
created_at: 2026-11-07T00:00:00Z
updated_at: 2026-11-07T00:00:00Z
---

## Summary

`BaseHTTPMiddleware` adds per-request overhead on every layer. Convert, one commit each: `LocaleMiddleware`, `AuthenticationMiddleware`. `StartupGuardMiddleware` was already plain ASGI (pinned by tests) and `realtime/` has no middleware class. Behaviour is unchanged; the existing suites are the spec.

**Spec:** [`docs/specs/asgi-middleware.md`](../../../../docs/specs/asgi-middleware.md)

## Files to Change

- **Modified:** `src/hyperadmin/i18n/middleware.py`, `src/hyperadmin/auth/middleware.py`
- **New:** `tests/unit/test_asgi_middleware.py`

## Scenarios

```
Scenario: non-HTTP scopes pass through untouched
  Given the admin app
  When  a websocket or lifespan scope arrives
  Then  each middleware forwards it to the inner app

Scenario: an anonymous request is redirected to login
  Given auth is configured
  When  GET /admin/ without a session
  Then  the response is a 302 to /admin/login

Scenario: a streaming response is not buffered
  Given an SSE endpoint behind the middleware stack
  When  the client reads the stream
  Then  events arrive as they are sent
```

## Acceptance Criteria

- [ ] No `BaseHTTPMiddleware` import remains in `src/hyperadmin`
- [ ] Existing auth, MFA, locale, lifecycle and realtime tests pass unchanged
- [ ] `core/app.py` is not edited (same class names in `add_middleware`)
- [ ] E2E suite green, including the SSE path
- [ ] `uv run poe test:cov-diff` reports 100% of changed lines
- [ ] Load-test number for `pg-9cpu-400u` recorded in the PR

## Blocked by

- `reviewspec-approve-asgi-middleware-sdd` (st-perf-02)

## Parent

- Epic: `epic-adapter-query-performance-selectinload-pagination-count`
