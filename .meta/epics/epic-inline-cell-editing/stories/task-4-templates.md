---
type: story
id: ice-task-4
title: "Task 4: Templates — inline cell, editor, error fragment"
status: done
priority: medium
labels:
  - task
  - templates
estimate: 5
epic_ref:
  id: epic-inline-cell-editing
created_at: 2026-05-03
updated_at: 2026-05-03
---

## Description

Add three template fragments and integrate them into the existing
`components/table.html`:

- `components/inline_cell.html` — static cell + edit affordance (button)
- `components/inline_editor.html` — inline form fragment (input + Save/Cancel)
- `components/inline_cell_error.html` — error fragment (422 fallback)

Update `components/table.html` to render `inline_cell.html` when the field is
editable.

## Acceptance Criteria

- [ ] `data-testid="cell-edit-{field}"` on the edit button
- [ ] `data-testid="cell-editor-{field}"` on the inline form
- [ ] `data-testid="cell-save-{field}"` and `cell-cancel-{field}` on buttons
- [ ] `aria-label` on the editor input names the field
- [ ] HTMX wiring: `hx-get`/`hx-post` target the cell `<td>` via `outerHTML`
- [ ] Page-level `aria-live="polite"` region on the list view announces saves
