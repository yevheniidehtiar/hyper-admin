---
type: story
id: s_BQCfl6tP7v
title: "feat(plugin-tasks): InMemoryTaskBackend for tests, demos and UI development"
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
  issue_number: 741
  repo: yevheniidehtiar/hyper-admin
created_at: 2026-10-29T00:00:00Z
updated_at: 2026-10-29T00:00:00Z
---

## Context

Deterministic backend so the UI epic can proceed without Postgres.

**Spec:** [`docs/specs/plugin-tasks.md`](../../../../docs/specs/plugin-tasks.md)

## Scenarios

**Scenario: in-memory backend passes the contract**
  Given InMemoryTaskBackend seeded with tasks across queues and states
  When  the contract suite runs
  Then  all tests pass

**Scenario: queue pause is reflected**
  Given an unpaused queue "reports"
  When  set_queue_paused("reports", True, actor="alice") is called
  Then  list_queues reports paused=True and the actor is recorded

## Acceptance Criteria

- [ ] Implements every Capability
- [ ] Records an in-memory audit list of (action, target, actor)
- [ ] `seed()` helper for demos/tests
- [ ] Contract suite green

## Files Likely Affected

- `plugins/hyperadmin-tasks/src/hyperadmin_tasks/backends/__init__.py`
- `plugins/hyperadmin-tasks/src/hyperadmin_tasks/backends/memory.py`
- `plugins/hyperadmin-tasks/tests/test_memory_backend.py`

## Dependencies

Depends on: `test-plugin-tasks-backend-contract-suite`

## Notes for Implementer

Pattern: `src/hyperadmin/realtime/pubsub.py` InMemoryPubSub.
