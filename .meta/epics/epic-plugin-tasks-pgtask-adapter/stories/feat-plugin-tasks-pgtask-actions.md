---
type: story
id: HumNPED9rjfA
title: "feat(plugin-tasks): PgTaskBackend actions (retry, cancel, queue & schedule pause) with audited actor"
status: done
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
  id: krqQHG094vaz
github:
  issue_number: 748
  repo: yevheniidehtiar/hyper-admin
  synced_at: 2026-11-01T00:00:00Z
created_at: 2026-10-29T00:00:00Z
updated_at: 2026-11-01T00:00:00Z
---

## Context

Admin actions through pgtask's administrator role so its audit table records who did what.

**Spec:** [`docs/specs/plugin-tasks.md`](../../../../docs/specs/plugin-tasks.md)

## Scenarios

**Scenario: retry failed task**
  Given a failed task
  When  retry_task(id, actor="alice")
  Then  the task is pending and administrator_audit_view has an entry with actor alice

**Scenario: pause queue**
  Given queue "reports" with ready tasks
  When  set_queue_paused("reports", True, actor="alice")
  Then  workers stop claiming and list_queues reports paused

## Acceptance Criteria

- [ ] Actions use the administrator DSN only
- [ ] Capabilities reflect what the installed pgtask version supports
- [ ] Action half of contract suite green

## Files Likely Affected

- `plugins/hyperadmin-tasks/src/hyperadmin_tasks/backends/pgtask.py`

## Dependencies

Depends on: `feat-plugin-tasks-pgtask-read-side`

## Notes for Implementer

SDD Open Question 2: if admin SQL functions are not public, use the Python client with the actor header.
