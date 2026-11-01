---
type: story
id: IlybHY4iM9uJ
title: "feat(plugin-tasks): tasks dashboard with per-queue stats and auto-refresh"
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
  issue_number: 754
  repo: yevheniidehtiar/hyper-admin
  synced_at: 2026-11-01T00:00:00Z
created_at: 2026-10-29T00:00:00Z
updated_at: 2026-11-01T00:00:00Z
---

## Context

Landing page at /admin/tasks.

**Spec:** [`docs/specs/plugin-tasks.md`](../../../../docs/specs/plugin-tasks.md)

## Scenarios

**Scenario: dashboard lists queues**
  Given queues reports and emails with tasks
  When  the user opens /admin/tasks
  Then  a row per queue shows ready, running, scheduled, failed counts and oldest-ready age

**Scenario: auto refresh**
  Given refresh_seconds=5
  When  5 seconds pass
  Then  the stats partial is re-fetched via HTMX without a full reload

**Scenario: backend down**
  Given the backend raises on list_queues
  When  the user opens /admin/tasks
  Then  an error banner (tasks-backend-error) is shown instead of a 500

## Acceptance Criteria

- [ ] Template `tasks/dashboard.html` + `_queue_stats.html` partial
- [ ] testids: tasks-queue-table, tasks-queue-row, tasks-backend-error
- [ ] Route tests with InMemoryTaskBackend

## Files Likely Affected

- `plugins/hyperadmin-tasks/src/hyperadmin_tasks/routes.py`
- `plugins/hyperadmin-tasks/src/hyperadmin_tasks/templates/tasks/dashboard.html`
- `plugins/hyperadmin-tasks/src/hyperadmin_tasks/templates/tasks/_queue_stats.html`

## Dependencies

Depends on: `feat-plugin-tasks-settings-and-backend-wiring`

## Notes for Implementer

Reuse core layout and table components; no new JS framework.
