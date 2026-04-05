---
type: story
id: SI0jh4BXXqj4
title: "feat(core): add object_permission_checker to AdminOptions"
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
  issue_number: 425
  repo: yevheniidehtiar/hyper-admin
  last_sync_hash: sha256:967819d41f1aa3ded1007825720cb9be993d41c9f1a2979f6da2f703aa561412
  synced_at: 2026-04-05T09:13:33.560Z
created_at: 2026-04-01T21:36:55Z
updated_at: 2026-04-01T21:36:55Z
---

## Context

With the `ObjectPermissionChecker` protocol defined (#424), we need a way for users to configure it per-model via `AdminOptions`. This adds an optional `object_permission_checker` field to `AdminOptions`.

## Scenarios

**Scenario: AdminOptions accepts object_permission_checker parameter**
  Given `AdminOptions(object_permission_checker=MyChecker())`
  When  the options object is inspected
  Then  `object_permission_checker` is the MyChecker instance

**Scenario: AdminOptions defaults to None when no checker provided**
  Given `AdminOptions()` with no `object_permission_checker`
  When  the options object is inspected
  Then  `object_permission_checker` is None

## Acceptance Criteria

- [ ] `object_permission_checker: Any | None = None` added to `AdminOptions`
- [ ] Existing tests pass (backward compatible)
- [ ] Unit test verifies both scenarios

## Files Likely Affected
- `src/hyperadmin/core/options.py`
- `tests/unit/test_core.py` or `tests/unit/test_object_permissions.py`

## Dependencies
Depends on: #424 (ObjectPermissionChecker protocol)

## Notes for Implementer
- `AdminOptions` is a Pydantic `BaseModel` — use `Any | None = None` typing
- Do NOT import the concrete checker type into `core/` — use `Any` to avoid circular deps
