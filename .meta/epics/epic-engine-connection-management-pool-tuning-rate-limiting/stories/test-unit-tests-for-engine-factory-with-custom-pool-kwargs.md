---
type: story
id: aBlIYeXaZDK-
title: "test: unit tests for engine factory with custom pool kwargs"
status: todo
priority: medium
assignee: null
labels:
  - agent-task
  - area:tests
  - size:S
  - performance
estimate: null
epic_ref:
  id: fAZXHu4TtVlv
github:
  issue_number: 231
  repo: yevheniidehtiar/hyper-admin
  last_sync_hash: sha256:4cd742b844cefab58ef42832e18a26678a8930a29c13c601308f65a48c534c6e
  synced_at: 2026-04-05T09:13:33.559Z
created_at: 2026-03-27T00:42:07Z
updated_at: 2026-03-29T18:26:23Z
---

## Context
Part of Epic #212 (B1: Configurable engine kwargs).
Currently `db.py` creates a bare `create_async_engine()` with no pool config.

## Acceptance criteria
- [ ] Test that engine factory accepts and forwards `pool_size`, `max_overflow`, `pool_timeout`, `pool_recycle`
- [ ] Test defaults are sensible (SQLAlchemy defaults preserved when no kwargs)
- [ ] Test SQLite engine skips pool kwargs (uses NullPool)

## Files
- `tests/unit/test_db_engine.py` (new)

## Dependencies
- Blocked by: none
- Blocking: B1.2
