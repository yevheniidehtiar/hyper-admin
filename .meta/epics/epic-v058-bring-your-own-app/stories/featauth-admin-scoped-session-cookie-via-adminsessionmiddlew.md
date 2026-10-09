---
type: story
id: st-v058-byoa-36
title: "feat(auth): admin-scoped session cookie via AdminSessionMiddleware"
status: todo
priority: high
assignee: null
labels:
  - size:M
  - planned
  - area:auth
  - layer:views
estimate: null
epic_ref:
  id: ep-v058-byoa-01
created_at: 2026-09-28T00:00:00Z
updated_at: 2026-09-28T00:00:00Z
---

## Summary

Add the settings `session_cookie`, `session_max_age`, `session_same_site` and `session_https_only`, and set the cookie path to the prefix. `AdminSessionMiddleware` saves the host's `scope['session']` and restores it before `http.response.start`.

**Spec:** [`docs/specs/bring-your-own-app.md`](../../../../docs/specs/bring-your-own-app.md) — section: C.4

## Files to Change

- `src/hyperadmin/auth/session_middleware.py`
- `src/hyperadmin/core/settings.py`
- `src/hyperadmin/core/app.py`
- `tests/unit/test_admin_session_cookie.py`

## Scenarios

```
Scenario: cookie scoped to prefix
  Given built-in auth at /admin
  When  a user logs in
  Then  Set-Cookie names hyperadmin_session with Path=/admin

Scenario: host session untouched
  Given the host SessionMiddleware with cookie 'session'
  When  the user logs in to /admin
  Then  the host session cookie is unchanged
```

## Acceptance Criteria

- [ ] cookie scoped to prefix
- [ ] host session untouched
- [ ] `poe lint` and `poe test:unit` pass

## Review amendments (2026-09-28)

- Replace `session_https_only` with `cookie_secure: "auto" | bool = "auto"` for all admin cookies. `auto` sets `Secure` from the effective request scheme, so plain-http installs and `TestClient` keep working. Add a TestClient login scenario.
- Cookie paths use the per-request admin path (`admin_base_path`), which honours the host's `root_path`. Add a scenario with the host under `root_path="/api"`.
- Fix `views/locale.py`: the cookie path is the admin path, not the hard-coded `"/admin"`, and a `Referer` is used only when it is same-origin and under the admin path (open-redirect fix). Add scenarios for `mount("/backoffice")` and an off-site `Referer`.
- Route `AuthenticationMiddleware`'s `login_url` and the redirects in `auth/views.py` through the admin path.

## Blocked by

- `featcore-isolated-sub-application-mount` (st-v058-byoa-35)

## Parent

- Epic: `epic-v058-bring-your-own-app` (v0.5.8 — Bring Your Own App)
