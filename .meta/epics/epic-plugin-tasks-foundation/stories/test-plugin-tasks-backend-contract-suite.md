---
type: story
id: PocktBXkhK5j
title: "test(plugin-tasks): reusable TaskBackend contract test suite"
status: backlog
priority: high
assignee: null
labels:
  - agent-task
  - size:M
  - planned
  - plugin
estimate: null
epic_ref:
  id: M437OCoW6YMr
github:
  issue_number: 745
  repo: yevheniidehtiar/hyper-admin
created_at: 2026-10-29T00:00:00Z
updated_at: 2026-10-29T00:00:00Z
---

## Context

TDD: write the behavioural contract before the in-memory and pgtask adapters. Shipped as an importable module so third-party adapters can reuse it.

**Spec:** [`docs/specs/plugin-tasks.md`](../../../../docs/specs/plugin-tasks.md)

## Scenarios

**Scenario: adapter authors reuse the suite**
  Given a test module subclasses TaskBackendContract with a backend fixture
  When  pytest runs
  Then  all contract tests are collected against that backend

**Scenario: retry contract**
  Given a failed task seeded via the fixture's seeding hook
  When  retry_task is called with an actor
  Then  the task's state becomes pending and its attempt budget is reset per backend semantics

## Acceptance Criteria

- [ ] `hyperadmin_tasks.contract.TaskBackendContract` covering listing, filtering, pagination, get_task (incl. missing id), each action, capability gating
- [ ] Seeding hook protocol so each backend can create fixtures natively
- [ ] Marked xfail-free: suite fails until the in-memory backend lands (run in that PR)

## Files Likely Affected

- `plugins/hyperadmin-tasks/src/hyperadmin_tasks/contract.py`
- `plugins/hyperadmin-tasks/tests/conftest.py`

## Dependencies

Depends on: `feat-plugin-tasks-taskbackend-port-and-read-models`

## Notes for Implementer

Can be stacked as the first commit of the in-memory backend PR (feedback: stack tightly-coupled stories).
