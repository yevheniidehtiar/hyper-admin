---
type: story
id: vJHnqPSz8Q3h
title: "feat(adapters): implement count caching with TTL in both adapters"
status: todo
priority: medium
assignee: null
labels:
  - agent-task
  - area:adapters
  - agent:claude
  - size:L
  - performance
estimate: null
epic_ref:
  id: bz_SWmq9yUG6
github:
  issue_number: 225
  repo: yevheniidehtiar/hyper-admin
  last_sync_hash: sha256:8f999f1a13a451bd72950cde5b7842646981ae4971ce67601a398e2384778bdd
  synced_at: 2026-04-05T09:13:33.559Z
created_at: 2026-03-27T00:41:05Z
updated_at: 2026-03-27T00:41:05Z
---

## Context
Part of Epic #211 (A3: COUNT query optimization).

## Acceptance criteria
- [ ] SQLModelAdapter caches count result with timestamp; reuses if within TTL
- [ ] SQLAlchemyAdapter same behavior
- [ ] Cache invalidated on `create()`, `update()`, `delete()`
- [ ] Optional `use_approximate_count` for PostgreSQL uses `pg_class.reltuples`
- [ ] Fallback to exact count for non-PostgreSQL backends
- [ ] All tests from A3.1 pass

## Files
- `src/hyperadmin/adapters/sqlmodel.py` (lines 82-85)
- `src/hyperadmin/adapters/sqlalchemy.py` (lines 52-66)

## Dependencies
- Blocked by: #224 (A3.2 core contract)
- Blocking: D1.1
