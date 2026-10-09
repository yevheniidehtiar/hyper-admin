---
type: story
id: st-v058-byoa-25
title: "feat(auth): ExternalAuth, TokenCookie, CallablePermissionChecker and build_admin_dependency"
status: todo
priority: high
assignee: null
labels:
  - size:M
  - planned
  - area:auth
  - layer:logic
estimate: null
epic_ref:
  id: ep-v058-byoa-01
created_at: 2026-09-28T00:00:00Z
updated_at: 2026-09-28T00:00:00Z
---

## Summary

Add `auth/bridge.py`, which imports from `core/` only. It contains:
- the dataclasses `ExternalAuth` and `TokenCookie`;
- the default policies `can_access`, `display_name` and `user_key`;
- `CallablePermissionChecker`, which accepts sync or async callables;
- `build_admin_dependency`, which resolves the host dependency, raises the core auth exceptions, and sets `request.state.user`, `user_key` and `user_display`.

**Spec:** [`docs/specs/bring-your-own-app.md`](../../../../docs/specs/bring-your-own-app.md) — section: B.3, API

## Files to Change

- `src/hyperadmin/auth/bridge.py`
- `src/hyperadmin/auth/__init__.py`
- `tests/unit/test_auth_bridge.py`
- `tests/unit/test_auth_bridge_dependency.py`

## Scenarios

```
Scenario: callable checker
  Given a sync lambda has_permission
  When  CallablePermissionChecker.has_permission is awaited
  Then  the lambda's result is returned

Scenario: default can_access denies non-staff
  Given a host user without is_staff or is_superuser
  When  default_can_access runs
  Then  False is returned

Scenario: anonymous raises
  Given the host dependency returns None
  When  the admin dependency resolves
  Then  AdminAuthenticationRequired is raised

Scenario: can_access False raises
  Given can_access returns False
  When  the admin dependency resolves
  Then  AdminAccessDenied is raised

Scenario: state is populated
  Given a host user with a UUID id
  When  the admin dependency resolves
  Then  request.state.user_key is that UUID

Scenario: dependency overrides are honoured
  Given app.dependency_overrides replaces the host dependency
  When  an admin route is requested
  Then  the override's user is used
```

## Acceptance Criteria

- [ ] callable checker
- [ ] default can_access denies non-staff
- [ ] anonymous raises
- [ ] can_access False raises
- [ ] state is populated
- [ ] dependency overrides are honoured
- [ ] `poe lint` and `poe test:unit` pass

## Review amendments (2026-09-28)

- Add `ExternalAuth.allow_full_access: bool = False` and `TokenCookie.token_endpoint` (a token URL, or an `issue_token(username, password)` callable).
- `CallablePermissionChecker` plus the new `BridgeDefaultPermissionChecker` (superusers get everything, others `view_*` only).

## Blocked by

- `refactorauth-lazy-auth-package-exports-and-auth-metadata` (st-v058-byoa-17)
- `featcore-admin-auth-exceptions-and-pure-csrftokensigner` (st-v058-byoa-18)

## Parent

- Epic: `epic-v058-bring-your-own-app` (v0.5.8 — Bring Your Own App)
