---
type: story
id: XwMkkYsoH9cV
title: "test(plugin-tasks): Postgres 16 harness running the contract suite against PgTaskBackend"
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
  id: krqQHG094vaz
github:
  issue_number: 751
  repo: yevheniidehtiar/hyper-admin
created_at: 2026-10-29T00:00:00Z
updated_at: 2026-10-29T00:00:00Z
---

## Context

TDD harness: spin up Postgres, migrate the pgtask schema, configure observer/administrator roles, run the contract suite.

**Spec:** [`docs/specs/plugin-tasks.md`](../../../../docs/specs/plugin-tasks.md)

## Scenarios

**Scenario: harness skips without Postgres**
  Given no PGTASK_TEST_DSN and no docker
  When  pytest runs
  Then  pgtask contract tests are skipped with reason "Postgres 16+ unavailable"

**Scenario: harness provisions roles**
  Given a Postgres 16 container
  When  the session fixture runs
  Then  pgtask migrate and configure-grants have created observer and administrator roles

## Acceptance Criteria

- [ ] Fixture via `PGTASK_TEST_DSN` or testcontainers
- [ ] Seeding hook enqueues/claims/fails real tasks with a pgtask Worker
- [ ] `pytest -m pgtask` marker

## Files Likely Affected

- `plugins/hyperadmin-tasks/tests/pgtask/conftest.py`
- `plugins/hyperadmin-tasks/tests/pgtask/test_contract.py`

## Dependencies

Depends on: `build-plugin-tasks-add-pgtask-extra`, `test-plugin-tasks-backend-contract-suite`

## Notes for Implementer

Bot token lacks `workflow` scope — any `.github/workflows` Postgres service change must be handed to the owner (label needs-human).
