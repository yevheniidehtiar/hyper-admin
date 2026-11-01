---
type: story
id: 7HgdThwIY64j
title: "feat(plugin-tasks): TaskBackend port, read models and capabilities"
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
  id: M437OCoW6YMr
github:
  issue_number: 743
  repo: yevheniidehtiar/hyper-admin
created_at: 2026-10-29T00:00:00Z
updated_at: 2026-11-01T00:00:00Z
---

## Context

Define the backend-agnostic contract every adapter and the UI depend on (bottom layer).

**Spec:** [`docs/specs/plugin-tasks.md`](../../../../docs/specs/plugin-tasks.md)

## Scenarios

**Scenario: read models are immutable**
  Given a TaskRecord instance
  When  a field is assigned
  Then  a ValidationError/FrozenInstanceError is raised

**Scenario: unsupported action is rejected**
  Given a backend whose capabilities exclude CANCEL
  When  cancel_task is called
  Then  TasksBackendError is raised naming the capability

## Acceptance Criteria

- [ ] `TaskBackend` Protocol (no `Protocol` suffix, CONSTITUTION §3) with the methods from the SDD
- [ ] Frozen pydantic models: QueueStats, TaskRecord, AttemptRecord, WorkerRecord, ScheduleRecord, TaskFilter, Page[T]
- [ ] `TaskState` and `Capability` StrEnums; `TasksBackendError`
- [ ] 100% coverage of new lines

## Files Likely Affected

- `plugins/hyperadmin-tasks/src/hyperadmin_tasks/backend.py`
- `plugins/hyperadmin-tasks/tests/test_backend_models.py`

## Dependencies

Depends on: `chore-scaffold-plugins-hyperadmin-tasks-package`

## Notes for Implementer

Port lives in the plugin, not core — core stays task-agnostic.
