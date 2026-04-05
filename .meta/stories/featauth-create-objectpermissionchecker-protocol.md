---
type: story
id: HEkrfidBiy55
title: "feat(auth): create ObjectPermissionChecker protocol"
status: todo
priority: medium
assignee: null
labels:
  - enhancement
  - agent-task
  - area:core
  - size:S
estimate: null
epic_ref: null
github:
  issue_number: 424
  repo: yevheniidehtiar/hyper-admin
  last_sync_hash: sha256:c94e7e6ef890fe58e946cce4f47f9217088ca349b688824ec60a1edcbc3b9c6f
  synced_at: 2026-04-05T09:13:33.560Z
created_at: 2026-04-01T21:36:45Z
updated_at: 2026-04-01T21:36:45Z
---

## Context

HyperAdmin currently only supports model-level permissions (`view_model`, `add_model`, etc.) via `PermissionChecker` in `core/auth.py`. There is no way to check permissions on individual objects (e.g., "can this user edit THIS specific record?"). This issue adds the `ObjectPermissionChecker` protocol to `core/auth.py` as the contract for object-level permission checking.

## Scenarios

**Scenario: ObjectPermissionChecker protocol is runtime-checkable**
  Given a class implementing `has_object_permission(user, obj, action) -> bool`
  When  `isinstance()` is called against `ObjectPermissionChecker`
  Then  it returns True

**Scenario: default implementation denies all non-superusers**
  Given a non-superuser requesting "change" on an object they don't own
  When  `has_object_permission()` is called with the default checker
  Then  it returns False

## Acceptance Criteria

- [ ] `ObjectPermissionChecker` protocol added to `src/hyperadmin/core/auth.py`
- [ ] Protocol is `@runtime_checkable` with method `has_object_permission(user, obj, action) -> bool`
- [ ] Unit tests cover both scenarios

## Files Likely Affected
- `src/hyperadmin/core/auth.py`
- `tests/unit/test_object_permissions.py` (new)

## Dependencies
Depends on: #423 (SDD approved)

## Notes for Implementer
- Follow existing protocol pattern in `core/auth.py` (see `PermissionChecker`)
- `core/` must not import from `views/` or `adapters/` (CONSTITUTION.md §2)
- Keep the protocol minimal: `has_object_permission(user: Any, obj: Any, action: str) -> bool`
