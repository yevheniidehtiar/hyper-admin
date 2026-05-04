---
type: story
id: ypfwd4OQb8J3
title: "feat(views): wire get_queryset into list_view + detail_view"
status: done
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
  issue_number: 480
  repo: yevheniidehtiar/hyper-admin
  last_sync_hash: sha256:a3251d3bf726f5a81dfe05696a3e644ea86c9738a7032cf2f9d6b5460b9330ea
  synced_at: 2026-04-07T17:23:23.791Z
created_at: 2026-04-02T14:03:57Z
updated_at: 2026-04-02T14:03:57Z
---

## Summary

Wire the `get_queryset()` hook into `DynamicModelView` so that `list_view` and `detail_view` (and update/delete) respect per-request query filtering.

## Files to Change

- `src/hyperadmin/views/dynamic.py` — call `get_queryset(request)` and pass filters to adapter

## Design

In `list_view()`, before calling `adapter.list()`:
1. Call `model_admin.get_queryset(request)` to get additional filters
2. Merge into `filters_to_apply`
3. Pass to `adapter.list()`

In `detail_view()` / `update_view()` / `delete_action()`:
1. After `adapter.get(pk)`, verify the object matches `get_queryset()` filters
2. Return 404 if object is filtered out

## Scenarios

**Scenario: list_view only shows records matching get_queryset filter**
  Given user "bob" owns orders [1, 2] and user "alice" owns orders [3, 4]
  And   ModelAdmin.get_queryset returns `{"owner_id": request.state.user.id}`
  When  "bob" visits GET /admin/order
  Then  only orders [1, 2] are displayed

**Scenario: detail_view returns 404 for filtered-out record**
  Given order#3 is owned by "alice"
  And   ModelAdmin.get_queryset returns `{"owner_id": request.state.user.id}`
  When  "bob" visits GET /admin/order/3
  Then  response is 404 Not Found

**Scenario: pagination count reflects filtered queryset**
  Given 100 total orders, 25 owned by "bob"
  When  "bob" visits GET /admin/order
  Then  pagination shows "25 total"

**Scenario: superuser sees all records (default get_queryset)**
  Given superuser with default ModelAdmin (no get_queryset override)
  When  superuser visits GET /admin/order
  Then  all 100 orders are displayed

## Acceptance Criteria

- [ ] list_view calls get_queryset and merges filters
- [ ] detail_view validates object against get_queryset filters
- [ ] update_view validates object against get_queryset filters
- [ ] delete_action validates object against get_queryset filters
- [ ] Pagination count uses filtered total
- [ ] Backward compatible (no get_queryset override = no filtering)

## Blocked by

- #478 (adapter get_queryset hook)
- #479 (ModelAdmin get_queryset)

## Parent

- Epic: #473
