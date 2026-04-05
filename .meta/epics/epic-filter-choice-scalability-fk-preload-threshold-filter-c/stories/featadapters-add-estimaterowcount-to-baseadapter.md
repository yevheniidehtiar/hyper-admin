---
type: story
id: KWT_XJUtIqLV
title: "feat(adapters): add estimate_row_count() to BaseAdapter"
status: todo
priority: medium
assignee: null
labels:
  - agent-task
  - area:core
  - area:adapters
  - size:S
  - performance
estimate: null
epic_ref:
  id: s1CtxVQ8Mehl
github:
  issue_number: 238
  repo: yevheniidehtiar/hyper-admin
  last_sync_hash: sha256:b5e93af8a6d48a3b0941ffc4deab03a3bfbd5bc8209a3cf5b559bba7c71c8393
  synced_at: 2026-04-05T09:13:33.559Z
created_at: 2026-03-27T00:43:02Z
updated_at: 2026-03-29T18:26:19Z
---

## Context
Part of Epic #213 (C1: Smart FK preload threshold).

## Acceptance criteria
- [ ] `BaseAdapter` gains abstract method `estimate_row_count() -> int`
- [ ] SQLModelAdapter impl: uses cached `SELECT COUNT(*)` or `pg_class.reltuples` for Postgres
- [ ] SQLAlchemyAdapter impl: same pattern
- [ ] Result cached per adapter instance (low-TTL, ~60s)

## Files
- `src/hyperadmin/core/adapters.py`
- `src/hyperadmin/adapters/sqlmodel.py`
- `src/hyperadmin/adapters/sqlalchemy.py`

## Dependencies
- Blocked by: #237 (C1.2 core options)
- Blocking: C1.4
