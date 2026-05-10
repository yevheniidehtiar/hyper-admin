---
type: story
id: st-v055-ac-02
title: "feat(views): add create_popup_view returning HX-Trigger payload"
status: todo
priority: high
assignee: null
labels:
  - size:M
  - planned
  - backend
  - upstream-readiness
  - H6
estimate: null
epic_ref:
  id: ep-v055-ac-01
created_at: 2026-05-10T00:00:00Z
updated_at: 2026-05-10T00:00:00Z
---

## Summary

Add `create_popup_view` to `DynamicModelView`. On a successful POST, return an
empty 200 with `HX-Trigger: hyperadminPopupCreated` carrying
`{"target": "<field>", "id": <pk>, "label": "<display>"}`. On validation
failure, re-render the popup form fragment with field errors.

**Spec:** [`docs/specs/htmx-autocomplete.md`](../../../../docs/specs/htmx-autocomplete.md)

## Files to Change

- **Modified:** `src/hyperadmin/views/dynamic.py` — `create_popup_view`, route registration
- **New:** `src/hyperadmin/templates/widgets/popup_form.html`
- **Modified:** `tests/unit/test_dynamic_views.py` — popup-view tests

## Scenarios

```
Scenario: popup create with valid data returns HX-Trigger payload
  Given Supplier is registered and the user is authenticated as admin
  When  POST /admin/suppliers/create-popup with valid form data + target=supplier_id
  Then  response status is 200 and body is empty
  And   HX-Trigger header contains "hyperadminPopupCreated" with id=<new pk> and target="supplier_id"

Scenario: popup create with permission denied returns 403
  Given the user lacks "add" permission on Supplier
  When  POST /admin/suppliers/create-popup with valid form data
  Then  response status is 403 with the standard error template fragment
```

## Acceptance Criteria

- [ ] `create_popup_view` registered at `POST /{model}/create-popup`
- [ ] Permission check via existing `_check_permission("add")`
- [ ] Success: 200 + empty body + `HX-Trigger` JSON payload
- [ ] Validation failure: 200 + re-rendered fragment with errors
- [ ] Permission failure: 403 + standard error fragment
- [ ] Unit tests cover both scenarios above
- [ ] `poe lint` passes

## Blocked by

- `featcore-extend-adminoptions-with-relation-config`

## Parent

- Epic: `epic-v055-htmx-autocomplete`
