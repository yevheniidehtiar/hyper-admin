---
type: story
id: tAMtxtC836lJ
title: "docs(examples): examples/tasks app with Postgres, sample tasks, cron schedule and enqueue action"
status: backlog
priority: medium
assignee: null
labels:
  - agent-task
  - size:M
  - documentation
  - planned
  - plugin
estimate: null
epic_ref:
  id: UuoF0wG2oyTQ
github:
  issue_number: 760
  repo: yevheniidehtiar/hyper-admin
created_at: 2026-10-29T00:00:00Z
updated_at: 2026-10-29T00:00:00Z
---

## Context

Runnable demo used for manual QA and docs screenshots.

**Spec:** [`docs/specs/plugin-tasks.md`](../../../../docs/specs/plugin-tasks.md)

## Scenarios

**Scenario: example app end-to-end**
  Given `docker compose up` in examples/tasks
  When  the user triggers "Generate report"
  Then  the task runs and shows succeeded in /admin/tasks

**Scenario: failure demo**
  Given the flaky sample task
  When  it is enqueued
  Then  it retries, fails, and can be retried from the UI

## Acceptance Criteria

- [ ] docker-compose with postgres:16
- [ ] README with steps
- [ ] No downstream consumer names in files

## Files Likely Affected

- `examples/tasks/main.py`
- `examples/tasks/tasks.py`
- `examples/tasks/docker-compose.yml`
- `examples/tasks/README.md`

## Dependencies

Depends on: `feat-plugin-tasks-in-process-worker`, `feat-plugin-tasks-transactional-enqueue`, `feat-plugin-tasks-ui-actions`

## Notes for Implementer

Follow CONSTITUTION.md; 100% patch coverage (`poe test:cov-diff`).
