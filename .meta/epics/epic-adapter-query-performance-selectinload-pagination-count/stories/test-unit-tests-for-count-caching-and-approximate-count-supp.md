---
type: story
id: HbI9qnYkxdGg
title: "test: unit tests for count caching and approximate count support"
status: todo
priority: medium
assignee: null
labels:
  - agent-task
  - area:tests
  - area:adapters
  - agent:claude
  - size:M
  - performance
estimate: null
epic_ref:
  id: bz_SWmq9yUG6
github:
  issue_number: 223
  repo: yevheniidehtiar/hyper-admin
  last_sync_hash: sha256:28f475aa2b99d6c85fa866084870a8f4b4b5ce98a7ed283b1cda90524e23cacb
  synced_at: 2026-04-05T09:13:33.559Z
created_at: 2026-03-27T00:40:28Z
updated_at: 2026-03-27T00:40:28Z
---

## Context
Part of Epic #211 (A3: COUNT query optimization).
COUNT(*) runs on every list request with no caching. On 10M rows this takes seconds.

## Acceptance criteria
- [ ] Test that repeated `list()` calls within TTL reuse cached count (no extra COUNT query)
- [ ] Test that `count_cache_ttl_seconds=0` disables caching (default, backward compat)
- [ ] Test cache invalidation on `create()`, `update()`, `delete()`
- [ ] Test `use_approximate_count=True` flag returns approximate count (PostgreSQL path)
- [ ] Tests cover both SQLModelAdapter and SQLAlchemyAdapter

## Files
- `tests/unit/test_adapter_count_cache.py` (new)

## Dependencies
- Blocked by: none
- Blocking: A3.2
