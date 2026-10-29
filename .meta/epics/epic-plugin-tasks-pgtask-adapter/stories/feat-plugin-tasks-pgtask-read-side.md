---
type: story
id: zKKdr2aYpvga
title: "feat(plugin-tasks): PgTaskBackend read side over pgtask observer views"
status: backlog
priority: high
assignee: null
labels:
  - agent-task
  - size:L
  - enhancement
  - planned
  - plugin
estimate: null
epic_ref:
  id: krqQHG094vaz
github:
  issue_number: 750
  repo: yevheniidehtiar/hyper-admin
created_at: 2026-10-29T00:00:00Z
updated_at: 2026-10-29T00:00:00Z
---

## Context

Map observer views (`queue_overview`, `task_view`, `attempt_view`, `worker_view`, `schedule_view`) to the port's read models.

**Spec:** [`docs/specs/plugin-tasks.md`](../../../../docs/specs/plugin-tasks.md)

## Scenarios

**Scenario: queue overview**
  Given tasks in ready, running, failed and scheduled states on queue "reports"
  When  list_queues is called
  Then  QueueStats for "reports" has the matching counts

**Scenario: filter and paginate**
  Given 120 tasks on two queues
  When  list_tasks(TaskFilter(queue="reports", state=FAILED), page=2, per_page=50) is called
  Then  only failed reports tasks of page 2 are returned

**Scenario: missing task**
  Given no task with id X
  When  get_task("X")
  Then  None is returned

## Acceptance Criteria

- [ ] Single `_columns.py` mapping table; native states mapped to `TaskState`
- [ ] Separate observer-role pool (`observer_dsn`)
- [ ] Parameterised SQL only
- [ ] Read half of the contract suite green

## Files Likely Affected

- `plugins/hyperadmin-tasks/src/hyperadmin_tasks/backends/pgtask.py`
- `plugins/hyperadmin-tasks/src/hyperadmin_tasks/backends/_pgtask_columns.py`

## Dependencies

Depends on: `test-plugin-tasks-postgres-contract-harness`

## Notes for Implementer

View columns are NOT a pgtask stability contract (storage-boundary docs) — keep all knowledge in one module (CONSTITUTION §6).
