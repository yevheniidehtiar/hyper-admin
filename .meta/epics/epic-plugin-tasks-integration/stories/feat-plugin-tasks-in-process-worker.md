---
type: story
id: QVP4dSaO_qEJ
title: "feat(plugin-tasks): optional in-process pgtask Worker bound to the admin lifespan"
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
  id: UuoF0wG2oyTQ
github:
  issue_number: 762
  repo: yevheniidehtiar/hyper-admin
  synced_at: 2026-11-01T00:00:00Z
created_at: 2026-10-29T00:00:00Z
updated_at: 2026-10-29T00:00:00Z
---

## Context

Dev and small deploys shouldn't need a separate worker process.

**Spec:** [`docs/specs/plugin-tasks.md`](../../../../docs/specs/plugin-tasks.md)

## Scenarios

**Scenario: worker starts and drains**
  Given run_worker=True and a registered TaskRegistry
  When  the app starts then shuts down
  Then  the worker processes tasks and shutdown waits up to the grace period

**Scenario: disabled by default**
  Given default settings
  When  the app starts
  Then  no worker is started

## Acceptance Criteria

- [ ] `TasksPlugin(registries=[...])` or settings dotted path to registries
- [ ] Graceful drain via `worker.shutdown()`
- [ ] Docs: separate worker process recipe

## Files Likely Affected

- `plugins/hyperadmin-tasks/src/hyperadmin_tasks/integration.py`
- `plugins/hyperadmin-tasks/src/hyperadmin_tasks/plugin.py`

## Dependencies

Depends on: `feat-plugin-tasks-pgtask-actions`

## Notes for Implementer

Follow CONSTITUTION.md; 100% patch coverage (`poe test:cov-diff`).
