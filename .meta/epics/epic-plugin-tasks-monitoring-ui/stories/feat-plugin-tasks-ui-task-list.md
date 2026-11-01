---
type: story
id: dxAiFEqdKldY
title: "feat(plugin-tasks): task list with queue/state/name filters, ID search and pagination"
status: backlog
priority: medium
assignee: null
labels:
  - agent-task
  - size:M
  - enhancement
  - planned
  - plugin
estimate: null
epic_ref:
  id: PWKqpZ5lCyfD
github:
  issue_number: 756
  repo: yevheniidehtiar/hyper-admin
  synced_at: 2026-11-01T00:00:00Z
created_at: 2026-10-29T00:00:00Z
updated_at: 2026-10-29T00:00:00Z
---

## Context

Browse and find tasks.

**Spec:** [`docs/specs/plugin-tasks.md`](../../../../docs/specs/plugin-tasks.md)

## Scenarios

**Scenario: filter by state**
  Given failed and succeeded tasks
  When  the user selects state=failed
  Then  only failed tasks are listed and the filter persists in the URL

**Scenario: search by id**
  Given a task with id T1
  When  the user searches "T1"
  Then  the row for T1 is shown

**Scenario: paginate**
  Given 120 tasks and page_size 50
  When  the user clicks next
  Then  rows 51–100 are shown and pagination info reads page 2

## Acceptance Criteria

- [ ] Labels on filter inputs (get_by_label)
- [ ] testids: tasks-list-table, tasks-list-row, tasks-state-filter, tasks-search-input, pagination-*
- [ ] Queue name on dashboard links to filtered list

## Files Likely Affected

- `plugins/hyperadmin-tasks/src/hyperadmin_tasks/routes.py`
- `plugins/hyperadmin-tasks/src/hyperadmin_tasks/templates/tasks/task_list.html`

## Dependencies

Depends on: `feat-plugin-tasks-ui-dashboard`

## Notes for Implementer

Follow CONSTITUTION.md; 100% patch coverage (`poe test:cov-diff`).
