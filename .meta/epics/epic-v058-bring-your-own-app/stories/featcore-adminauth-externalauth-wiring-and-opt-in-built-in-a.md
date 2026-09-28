---
type: story
id: st-v058-byoa-40
title: "feat(core): Admin(auth=ExternalAuth) wiring and opt-in built-in auth models"
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

Wire `Admin(auth=...)` with protected and public routers, mapping the permission checker as described in the SDD, and make it mutually exclusive with `auth_backend`, `otp_service` and `oauth_backend`. Add no session or auth middleware in bridge mode. Add `settings.register_auth_models` (auto), and log a startup `WARNING` when `has_permission` is omitted.

**Spec:** [`docs/specs/bring-your-own-app.md`](../../../../docs/specs/bring-your-own-app.md) — section: B.3

## Files to Change

- `src/hyperadmin/core/app.py`
- `src/hyperadmin/core/settings.py`
- `tests/unit/test_admin_external_auth.py`
- `tests/unit/test_auth_auto_register.py`

## Scenarios

```
Scenario: staff user admitted
  Given Admin(auth=ExternalAuth(get_user=dep, can_access=is_admin))
  When  GET /admin/ is sent with a valid bearer
  Then  the response is 200
  And   the navbar shows the host display name

Scenario: has_permission gates
  Given has_permission(user, 'delete_order') returns False
  When  DELETE /admin/order/5 is sent with a valid token
  Then  the response is 403

Scenario: object checker gets host user
  Given an owner_only object checker on Order
  When  GET /admin/order/42 is requested
  Then  the checker was called with the host User instance

Scenario: mutual exclusion
  Given both auth= and auth_backend=
  When  Admin(...) is constructed
  Then  ValueError names both parameters

Scenario: no hyperadmin tables in bridge mode
  Given a fresh interpreter importing only hyperadmin and the bridge
  When  the admin mounts and starts
  Then  SQLModel.metadata has no hyperadmin_users table

Scenario: built-in models kept for auth_backend
  Given Admin(auth_backend=SessionAuthBackend(engine))
  When  it mounts
  Then  User, Group and Permission admins are registered
```

## Acceptance Criteria

- [ ] staff user admitted
- [ ] has_permission gates
- [ ] object checker gets host user
- [ ] mutual exclusion
- [ ] no hyperadmin tables in bridge mode
- [ ] built-in models kept for auth_backend
- [ ] `poe lint` and `poe test:unit` pass

## Review amendments (2026-09-28)

- Fail-safe default permissions (Owner decision 3): without `has_permission`, superusers get full access and others get view-only. `ExternalAuth(allow_full_access=True)` opts into full access and logs a `WARNING`. By default, non-superusers never get change or delete on the host user model (the class of the object `get_user` returns).
- `ModelPermissionChecker` combined with `auth=` raises `ValueError` unless `register_auth_models=True`.
- Add scenarios: a staff user is view-only; a staff user cannot set their own `is_superuser`; and the rejected-checker combination.

## Blocked by

- `featauth-externalauth-tokencookie-callablepermissionchecker` (st-v058-byoa-25)
- `featviews-csrfguard-signed-double-submit-wired-into-hyperadm` (st-v058-byoa-39)

## Parent

- Epic: `epic-v058-bring-your-own-app` (v0.5.8 — Bring Your Own App)
