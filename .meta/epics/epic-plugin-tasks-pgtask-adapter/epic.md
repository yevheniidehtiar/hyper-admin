---
type: epic
id: krqQHG094vaz
title: "epic(plugin-tasks): experimental pgtask adapter (PgTaskBackend)"
status: done
priority: high
owner: null
labels:
  - epic
  - agent-task
  - size:L
  - planned
  - plugin
milestone_ref:
  id: iOTodDwZehp2
github:
  issue_number: 746
  repo: yevheniidehtiar/hyper-admin
  synced_at: 2026-11-01T00:00:00Z
created_at: 2026-10-29T00:00:00Z
updated_at: 2026-11-01T00:00:00Z
---

## Overview

Implement `PgTaskBackend` on top of [`pgtask`](https://github.com/Kludex/pgtask) —
reads via the security-barrier observer views on an observer-role connection, actions via the
administrator role so `pgtask.administrator_audit` records the HyperAdmin actor. pgtask is
**pre-alpha**: all column mapping lives in one module, versions are pinned (`pgtask>=0.4,<0.5`),
and a startup probe fails fast on storage-protocol or column drift.

**SDD:** [`docs/specs/plugin-tasks.md`](../../../docs/specs/plugin-tasks.md)

## Tasks

- [ ] #747 build-plugin-tasks-add-pgtask-extra
- [ ] #751 test-plugin-tasks-postgres-contract-harness
- [ ] #750 feat-plugin-tasks-pgtask-read-side
- [ ] #748 feat-plugin-tasks-pgtask-actions
- [ ] #749 feat-plugin-tasks-pgtask-compat-probe

## Scenarios

**Scenario: adapter passes the contract suite on real Postgres**
  Given Postgres 16+ with the pgtask schema migrated
  When  the contract suite runs against PgTaskBackend
  Then  all contract tests pass

**Scenario: incompatible storage protocol fails fast**
  Given the database storage_protocol_range excludes the adapter's supported version
  When  the admin starts
  Then  startup fails with a TasksBackendError naming both versions

## Acceptance Criteria

- [ ] `[pgtask]` extra on hyperadmin-tasks; pgtask/psycopg imported only in `backends/pgtask.py`
- [ ] Reads only through observer views; actions record the actor in `pgtask.administrator_audit`
- [ ] Contract suite green against Postgres 16+ (skipped with a clear marker when unavailable)
- [ ] Storage-protocol and column-drift probe with actionable errors

## Blocked by

- epic-plugin-tasks-foundation (port + contract suite)
