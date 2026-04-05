---
type: story
id: Byq7TM_8nG4U
title: "feat(views): add object-level permission checks to detail/update/delete"
status: todo
priority: medium
assignee: null
labels:
  - backend
  - size:M
  - planned
estimate: null
epic_ref:
  id: ufsAiAiHcy3m
github:
  issue_number: 481
  repo: yevheniidehtiar/hyper-admin
  last_sync_hash: sha256:93debffa8341158ba800e2dcb674dafa156171ad0a9eb15a46e63d2bb0afe6e1
  synced_at: 2026-04-05T09:13:33.560Z
created_at: 2026-04-02T14:52:12Z
updated_at: 2026-04-02T14:52:12Z
---

## Summary

Enhance `detail_view`, `update_view`, and `delete_action` in `DynamicModelView` to call `object_permission_checker.has_object_permission()` after fetching the object, returning 403 if denied.

## Files to Change

- `src/hyperadmin/views/dynamic.py` — add `_check_object_permission()` helper, call from detail/update/delete

## Design

```python
async def _check_object_permission(
    self, request: Request, obj: Any, action: str
) -> None:
    checker = self.options.object_permission_checker
    if checker is None:
        return
    user = getattr(request.state, "user", None)
    if user is None:
        raise HTTPException(status_code=403)
    if not await checker.has_object_permission(user, obj, action):
        raise HTTPException(status_code=403, detail="Permission denied")
```

## Scenarios

**Scenario: staff user cannot view another user's record when object permission denies it**
  Given user "bob" has view_order model permission
  And   ObjectPermissionChecker denies "bob" access to order#42
  When  GET /admin/order/42
  Then  response is 403 Forbidden

**Scenario: superuser bypasses object-level permission**
  Given superuser "admin" exists
  And   ObjectPermissionChecker would deny order#42
  When  GET /admin/order/42
  Then  response is 200 OK (superuser bypass in checker implementation)

**Scenario: object permission check on update**
  Given ObjectPermissionChecker denies "bob" change access to order#42
  When  PUT /admin/order/42 with valid data
  Then  response is 403 Forbidden

**Scenario: object permission check on delete**
  Given ObjectPermissionChecker denies "bob" delete access to order#42
  When  DELETE /admin/order/42
  Then  response is 403 Forbidden

## Acceptance Criteria

- [ ] `_check_object_permission()` helper added to DynamicModelView
- [ ] Called in detail_view after fetch
- [ ] Called in update_view after fetch
- [ ] Called in delete_action after fetch
- [ ] Returns 403 when checker denies access
- [ ] No-op when checker is None (backward compatible)

## Blocked by

- #476 (ObjectPermission protocol)
- #477 (AdminOptions field)

## Parent

- Epic: #473
