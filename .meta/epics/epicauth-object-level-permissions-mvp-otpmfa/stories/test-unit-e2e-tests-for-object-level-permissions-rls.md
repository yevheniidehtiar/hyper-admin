---
type: story
id: tRQuz_eZrFXy
title: "test: unit + e2e tests for object-level permissions & RLS"
status: todo
priority: medium
assignee: null
labels:
  - backend
  - size:M
  - planned
estimate: null
epic_ref:
  id: mmZ2u_cMD2xN
github:
  issue_number: 482
  repo: yevheniidehtiar/hyper-admin
  last_sync_hash: sha256:1943491a7c9ee639c82abcdf0db323b21a2764269e1c2c932f4d5b8bfdfbe840
  synced_at: 2026-04-07T17:23:23.791Z
created_at: 2026-04-02T14:52:33Z
updated_at: 2026-04-02T14:52:33Z
---

## Summary

Write unit tests for the ObjectPermission protocol, get_queryset hook, and view-layer enforcement. Write E2E tests verifying row-level security in the browser.

## Files to Change

- `tests/unit/test_object_permissions.py` — new
- `tests/unit/test_get_queryset.py` — new
- `tests/e2e/test_row_level_security.py` — new

## Scenarios

**Scenario: unit — ObjectPermissionChecker denies access returns False**
  Given a custom ObjectPermissionChecker that denies user "bob" for order#42
  When  `has_object_permission(bob, order42, "view")` is called
  Then  result is `False`

**Scenario: unit — get_queryset filters adapter list results**
  Given adapter with get_queryset returning `{"owner_id": 1}`
  When  `adapter.list()` is called
  Then  only records with owner_id=1 are returned

**Scenario: e2e — two users see only their own records**
  Given user "bob" owns 2 orders and user "alice" owns 3 orders
  When  "bob" logs in and visits /admin/order
  Then  list shows 2 rows
  When  "alice" logs in and visits /admin/order
  Then  list shows 3 rows

**Scenario: e2e — direct URL to another user's record returns 403**
  Given order#5 is owned by "alice"
  When  "bob" navigates to /admin/order/5
  Then  page shows 403 or redirects to list

## Acceptance Criteria

- [ ] Unit tests for ObjectPermissionChecker protocol
- [ ] Unit tests for get_queryset adapter filtering
- [ ] E2E test: multi-user list isolation
- [ ] E2E test: cross-user detail access denied
- [ ] All tests pass

## Blocked by

- #480 (view wiring for get_queryset)
- #481 (object-level permission in views)

## Parent

- Epic: #473
