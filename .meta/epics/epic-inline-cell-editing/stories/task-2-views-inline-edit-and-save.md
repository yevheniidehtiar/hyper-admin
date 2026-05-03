---
type: story
id: ice-task-2
title: "Task 2: Inline edit form + save views"
status: in-progress
priority: medium
labels:
  - task
  - views
estimate: M
epic_ref:
  id: epic-inline-cell-editing
created_at: 2026-05-03
updated_at: 2026-05-03
---

## Description

Add `inline_edit_form_view(request, item_id, field)` and
`inline_save_view(request, item_id, field)` to `DynamicModelView`.

The save view validates a single-field payload via `PydanticForm.validate`
on a single-key dict, calls `adapter.update(pk, {field: value})`, and renders
the `inline_cell.html` partial on success or `inline_cell_error.html` (status
422) on validation failure.

Both endpoints reject fields not in `options.list_editable` with HTTP 403.

## Acceptance Criteria

- [ ] GET endpoint returns the editor fragment with the current value pre-filled
- [ ] POST endpoint validates and persists the field via the adapter
- [ ] Field outside `list_editable` returns 403
- [ ] Validation failure returns 422 + error fragment
- [ ] No business logic in the view beyond field gating + delegation
