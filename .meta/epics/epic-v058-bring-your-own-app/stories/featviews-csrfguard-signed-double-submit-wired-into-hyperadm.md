---
type: story
id: st-v058-byoa-39
title: "feat(views): CsrfGuard signed double-submit wired into HyperAdminRoute and settings"
status: todo
priority: high
assignee: null
labels:
  - size:M
  - planned
  - area:views
  - layer:views
  - security
estimate: null
epic_ref:
  id: ep-v058-byoa-01
created_at: 2026-09-28T00:00:00Z
updated_at: 2026-09-28T00:00:00Z
---

## Summary

Add `views/csrf.py` `CsrfGuard`, which does cookie issuance, header or form token extraction, and `Sec-Fetch-Site`/`Origin` checks. Add the `csrf_*` settings and the `auto`/`enforce`/`report`/`off` modes. `_validate_secret_key` also fires when enforcing. Add a `csrf_client` test helper in `tests/conftest.py`.

**Spec:** [`docs/specs/bring-your-own-app.md`](../../../../docs/specs/bring-your-own-app.md) — section: D.1

## Files to Change

- `src/hyperadmin/views/csrf.py`
- `src/hyperadmin/views/route.py`
- `src/hyperadmin/core/settings.py`
- `src/hyperadmin/core/app.py`
- `tests/conftest.py`
- `tests/unit/test_csrf_guard.py`

## Scenarios

```
Scenario: missing token rejected
  Given a logged-in built-in session user
  When  DELETE /admin/order/5 is sent with HX-Request and no X-CSRF-Token
  Then  the response is 403 with X-HyperAdmin-CSRF: failed
  And   order 5 still exists

Scenario: cross-site origin rejected
  Given a valid cookie and token pair
  When  POST /admin/order is sent with Origin: https://evil.example
  Then  the response is 403

Scenario: report mode allows
  Given HYPERADMIN_CSRF_MODE=report
  When  POST /admin/order is sent without a token
  Then  the request is processed
  And   a WARNING mentioning csrf is logged

Scenario: off without auth
  Given Admin() with no auth
  When  POST /admin/order is sent without a token
  Then  the response is not 403

Scenario: multipart with header token
  Given a multipart upload with the header token
  When  it is posted
  Then  the endpoint receives the file intact
```

## Acceptance Criteria

- [ ] missing token rejected
- [ ] cross-site origin rejected
- [ ] report mode allows
- [ ] off without auth
- [ ] multipart with header token
- [ ] `poe lint` and `poe test:unit` pass

## Blocked by

- `featviews-hyperadminroute-route-class-with-auth-error-transl` (st-v058-byoa-38)

## Parent

- Epic: `epic-v058-bring-your-own-app` (v0.5.8 — Bring Your Own App)
