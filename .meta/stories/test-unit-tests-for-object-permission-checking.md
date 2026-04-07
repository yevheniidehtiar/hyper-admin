---
type: story
id: tnJ9lOQerEjS
title: "test: unit tests for object permission checking"
status: todo
priority: medium
assignee: null
labels:
  - agent-task
  - area:tests
  - area:auth
  - size:M
estimate: null
epic_ref: null
github:
  issue_number: 431
  repo: yevheniidehtiar/hyper-admin
  last_sync_hash: sha256:80003ced5861b39185fc2094e3434c3ca5260d30e9fe80b71da288b6adad5216
  synced_at: 2026-04-07T17:23:23.791Z
created_at: 2026-04-01T21:38:24Z
updated_at: 2026-04-01T21:38:24Z
---

## Context

Comprehensive unit test coverage for the entire object-level permission subsystem (OLP-2 through OLP-8). This consolidates test verification for the protocol, AdminOptions config, get_queryset hook, and view-level permission checks.

## Acceptance Criteria

- [ ] Test ObjectPermissionChecker protocol runtime-checkability
- [ ] Test default checker behavior (deny non-superusers)
- [ ] Test superuser bypass
- [ ] Test AdminOptions with/without object_permission_checker
- [ ] Test get_queryset hook in BaseAdapter (pass-through default)
- [ ] Test get_queryset hook with filtering override
- [ ] Test _check_object_permission helper (no checker, denied, allowed)
- [ ] Test detail_view, update_view, delete_action 403 on denied
- [ ] Near 99% coverage for new code

## Files Likely Affected
- `tests/unit/test_object_permissions.py` (new)

## Dependencies
Depends on: #430 (all OLP implementation complete)

## Notes for Implementer
- TDD mandate: tests should be written alongside or before implementation
- Each BDD scenario from OLP-2 through OLP-8 maps to at least one test
- Use mock objects for the permission checker in unit tests
- Follow existing test patterns in `tests/unit/test_auth_permissions.py`
