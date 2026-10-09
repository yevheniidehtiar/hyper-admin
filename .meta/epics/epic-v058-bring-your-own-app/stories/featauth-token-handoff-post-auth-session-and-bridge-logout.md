---
type: story
id: st-v058-byoa-41
title: "feat(auth): token handoff, bearer login form, JWT-exp cookie lifetime and bridge logout"
status: todo
priority: high
assignee: null
labels:
  - size:M
  - planned
  - area:auth
  - layer:views
  - security
estimate: null
epic_ref:
  id: ep-v058-byoa-01
created_at: 2026-09-28T00:00:00Z
updated_at: 2026-09-28T00:00:00Z
---

## Summary

Add a public-router `POST {prefix}/auth/session`, which validates the bearer token through the host dependency and sets the admin-scoped `HttpOnly` cookie. It returns 400 for oversized tokens and 401 for invalid ones. Add `POST {prefix}/logout`, which clears the cookie and redirects to `logout_url`. `next` only accepts values inside the admin prefix.

**Spec:** [`docs/specs/bring-your-own-app.md`](../../../../docs/specs/bring-your-own-app.md) — section: B.4

## Files to Change

- `src/hyperadmin/auth/bridge.py`
- `src/hyperadmin/core/app.py`
- `tests/unit/test_auth_token_handoff.py`

## Scenarios

```
Scenario: handoff sets cookie
  Given ExternalAuth(token_cookie=TokenCookie()) at /admin
  When  POST /admin/auth/session is sent with a valid bearer
  Then  hyperadmin_token is set HttpOnly, SameSite=Lax, Path=/admin
  And   a following GET /admin/ with only that cookie returns 200

Scenario: invalid token rejected
  Given the host rejects 'Bearer bad'
  When  POST /admin/auth/session is sent
  Then  the response is 401
  And   no cookie is set

Scenario: oversized token
  Given a 5000-byte token
  When  POST /admin/auth/session is sent
  Then  the response is 400

Scenario: logout clears cookie
  Given a token cookie
  When  POST /admin/logout is sent with a CSRF token
  Then  the cookie is cleared
  And   the response redirects to logout_url

Scenario: no open redirect
  Given next=https://evil.example
  When  the handoff succeeds
  Then  the redirect stays under /admin
```

## Acceptance Criteria

- [ ] handoff sets cookie
- [ ] invalid token rejected
- [ ] oversized token
- [ ] logout clears cookie
- [ ] no open redirect
- [ ] `poe lint` and `poe test:unit` pass

## Review amendments (2026-09-28)

- The handoff route is protected by `Depends(build_admin_dependency(auth))`, with no internal sub-app request (this resolves Open Question 2). It is exempt from CSRF.
- Add the opt-in admin login form for bearer hosts (`TokenCookie(token_endpoint=...)`). It posts credentials server side to the host token endpoint and stores the access token in the cookie.
- The cookie's `Max-Age` is `min(max_age, jwt exp - now)`. A rejected cookie token is cleared before the redirect.
- `next` validation: a relative path under the admin path plus `/`; `//`, backslashes and schemes are rejected.
- Add a scenario: a bearer-only host with no frontend change reaches `/admin` in a browser.

## Blocked by

- `featcore-adminauth-externalauth-wiring-and-opt-in-built-in-a` (st-v058-byoa-40)

## Parent

- Epic: `epic-v058-bring-your-own-app` (v0.5.8 — Bring Your Own App)
