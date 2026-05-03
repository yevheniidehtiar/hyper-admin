---
type: story
id: ice-task-6
title: "Task 6: Unit tests — inline edit + save views"
status: in-progress
priority: medium
labels:
  - test
  - unit
estimate: M
epic_ref:
  id: epic-inline-cell-editing
created_at: 2026-05-03
updated_at: 2026-05-03
---

## Description

Add `tests/unit/test_inline_cell_editing.py` covering:

- GET inline editor returns the editor fragment with the value pre-filled
- POST inline save with valid data persists and returns the cell fragment
- POST inline save with invalid data returns 422 + error fragment
- Field outside `list_editable` returns 403 on both GET and POST
- Routes are absent when `list_editable` is empty (negative regression)

## Acceptance Criteria

- [ ] All tests pass under `poe test:unit`
- [ ] Coverage ≥ 95 % on the new code
