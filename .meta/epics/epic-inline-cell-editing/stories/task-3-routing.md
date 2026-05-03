---
type: story
id: ice-task-3
title: "Task 3: Routing — register inline edit + save routes"
status: in-progress
priority: medium
labels:
  - task
  - routing
estimate: S
epic_ref:
  id: epic-inline-cell-editing
created_at: 2026-05-03
updated_at: 2026-05-03
---

## Description

When `options.can_edit` is true and `options.list_editable` is non-empty,
register two routes per model in `routing.create_admin_router`:

- `GET  /<model>/{item_id:int}/inline/{field:str}` → `<model>-inline-edit-form`
- `POST /<model>/{item_id:int}/inline/{field:str}` → `<model>-inline-save`

## Acceptance Criteria

- [ ] Routes are absent when `list_editable` is empty
- [ ] Routes are present when `list_editable` declares ≥1 field
- [ ] URL names follow `{model}-inline-edit-form` / `{model}-inline-save`
