---
type: story
id: kZh6EAS_Ij9W
title: "feat(core): add object_permission_checker to AdminOptions"
status: todo
priority: medium
assignee: null
labels:
  - backend
  - core
  - size:S
  - planned
estimate: null
epic_ref:
  id: mmZ2u_cMD2xN
github:
  issue_number: 477
  repo: yevheniidehtiar/hyper-admin
  last_sync_hash: sha256:0c74f43ed6ea6bdcef1bb1c039a76afa5592f603d0aeb6108869a2bcb8e26395
  synced_at: 2026-04-07T17:23:23.791Z
created_at: 2026-04-02T13:55:32Z
updated_at: 2026-04-02T13:55:32Z
---

## Summary

Add `object_permission_checker: ObjectPermissionChecker | None = None` field to `AdminOptions` so models can opt into object-level permission enforcement.

## Files to Change

- `src/hyperadmin/core/options.py` — add field to `AdminOptions`

## Scenarios

**Scenario: AdminOptions accepts object_permission_checker**
  Given a model registered with `options=AdminOptions(object_permission_checker=my_checker)`
  When  the model's options are inspected
  Then  `options.object_permission_checker` is `my_checker`

**Scenario: default is None (no object-level checks)**
  Given a model registered with default options
  When  the model's options are inspected
  Then  `options.object_permission_checker` is `None`

## Acceptance Criteria

- [ ] Field added to AdminOptions with default None
- [ ] Type annotation uses the protocol from #476

## Blocked by

- #476 (ObjectPermission protocol)

## Parent

- Epic: #473
