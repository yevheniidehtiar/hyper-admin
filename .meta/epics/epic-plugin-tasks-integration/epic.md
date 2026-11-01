---
type: epic
id: UuoF0wG2oyTQ
title: "epic(plugin-tasks): app integration — in-process worker, transactional enqueue, example app, docs"
status: backlog
priority: medium
owner: null
labels:
  - epic
  - agent-task
  - size:M
  - planned
  - plugin
milestone_ref:
  id: iOTodDwZehp2
github:
  issue_number: 759
  repo: yevheniidehtiar/hyper-admin
  synced_at: 2026-11-01T00:00:00Z
created_at: 2026-10-29T00:00:00Z
updated_at: 2026-10-29T00:00:00Z
---

## Overview

Make adopting pgtask with HyperAdmin a few lines: optional in-process worker tied to the admin
lifespan, transactional enqueue from a SQLAlchemy `AsyncSession`, an `examples/tasks/` app, and
docs (plugin page, role setup, "Coming from Celery"). HyperAdmin core features are **not**
moved onto the queue.

**SDD:** [`docs/specs/plugin-tasks.md`](../../../docs/specs/plugin-tasks.md)

## Tasks

- [ ] #762 feat-plugin-tasks-in-process-worker
- [ ] #763 feat-plugin-tasks-transactional-enqueue
- [ ] #760 docs-plugin-tasks-example-app
- [ ] #761 docs-plugin-tasks-guide-and-celery-migration

## Scenarios

**Scenario: transactional enqueue rolls back with the business write**
  Given an AsyncSession on a postgresql+psycopg engine
  When  a row is inserted, a task is enqueued in the session, and the transaction rolls back
  Then  neither the row nor the task exists

**Scenario: example app end-to-end**
  Given `docker compose up` in examples/tasks
  When  the user triggers the "Generate report" admin action
  Then  the task appears in /admin/tasks, runs on the worker and shows succeeded

## Acceptance Criteria

- [ ] `run_worker=True` starts/drains a pgtask Worker with the admin lifespan
- [ ] `enqueue_in_session()` works on psycopg, errors clearly on asyncpg
- [ ] `examples/tasks/` with docker-compose Postgres 16
- [ ] Docs page + Celery migration guide, experimental warning, role setup

## Blocked by

- epic-plugin-tasks-pgtask-adapter
