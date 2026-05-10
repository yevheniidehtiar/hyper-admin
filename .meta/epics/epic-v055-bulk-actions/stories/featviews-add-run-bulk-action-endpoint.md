---
type: story
id: st-v055-bulk-02
title: "feat(views): add run_bulk_action endpoint with per-row outcome"
status: todo
priority: high
assignee: null
labels:
  - size:M
  - planned
  - backend
  - upstream-readiness
  - H3
estimate: null
epic_ref:
  id: ep-v055-bulk-01
created_at: 2026-05-10T00:00:00Z
updated_at: 2026-05-10T00:00:00Z
---

## Summary

Wire the bulk endpoint on `DynamicModelView`. Parses `ids[]` from the POST body,
enforces `requires_selection`, dispatches to the param-form renderer when a
form is configured, otherwise runs the handler per row and renders the result
page. Each row is wrapped in object-permission re-check + exception capture.

**Spec:** [`docs/specs/bulk-actions.md`](../../../../docs/specs/bulk-actions.md)

## Files to Change

- **Modified:** `src/hyperadmin/views/dynamic.py` — add `run_bulk_action`, `confirm_bulk_action`, `_render_bulk_result`, register routes
- **New:** `src/hyperadmin/core/bulk_results.py` — `BulkRowResult` NamedTuple
- **Modified:** `tests/unit/test_dynamic_views.py` — bulk endpoint coverage

## Scenarios

```
Scenario: empty ids with requires_selection returns 400
  When  POST /admin/orders/actions/archive/bulk with ids=[]
  Then  response status is 400 and body contains "Selection required"

Scenario: bulk handler runs per-row, captures HTTPException(403) as forbidden
  Given handler raises HTTPException(403) for id=2
  When  POST .../bulk with ids=[1,2,3]
  Then  result rows are ok / forbidden / ok in order

Scenario: bulk handler runs per-row, captures generic exception as failed
  Given handler raises RuntimeError("boom") for id=2
  When  POST .../bulk with ids=[1,2,3]
  Then  result rows are ok / failed / ok in order
  And   the "failed" row carries detail "boom"

Scenario: object-permission denial surfaces per row
  Given an ObjectPermissionChecker that denies "archive" on id=2
  When  POST .../bulk with ids=[1,2,3]
  Then  result rows are ok / forbidden / ok
  And   the handler is invoked only for ids 1 and 3
```

## Acceptance Criteria

- [ ] `BulkRowResult` NamedTuple defined in `core/bulk_results.py`
- [ ] `run_bulk_action` and `confirm_bulk_action` registered on `DynamicModelView`
- [ ] Routes mounted at `/{model}/actions/{name}/bulk` and `/.../bulk/confirm`
- [ ] `requires_selection` enforced with 400 response
- [ ] Object-level permission re-check per row
- [ ] HTTPException → "forbidden"; other exceptions → "failed" with `str(exc)`
- [ ] HTMX request returns fragment; non-HTMX returns full page
- [ ] Unit tests for all four scenarios above
- [ ] `poe lint` and `poe test:unit` pass

## Blocked by

- `featcore-extend-actiondef-with-bulk-and-form`

## Parent

- Epic: `epic-v055-bulk-actions`
