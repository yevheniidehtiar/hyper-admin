---
type: story
id: ejgWNwOBpqzf
title: "feat(views): add _check_object_permission helper to DynamicModelView"
status: todo
priority: medium
assignee: null
labels:
  - enhancement
  - agent-task
  - area:views
  - size:S
estimate: null
epic_ref: null
github:
  issue_number: 429
  repo: yevheniidehtiar/hyper-admin
  last_sync_hash: sha256:7fbf3cf10fe7f93917c4e6b6581987fb4b8e112a42f1b936ec08cafd6f0375a8
  synced_at: 2026-04-05T09:13:33.560Z
created_at: 2026-04-01T21:37:56Z
updated_at: 2026-04-01T21:37:56Z
---

## Context

`DynamicModelView._check_permission()` only checks model-level permissions. After fetching an object, we need a separate check for object-level permissions using the `ObjectPermissionChecker` from AdminOptions (#425). This adds a `_check_object_permission()` helper method.

## Scenarios

**Scenario: _check_object_permission passes when no checker configured**
  Given `AdminOptions` with `object_permission_checker = None`
  When  `_check_object_permission(request, obj, "change")` is called
  Then  no exception is raised

**Scenario: _check_object_permission raises 403 when checker denies**
  Given `AdminOptions` with an `ObjectPermissionChecker` that denies user for this object
  When  `_check_object_permission(request, obj, "change")` is called
  Then  `HTTPException` 403 is raised with "Permission denied"

## Acceptance Criteria

- [ ] `_check_object_permission(request, obj, action)` method added to `DynamicModelView`
- [ ] Method reads `object_permission_checker` from `self.options`
- [ ] Method is a no-op when checker is None (backward compatible)
- [ ] Superuser bypass supported
- [ ] Unit tests cover both scenarios

## Files Likely Affected
- `src/hyperadmin/views/dynamic.py`
- `tests/unit/test_object_permissions.py`

## Dependencies
Depends on: #424 (ObjectPermissionChecker protocol), #425 (AdminOptions config)

## Notes for Implementer
- Follow the pattern of existing `_check_permission()` at line 119 of `dynamic.py`
- The checker is async: `await checker.has_object_permission(user, obj, action)`
- Superuser check: `if user.is_superuser: return` (same as model-level check)
