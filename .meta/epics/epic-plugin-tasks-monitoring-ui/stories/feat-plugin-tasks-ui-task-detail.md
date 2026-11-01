---
type: story
id: 3vIxqk0PlGpu
title: "feat(plugin-tasks): task detail with payload, result/error and attempts timeline"
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
  issue_number: 755
  repo: yevheniidehtiar/hyper-admin
  synced_at: 2026-11-01T00:00:00Z
created_at: 2026-10-29T00:00:00Z
updated_at: 2026-10-29T00:00:00Z
---

## Context

Inspect a single task.

**Spec:** [`docs/specs/plugin-tasks.md`](../../../../docs/specs/plugin-tasks.md)

## Scenarios

**Scenario: failed task detail**
  Given a task failed after 3 attempts
  When  the user opens it
  Then  the error, 3 attempts with worker ids and timestamps, and payload are shown

**Scenario: large payload**
  Given a 1 MiB payload
  When  the user opens the task
  Then  a truncated preview (64 KiB cap) with an expand control is shown

**Scenario: deleted by retention**
  Given a task id that no longer exists
  When  the user opens it
  Then  a 404 page links back to the list

## Acceptance Criteria

- [ ] JSON rendered escaped (no `|safe`)
- [ ] testids: tasks-detail, tasks-attempt-row, tasks-payload, tasks-error

## Files Likely Affected

- `plugins/hyperadmin-tasks/src/hyperadmin_tasks/routes.py`
- `plugins/hyperadmin-tasks/src/hyperadmin_tasks/templates/tasks/task_detail.html`

## Dependencies

Depends on: `feat-plugin-tasks-ui-task-list`

## Notes for Implementer

XSS: payloads are untrusted user data.
