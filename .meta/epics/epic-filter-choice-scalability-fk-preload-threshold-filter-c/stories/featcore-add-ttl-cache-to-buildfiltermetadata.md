---
type: story
id: 1e68Ekrku4wj
title: "feat(core): add TTL cache to build_filter_metadata()"
status: todo
priority: medium
assignee: null
labels:
  - agent-task
  - area:core
  - agent:claude
  - size:M
  - performance
estimate: null
epic_ref:
  id: PFtDf4Pyy04h
github:
  issue_number: 241
  repo: yevheniidehtiar/hyper-admin
  last_sync_hash: sha256:84b9530a88d7624285d9b5b1df2f5131da3d46d9f376129d7efbf45f4b3ae784
  synced_at: 2026-04-07T17:23:23.790Z
created_at: 2026-03-27T00:44:04Z
updated_at: 2026-03-27T00:44:04Z
---

## Context
Part of Epic #213 (C2: Filter metadata caching).

## Acceptance criteria
- [ ] In-memory cache keyed by `(model_name, tuple(filter_fields))`
- [ ] `AdminOptions` gains `filter_cache_ttl_seconds: int = 60`
- [ ] When TTL=0, no caching (backward compat default)
- [ ] Cache auto-invalidated after TTL expires
- [ ] Invalidation hook callable from CUD operations
- [ ] All tests from C2.1 pass

## Files
- `src/hyperadmin/core/discovery.py`
- `src/hyperadmin/core/options.py`

## Dependencies
- Blocked by: #240 (C2.1 tests)
- Blocking: C2.3
