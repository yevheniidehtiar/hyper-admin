---
type: story
id: W9rSTTBbBQWf
title: "feat(plugin-tasks): workers and schedules pages"
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
  issue_number: 757
  repo: yevheniidehtiar/hyper-admin
created_at: 2026-10-29T00:00:00Z
updated_at: 2026-10-29T00:00:00Z
---

## Context

Who is processing work, and what runs on cron.

**Spec:** [`docs/specs/plugin-tasks.md`](../../../../docs/specs/plugin-tasks.md)

## Scenarios

**Scenario: workers listed**
  Given two live workers and one stale
  When  the user opens /admin/tasks/workers
  Then  three rows are shown and the stale one is marked unhealthy

**Scenario: schedules listed**
  Given a cron schedule "0 0 * * * *"
  When  the user opens /admin/tasks/schedules
  Then  it shows cron, next run (UTC) and misfire policy

**Scenario: capability hidden**
  Given a backend without SCHEDULES
  When  the user views the nav
  Then  no Schedules link is rendered

## Acceptance Criteria

- [ ] testids: tasks-worker-row, tasks-schedule-row
- [ ] Nav entries respect capabilities

## Files Likely Affected

- `plugins/hyperadmin-tasks/src/hyperadmin_tasks/routes.py`
- `plugins/hyperadmin-tasks/src/hyperadmin_tasks/templates/tasks/workers.html`
- `plugins/hyperadmin-tasks/src/hyperadmin_tasks/templates/tasks/schedules.html`
- `plugins/hyperadmin-tasks/src/hyperadmin_tasks/plugin.py`

## Dependencies

Depends on: `feat-plugin-tasks-ui-dashboard`

## Notes for Implementer

Follow CONSTITUTION.md; 100% patch coverage (`poe test:cov-diff`).
