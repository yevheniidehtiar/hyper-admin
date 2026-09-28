---
type: story
id: st-v058-byoa-51
title: "docs(guides): existing-app guide, examples/byoa, CSRF upgrade note and multi-tenancy SDD amendment"
status: todo
priority: high
assignee: null
labels:
  - size:M
  - planned
  - area:docs
  - layer:ui
  - docs
estimate: null
epic_ref:
  id: ep-v058-byoa-01
created_at: 2026-09-28T00:00:00Z
updated_at: 2026-09-28T00:00:00Z
---

## Summary

Write `docs/guides/existing-app.md` (in the nav) and `docs/guides/external-auth.md`. Add a runnable `examples/byoa/`: a host app with its own lifespan, `/static`, a `session` cookie, JWT-protected `/api`, UUID and natural-str models, and `Admin(auth=ExternalAuth(...), session_factory=...)`. Add a boot test and an e2e test. Add the CHANGELOG upgrade note, and amend `docs/specs/multi-tenancy.md` so tenants are resolved as a route dependency after the admin principal.

**Spec:** [`docs/specs/bring-your-own-app.md`](../../../../docs/specs/bring-your-own-app.md) — section: Rollout; Migration & Backward Compatibility

## Files to Change

- `docs/guides/existing-app.md`
- `docs/guides/external-auth.md`
- `mkdocs.yml`
- `examples/byoa/main.py`
- `examples/byoa/models.py`
- `tests/unit/test_example_byoa.py`
- `tests/e2e/test_external_auth.py`
- `CHANGELOG.md`
- `docs/specs/multi-tenancy.md`

## Scenarios

```
Scenario: BYOA example boots
  Given examples/byoa with its own lifespan, /static and session cookie
  When  GET /admin/ with a valid bearer and GET /health are requested
  Then  both return 200
  And   the host session cookie is untouched

Scenario: e2e login round-trip
  Given the byoa example with login_url='/login'
  When  an anonymous browser opens /admin/
  Then  it lands on /login and returns to /admin/ after login

Scenario: e2e HTMX delete in bridge mode
  Given a token cookie from the handoff
  When  the user deletes a row
  Then  the row disappears

Scenario: guide under 20 lines
  Given the guide's minimal wiring snippet
  When  it is counted
  Then  it is fewer than 20 lines of code
```

## Acceptance Criteria

- [ ] BYOA example boots
- [ ] e2e login round-trip
- [ ] e2e HTMX delete in bridge mode
- [ ] guide under 20 lines
- [ ] `poe lint` and `poe test:unit` pass (and `poe test:e2e`)

## Blocked by

- `featauth-admin-scoped-session-cookie-via-adminsessionmiddlew` (st-v058-byoa-36)
- `fixuploads-serve-uploads-under-the-admin-prefix-behind-auth` (st-v058-byoa-37)
- `featauth-token-handoff-post-auth-session-and-bridge-logout` (st-v058-byoa-41)
- `featrealtime-hashable-user-keys-bridge-aware-sse-ws-and-webs` (st-v058-byoa-42)
- `featui-csrf-token-injection-and-bridge-aware-navbar` (st-v058-byoa-46)
- `featui-range-inputs-and-filter-errors-in-the-filter-bar` (st-v058-byoa-47)
- `teste2e-pk-type-and-timezone-fixture-app-uuid-natural-str-in` (st-v058-byoa-49)

## Parent

- Epic: `epic-v058-bring-your-own-app` (v0.5.8 — Bring Your Own App)
