---
type: story
id: st-v058-byoa-35
title: "feat(core): isolated sub-application mount"
status: todo
priority: high
assignee: null
labels:
  - size:M
  - planned
  - area:core
  - layer:views
estimate: null
epic_ref:
  id: ep-v058-byoa-01
created_at: 2026-09-28T00:00:00Z
updated_at: 2026-09-28T00:00:00Z
---

## Summary

`mount()` builds a private FastAPI sub-app with no OpenAPI and attaches it with `app.mount(path, name=route_namespace)`. Middleware is scoped to the admin, and `/static` and `/realtime/ws` move under the prefix (the static mount leaves `__init__`). `mount_mode='router'` is the legacy mode with a `DeprecationWarning`, and `mount('/')` forces router mode. The auth prefix check becomes segment-safe.

**Spec:** [`docs/specs/bring-your-own-app.md`](../../../../docs/specs/bring-your-own-app.md) — section: C.1

## Files to Change

- `src/hyperadmin/core/app.py`
- `src/hyperadmin/core/settings.py`
- `src/hyperadmin/auth/middleware.py`
- `src/hyperadmin/i18n/middleware.py`
- `tests/unit/test_isolated_mount.py`
- `tests/unit/test_admin_prefix.py`

## Scenarios

```
Scenario: host routes untouched
  Given GET /health on the host
  When  it is requested
  Then  there is no Content-Language header

Scenario: host static keeps working
  Given the host mounts /static
  When  the dashboard renders
  Then  its stylesheet is served from /admin/static

Scenario: segment-safe prefix
  Given auth at /admin in router mode
  When  GET /administrator is requested
  Then  no redirect to /admin/login occurs

Scenario: not in host OpenAPI
  Given isolated mode
  When  GET /openapi.json is requested
  Then  no path starts with /admin

Scenario: router mode legacy
  Given mount_mode='router'
  When  the admin is mounted
  Then  a DeprecationWarning is emitted
  And   routes use un-namespaced names
```

## Acceptance Criteria

- [ ] host routes untouched
- [ ] host static keeps working
- [ ] segment-safe prefix
- [ ] not in host OpenAPI
- [ ] router mode legacy
- [ ] `poe lint` and `poe test:unit` pass

## Blocked by

- `featcore-lifecycle-with-opt-in-create-tables-startup-shutdow` (st-v058-byoa-26)
- `featviews-namespace-aware-url-helper-and-jinja-url-for-overr` (st-v058-byoa-34)

## Parent

- Epic: `epic-v058-bring-your-own-app` (v0.5.8 — Bring Your Own App)
