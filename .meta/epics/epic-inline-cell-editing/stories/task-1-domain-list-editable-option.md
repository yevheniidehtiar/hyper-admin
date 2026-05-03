---
type: story
id: ice-task-1
title: "Task 1: Add list_editable option to AdminOptions"
status: in-progress
priority: medium
labels:
  - task
  - core
estimate: S
epic_ref:
  id: epic-inline-cell-editing
created_at: 2026-05-03
updated_at: 2026-05-03
---

## Description

Add a `list_editable: list[str]` field to `AdminOptions` (default empty list)
and ensure `ModelAdmin` subclasses can declare it as a class attribute that
the registry merges into options at registration time.

## Acceptance Criteria

- [ ] `AdminOptions.list_editable` defaults to `[]`
- [ ] `ModelAdmin.list_editable` class attribute is read by the registry
      when constructing options
- [ ] Existing `AdminOptions` consumers continue to work unchanged
