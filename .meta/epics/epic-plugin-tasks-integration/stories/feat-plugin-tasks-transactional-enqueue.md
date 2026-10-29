---
type: story
id: Q2otsaWkvVh4
title: "feat(plugin-tasks): enqueue_in_session() transactional enqueue from SQLAlchemy AsyncSession"
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
  issue_number: 763
  repo: yevheniidehtiar/hyper-admin
created_at: 2026-10-29T00:00:00Z
updated_at: 2026-10-29T00:00:00Z
---

## Context

Outbox-free consistency: enqueue in the same transaction as the business write.

**Spec:** [`docs/specs/plugin-tasks.md`](../../../../docs/specs/plugin-tasks.md)

## Scenarios

**Scenario: commit**
  Given an AsyncSession on psycopg
  When  a row is inserted, enqueue_in_session is called, and the session commits
  Then  both the row and the task exist

**Scenario: rollback**
  Given the same setup
  When  the transaction rolls back
  Then  neither exists

**Scenario: asyncpg**
  Given an engine using asyncpg
  When  enqueue_in_session is called
  Then  TasksBackendError says the psycopg driver is required

## Acceptance Criteria

- [ ] Gets the raw psycopg AsyncConnection from the session and calls `Client.enqueue_on`
- [ ] Integration tests on Postgres harness

## Files Likely Affected

- `plugins/hyperadmin-tasks/src/hyperadmin_tasks/integration.py`
- `plugins/hyperadmin-tasks/tests/pgtask/test_enqueue_in_session.py`

## Dependencies

Depends on: `feat-plugin-tasks-pgtask-actions`

## Notes for Implementer

pgtask enqueue API differs between 0.4.0 PyPI and main — target the pinned version.
