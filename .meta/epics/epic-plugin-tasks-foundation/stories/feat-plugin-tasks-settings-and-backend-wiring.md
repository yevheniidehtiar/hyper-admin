---
type: story
id: pkT8vQFAKjBH
title: "feat(plugin-tasks): TasksSettings and backend selection/lifecycle wiring"
status: backlog
priority: high
assignee: null
labels:
  - agent-task
  - size:M
  - enhancement
  - planned
  - plugin
estimate: null
epic_ref:
  id: M437OCoW6YMr
github:
  issue_number: 742
  repo: yevheniidehtiar/hyper-admin
created_at: 2026-10-29T00:00:00Z
updated_at: 2026-10-29T00:00:00Z
---

## Context

Select and construct the backend from settings and open/close it with the admin lifespan.

**Spec:** [`docs/specs/plugin-tasks.md`](../../../../docs/specs/plugin-tasks.md)

## Scenarios

**Scenario: memory backend by default**
  Given no HYPERADMIN_TASKS_* env vars
  When  Admin starts
  Then  the plugin uses InMemoryTaskBackend

**Scenario: missing extra is explained**
  Given HYPERADMIN_TASKS_BACKEND=pgtask and pgtask is not installed
  When  Admin is constructed
  Then  TasksBackendError says to install hyperadmin-tasks[pgtask]

**Scenario: custom backend factory**
  Given HYPERADMIN_TASKS_BACKEND=myapp.tasks:make_backend
  When  Admin starts
  Then  the factory's backend is used

## Acceptance Criteria

- [ ] `TasksSettings` (fields per SDD) exposed as `TasksPlugin.settings_model`
- [ ] Backend `startup()`/`shutdown()` called from the admin lifespan via existing seams
- [ ] If no async lifecycle seam exists, open `feat(core): plugin async startup/shutdown seam` as a separate small PR first (SDD Open Question 1)

## Files Likely Affected

- `plugins/hyperadmin-tasks/src/hyperadmin_tasks/settings.py`
- `plugins/hyperadmin-tasks/src/hyperadmin_tasks/plugin.py`
- `plugins/hyperadmin-tasks/tests/test_settings.py`

## Dependencies

Depends on: `feat-plugin-tasks-inmemory-backend`

## Notes for Implementer

Lifecycle hooks in core are sync-only (`core/plugins.py`); check `core/lifecycle.py` / `Admin.lifespan` for an async seam before touching core.
