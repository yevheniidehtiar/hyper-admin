---
type: story
id: st-v058-byoa-46
title: "feat(ui): bridge-aware navbar and CSRF reload banner"
status: todo
priority: high
assignee: null
labels:
  - size:M
  - planned
  - area:templates
  - layer:ui
  - frontend
  - security
estimate: null
epic_ref:
  id: ep-v058-byoa-01
created_at: 2026-09-28T00:00:00Z
updated_at: 2026-09-28T00:00:00Z
---

## Summary

Add `_base.html` `<body hx-headers>` with the token, a `<meta name='csrf-token'>` tag, and `{{ csrf_input() }}` in every plain POST form. Show a reload banner on a 403 carrying `X-HyperAdmin-CSRF`. The navbar uses `request.state.user_display` and the bridge logout.

**Spec:** [`docs/specs/bring-your-own-app.md`](../../../../docs/specs/bring-your-own-app.md) — section: D.1

## Files to Change

- `src/hyperadmin/templates/_base.html`
- `src/hyperadmin/templates/_navbar.html`
- `src/hyperadmin/templates/login.html`
- `src/hyperadmin/templates/auth/mfa_challenge.html`
- `src/hyperadmin/templates/auth/mfa_settings.html`
- `src/hyperadmin/templates/components/bulk_form.html`
- `src/hyperadmin/templates/components/bulk_result.html`
- `src/hyperadmin/templates/widgets/popup_form.html`
- `src/hyperadmin/core/app.py`
- `tests/e2e/test_csrf.py`

## Scenarios

```
Scenario: HTMX delete carries token
  Given the list page rendered with body hx-headers
  When  the delete button issues DELETE /admin/order/5
  Then  the response is 200
  And   order 5 is deleted

Scenario: plain form hidden field
  Given the login page rendered a hidden csrf_token input
  When  POST /admin/login is sent with valid credentials
  Then  the response is 302 to /admin/

Scenario: login CSRF blocked
  Given no hyperadmin_csrf cookie
  When  a cross-site form POSTs /admin/login
  Then  the response is 403
  And   no session is created

Scenario: stale token banner
  Given a stale CSRF cookie
  When  an HTMX POST gets 403 with X-HyperAdmin-CSRF
  Then  get_by_test_id('csrf-reload-banner') is visible

Scenario: bridged navbar
  Given a bridged user with display name 'Ada'
  When  the dashboard renders
  Then  the navbar shows 'Ada'
```

## Acceptance Criteria

- [ ] HTMX delete carries token
- [ ] plain form hidden field
- [ ] login CSRF blocked
- [ ] stale token banner
- [ ] bridged navbar
- [ ] `poe lint` and `poe test:unit` pass (and `poe test:e2e`)

## Review amendments (2026-09-28)

- CSRF token injection (`hx-headers`, meta and `csrf_input`) moved to `-39`, so enforcement and injection ship together. This story keeps only the bridge-aware navbar (logout form, display name) and the "reload page" banner for 403s that carry `X-HyperAdmin-CSRF`.

## Blocked by

- `featcore-adminauth-externalauth-wiring-and-opt-in-built-in-a` (st-v058-byoa-40)

## Parent

- Epic: `epic-v058-bring-your-own-app` (v0.5.8 — Bring Your Own App)
