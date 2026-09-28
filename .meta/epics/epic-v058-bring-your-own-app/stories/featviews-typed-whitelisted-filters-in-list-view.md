---
type: story
id: st-v058-byoa-44
title: "feat(views): typed, whitelisted filters in list_view"
status: todo
priority: high
assignee: null
labels:
  - size:S
  - planned
  - area:views
  - layer:views
  - security
estimate: null
epic_ref:
  id: ep-v058-byoa-01
created_at: 2026-09-28T00:00:00Z
updated_at: 2026-09-28T00:00:00Z
---

## Summary

`list_view` uses `parse_filter_params`, restricted to `list_filter`, and passes `FilterCondition`s to the adapter. Invalid values produce `filter_errors` and the page still returns 200.

**Spec:** [`docs/specs/bring-your-own-app.md`](../../../../docs/specs/bring-your-own-app.md) — section: D.3

## Files to Change

- `src/hyperadmin/views/dynamic.py`
- `tests/unit/test_list_view_typed_filters.py`

## Scenarios

```
Scenario: integer filter coerced
  Given Order list_filter ['quantity']
  When  /admin/order?filter_quantity=3 is requested
  Then  only quantity 3 rows are listed

Scenario: non-whitelisted ignored
  Given User list_filter ['is_active']
  When  /admin/user?filter_password_hash=abc is requested
  Then  all users are listed

Scenario: invalid UUID keeps page working
  Given Order list_filter ['customer_id'] of type UUID
  When  filter_customer_id=not-a-uuid is requested
  Then  the status is 200
  And   filter_errors contains customer_id
```

## Acceptance Criteria

- [ ] integer filter coerced
- [ ] non-whitelisted ignored
- [ ] invalid UUID keeps page working
- [ ] `poe lint` and `poe test:unit` pass

## Blocked by

- `featadapters-apply-filtercondition-lists-with-dict-back-comp` (st-v058-byoa-24)
- `fixviews-list-view-logs-and-surfaces-db-errors-instead-of-sw` (st-v058-byoa-43)

## Parent

- Epic: `epic-v058-bring-your-own-app` (v0.5.8 — Bring Your Own App)
