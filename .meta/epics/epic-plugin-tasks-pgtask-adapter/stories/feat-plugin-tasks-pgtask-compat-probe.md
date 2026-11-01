---
type: story
id: Wf0UhzZkRsdd
title: "feat(plugin-tasks): pgtask storage-protocol and column-drift startup probe"
status: backlog
priority: high
assignee: null
labels:
  - agent-task
  - size:S
  - enhancement
  - planned
  - plugin
estimate: null
epic_ref:
  id: krqQHG094vaz
github:
  issue_number: 749
  repo: yevheniidehtiar/hyper-admin
  synced_at: 2026-11-01T00:00:00Z
created_at: 2026-10-29T00:00:00Z
updated_at: 2026-10-29T00:00:00Z
---

## Context

Fail fast with actionable errors instead of broken pages when pgtask or its schema changes.

**Spec:** [`docs/specs/plugin-tasks.md`](../../../../docs/specs/plugin-tasks.md)

## Scenarios

**Scenario: protocol out of range**
  Given storage_protocol_range() excludes the supported version
  When  backend startup()
  Then  TasksBackendError names both versions and the supported pgtask range

**Scenario: schema not migrated**
  Given an empty database
  When  backend startup()
  Then  TasksBackendError tells the user to run `pgtask migrate`

## Acceptance Criteria

- [ ] Probe runs once in `startup()`
- [ ] Column check against `_pgtask_columns.py`
- [ ] Unit tests with a fake connection + one integration test

## Files Likely Affected

- `plugins/hyperadmin-tasks/src/hyperadmin_tasks/backends/pgtask.py`
- `plugins/hyperadmin-tasks/tests/pgtask/test_probe.py`

## Dependencies

Depends on: `feat-plugin-tasks-pgtask-read-side`

## Notes for Implementer

Follow CONSTITUTION.md; 100% patch coverage (`poe test:cov-diff`).
