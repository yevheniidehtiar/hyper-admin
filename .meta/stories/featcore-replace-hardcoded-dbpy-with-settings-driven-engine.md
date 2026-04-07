---
type: story
id: OoXHqE1LcTT3
title: "feat(core): replace hardcoded db.py with settings-driven engine"
status: done
priority: medium
assignee: null
labels:
  - enhancement
  - agent-task
  - area:core
  - size:S
  - area:settings
estimate: null
epic_ref: null
github:
  issue_number: 377
  repo: yevheniidehtiar/hyper-admin
  last_sync_hash: sha256:ecb82f26300866917d573a58ef5386e88166d7cb0ebbe0072132030663d59401
  synced_at: 2026-04-07T17:23:23.791Z
created_at: 2026-03-31T09:07:55Z
updated_at: 2026-03-31T19:59:00Z
---

## Context

`src/hyperadmin/db.py` currently has hardcoded `sqlite_url = "sqlite+aiosqlite:///:memory:"` and `echo=True`. Replace with settings-driven engine creation using `settings.database_url` and `settings.debug`.

## Scenarios

**Scenario: engine created from settings.database_url**
  Given `HyperAdminSettings(database_url="sqlite+aiosqlite:///prod.db")`
  When  the default engine is created
  Then  it uses `sqlite+aiosqlite:///prod.db`

**Scenario: echo follows settings.debug**
  Given `HyperAdminSettings(debug=True)`
  When  the default engine is created
  Then  `echo=True` on the engine

## Acceptance criteria

- [ ] `db.py` reads `database_url` from settings instead of hardcoded string
- [ ] `echo` derived from `settings.debug`
- [ ] Fallback to in-memory SQLite when no settings provided (backward compat)
- [ ] Unit tests

## Files likely affected

- `src/hyperadmin/db.py`

## Dependencies

Depends on: #375
