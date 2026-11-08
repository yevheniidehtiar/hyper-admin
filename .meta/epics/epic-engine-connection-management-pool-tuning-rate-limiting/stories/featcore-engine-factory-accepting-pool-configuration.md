---
type: story
id: IoS6IaXjSYg-
title: "feat(core): engine factory accepting pool configuration"
status: done
priority: medium
assignee: null
labels:
  - agent-task
  - area:core
  - size:S
  - performance
estimate: null
epic_ref:
  id: ed1DCvpnaZ1w
github:
  issue_number: 232
  repo: yevheniidehtiar/hyper-admin
  last_sync_hash: sha256:070104cf9112084a26a336b47199ac7a43b49b59cd7e0ae433052029dc2b1dba
  synced_at: 2026-04-07T17:23:23.790Z
created_at: 2026-03-27T00:42:09Z
updated_at: 2026-11-08T00:00:00Z
---

## Context
Part of Epic #212 (B1: Configurable engine kwargs).

## Acceptance criteria
- [x] `HyperAdminSettings` gains `database_pool_size`, `database_max_overflow`, `database_pool_timeout`, `database_pool_recycle` and `database_pool_pre_ping` (`HYPERADMIN_DATABASE_POOL_*`), applied to the engine built from `database_url`
- [x] `hyperadmin.db.build_engine(url, engine_kwargs)` forwards the kwargs to `create_async_engine` for host-built engines
- [x] Unset settings keep SQLAlchemy's defaults (5 + 10 overflow, 30 s)
- [x] Pool arguments are dropped for **in-memory** SQLite only: its `StaticPool` rejects them. File SQLite uses a queue pool and honours them (corrected from "SQLite skips pool kwargs")
- [x] Production starting values documented in `docs/compatibility.md`: `pool_size=20, max_overflow=40, pool_timeout=30`, and the `workers * (pool_size + max_overflow) < max_connections` rule
- [x] All tests from #231 pass

## Files
- `src/hyperadmin/db.py`
- `src/hyperadmin/core/settings.py`

## Dependencies
- Blocked by: #231
- Blocking: none (standalone improvement)

Delivered in #995.
