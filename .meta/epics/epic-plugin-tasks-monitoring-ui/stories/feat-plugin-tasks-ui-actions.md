---
type: story
id: gPuinCXyopO1
title: "feat(plugin-tasks): retry / cancel / pause-resume actions with permission and capability gating"
status: done
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
  issue_number: 753
  repo: yevheniidehtiar/hyper-admin
  synced_at: 2026-11-01T00:00:00Z
created_at: 2026-10-29T00:00:00Z
updated_at: 2026-11-01T00:00:00Z
---

## Context

Safe operator actions from the UI.

**Spec:** [`docs/specs/plugin-tasks.md`](../../../../docs/specs/plugin-tasks.md)

## Scenarios

**Scenario: retry**
  Given a failed task and a manage_tasks user
  When  the user clicks Retry and confirms
  Then  retry_task is called with the username as actor and a success flash is shown

**Scenario: forbidden**
  Given a view_tasks-only user
  When  they POST /admin/tasks/t/T1/retry
  Then  403 is returned and nothing changes

**Scenario: race**
  Given the task was already retried
  When  the backend raises TasksBackendError
  Then  an error flash is shown, no 500

**Scenario: pause queue**
  Given queue reports running
  When  a manage_tasks user clicks Pause
  Then  the dashboard shows reports as paused

## Acceptance Criteria

- [ ] POST-only, CSRF-protected
- [ ] Confirmation dialog
- [ ] Buttons hidden without permission or capability
- [ ] testids: tasks-retry-btn, tasks-cancel-btn, tasks-queue-pause-btn, tasks-schedule-pause-btn

## Files Likely Affected

- `plugins/hyperadmin-tasks/src/hyperadmin_tasks/routes.py`
- `plugins/hyperadmin-tasks/src/hyperadmin_tasks/templates/tasks/_actions.html`

## Dependencies

Depends on: `feat-plugin-tasks-ui-task-detail`, `feat-plugin-tasks-ui-workers-and-schedules`

## Notes for Implementer

Follow CONSTITUTION.md; 100% patch coverage (`poe test:cov-diff`).
