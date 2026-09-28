---
type: story
id: st-v058-byoa-38
title: "feat(views): HyperAdminRoute route class with auth-error translation and token-cookie bridging"
status: todo
priority: high
assignee: null
labels:
  - size:M
  - planned
  - area:views
  - layer:views
estimate: null
epic_ref:
  id: ep-v058-byoa-01
created_at: 2026-09-28T00:00:00Z
updated_at: 2026-09-28T00:00:00Z
---

## Summary

Add `views/route.py` `make_admin_route_class()`, set as `route_class` on every admin router. It maps `AdminAuthenticationRequired`, `AdminAccessDenied` and host 401/403 errors to a redirect, `HX-Redirect`, `HX-Refresh` or 403, and copies the token cookie into `Authorization` when no such header is present.

**Spec:** [`docs/specs/bring-your-own-app.md`](../../../../docs/specs/bring-your-own-app.md) — section: B.2

## Files to Change

- `src/hyperadmin/views/route.py`
- `src/hyperadmin/routing.py`
- `src/hyperadmin/core/app.py`
- `tests/unit/test_admin_route_class.py`

## Scenarios

```
Scenario: anonymous browser redirected
  Given ExternalAuth(login_url='/login')
  And   dep returns None
  When  GET /admin/order?page=2 is requested
  Then  the response is 303 to /login?next=%2Fadmin%2Forder%3Fpage%3D2

Scenario: host 401 treated as anonymous
  Given dep uses OAuth2PasswordBearer(auto_error=True)
  When  GET /admin/ is requested without Authorization
  Then  the response is 303 to login_url

Scenario: HTMX gets HX-Redirect
  Given dep returns None
  When  an HX-Request DELETE /admin/order/5 is sent
  Then  the response is 401 with HX-Redirect

Scenario: can_access failure is 403
  Given can_access returns False
  When  GET /admin/ is requested
  Then  the response is 403 without redirect

Scenario: header wins over cookie
  Given a token cookie for A
  When  GET /admin/ is sent with Authorization for B
  Then  request.state.user is B

Scenario: API prefix gets 401
  Given dep returns None
  When  GET /admin/realtime/sse is requested
  Then  the response is 401
```

## Acceptance Criteria

- [ ] anonymous browser redirected
- [ ] host 401 treated as anonymous
- [ ] HTMX gets HX-Redirect
- [ ] can_access failure is 403
- [ ] header wins over cookie
- [ ] API prefix gets 401
- [ ] `poe lint` and `poe test:unit` pass

## Review amendments (2026-09-28)

- The pipeline order is fixed, with one `Request` object throughout:
  1. Bridge the token cookie by mutating `scope["headers"]` before any body read.
  2. Solve auth.
  3. Verify CSRF on the same `Request` that is passed to the handler.
  4. Run the handler and attach the CSRF cookie.
  No second `Request` is built from a copied scope.
- Only `AdminAccessDenied` and 403s raised during dependency solving map to the `can_access` page. `HTTPException(403)` raised by views passes through unchanged.
- When the host rejects a token that came from the cookie, clear the cookie before redirecting.
- Add a unit test: a plain multipart POST with the token cookie and a body `csrf_token` reaches the handler with every field.

## Blocked by

- `featcore-admin-auth-exceptions-and-pure-csrftokensigner` (st-v058-byoa-18)
- `featcore-isolated-sub-application-mount` (st-v058-byoa-35)

## Parent

- Epic: `epic-v058-bring-your-own-app` (v0.5.8 — Bring Your Own App)
