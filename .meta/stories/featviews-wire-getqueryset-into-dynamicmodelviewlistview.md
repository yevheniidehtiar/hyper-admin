---
type: story
id: _jrhZw9RSd6K
title: "feat(views): wire get_queryset into DynamicModelView.list_view"
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
  issue_number: 428
  repo: yevheniidehtiar/hyper-admin
  last_sync_hash: sha256:3c7876d5ab13b07290867ec38758e43433a8ad6475fd112afc0febf04c763a2b
  synced_at: 2026-04-07T17:23:23.791Z
created_at: 2026-04-01T21:37:44Z
updated_at: 2026-04-01T21:37:44Z
---

## Context

The `get_queryset()` hook exists in the adapter (#426) and ModelAdmin (#427), but the view layer does not pass `request` to the adapter. This issue wires the request object through `DynamicModelView.list_view()` into the adapter's `list()` method, enabling row-level filtering.

## Scenarios

**Scenario: list_view passes request to adapter for queryset filtering**
  Given a model with `get_queryset` filtering by `owner_id`
  And   user A owns 3 records, user B owns 2 records
  When  user A views the list
  Then  only 3 records are shown

**Scenario: list_view without get_queryset override shows all records**
  Given a model with no `get_queryset` override
  When  any user views the list
  Then  all records are shown (backward compatible)

**Scenario: get_queryset applies to search and filter results too**
  Given a model with `get_queryset` filtering by `owner_id`
  And   user A searches for "test"
  When  the search executes
  Then  only user A's records matching "test" are returned

## Acceptance Criteria

- [ ] `DynamicModelView.list_view()` passes `request` to `adapter.list()`
- [ ] `DynamicModelView.detail_view()` passes `request` to adapter for scoped `get()`
- [ ] `admin_instance` is accessible to the adapter for `get_queryset()` delegation
- [ ] Search and filter results respect `get_queryset` scoping
- [ ] All existing E2E and unit tests pass (backward compatible)
- [ ] Unit tests cover all 3 scenarios

## Files Likely Affected
- `src/hyperadmin/views/dynamic.py` — pass `request` in `list_view()`, `detail_view()`
- `src/hyperadmin/routing.py` — ensure `admin_instance` is available to adapter

## Dependencies
Depends on: #426 (get_queryset in BaseAdapter), #427 (get_queryset in ModelAdmin)

## Notes for Implementer
- `DynamicModelView` already has `self._admin_instance` — use it to delegate `get_queryset`
- The adapter's `list()` currently takes `(page, page_size, search, filters, order_by, search_fields)` — add `request=None`
- `dynamic.py` is 989 LOC — keep changes minimal, watch the 300 LOC review trigger
