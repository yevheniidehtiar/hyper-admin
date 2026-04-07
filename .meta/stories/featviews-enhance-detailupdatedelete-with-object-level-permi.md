---
type: story
id: 26dtUfDV2IPf
title: "feat(views): enhance detail/update/delete with object-level permission checks"
status: todo
priority: medium
assignee: null
labels:
  - enhancement
  - agent-task
  - area:views
  - size:M
estimate: null
epic_ref: null
github:
  issue_number: 430
  repo: yevheniidehtiar/hyper-admin
  last_sync_hash: sha256:7b88fdaabc918fd4b08c3e9ddb089cc9f2519fafc803ca8f57b308761bf8ff0b
  synced_at: 2026-04-07T17:23:23.791Z
created_at: 2026-04-01T21:38:11Z
updated_at: 2026-04-01T21:38:11Z
---

## Context

With the `_check_object_permission()` helper in place (#429), the actual view handlers need to call it after fetching the object. Currently `detail_view`, `update_form_view`, `update_view`, and `delete_action` only check model-level permissions, not object-level.

## Scenarios

**Scenario: detail_view returns 403 when object permission denied**
  Given a user without object-level view permission for record #5
  When  GET `/admin/model/5` is requested
  Then  response is 403 "Permission denied"

**Scenario: update_form_view returns 403 when object permission denied**
  Given a user without object-level change permission for record #5
  When  GET `/admin/model/5/edit` is requested
  Then  response is 403 "Permission denied"

**Scenario: delete_action returns 403 when object permission denied**
  Given a user without object-level delete permission for record #5
  When  DELETE `/admin/model/5` is requested
  Then  response is 403 "Permission denied"

**Scenario: superuser bypasses object-level checks**
  Given a superuser requesting delete on record #5
  When  DELETE `/admin/model/5` is requested
  Then  the record is deleted successfully

## Acceptance Criteria

- [ ] `detail_view` calls `_check_object_permission(request, item, "view")` after `adapter.get()`
- [ ] `update_form_view` calls `_check_object_permission(request, item, "change")`
- [ ] `update_view` calls `_check_object_permission(request, item, "change")`
- [ ] `delete_action` calls `_check_object_permission(request, item, "delete")`
- [ ] Superuser bypass works
- [ ] Unit tests cover all 4 scenarios

## Files Likely Affected
- `src/hyperadmin/views/dynamic.py` (lines ~302, ~633, ~709, ~943)

## Dependencies
Depends on: #429 (_check_object_permission helper)

## Notes for Implementer
- Insert the check AFTER `adapter.get(pk=item_id)` and the 404 check
- Pattern: `await self._check_object_permission(request, item, "view")`
- Keep changes minimal — only add the check call, no logic changes
