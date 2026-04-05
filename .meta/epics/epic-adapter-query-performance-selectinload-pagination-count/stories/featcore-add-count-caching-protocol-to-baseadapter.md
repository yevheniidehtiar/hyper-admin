---
type: story
id: A2TSkyjCkGZF
title: "feat(core): add count caching protocol to BaseAdapter"
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
  id: bz_SWmq9yUG6
github:
  issue_number: 224
  repo: yevheniidehtiar/hyper-admin
  last_sync_hash: sha256:d44b24b30681ec2eeb9836c7428d56877840bcaa9c4d8e589bdb384fe5756ee8
  synced_at: 2026-04-05T09:13:33.559Z
created_at: 2026-03-27T00:41:02Z
updated_at: 2026-03-27T00:41:02Z
---

## Context
Part of Epic #211 (A3: COUNT query optimization).

## Acceptance criteria
- [ ] `AdminOptions` gains `count_cache_ttl_seconds: int = 0` (0=disabled)
- [ ] `BaseAdapter` gains internal `_count_cache` dict with timestamp-based expiry
- [ ] CUD methods (`create`, `update`, `delete`) invalidate the cache
- [ ] Cache key includes filter hash for per-filter caching
- [ ] All tests from A3.1 pass

## Files
- `src/hyperadmin/core/adapters.py`
- `src/hyperadmin/core/options.py`

## Dependencies
- Blocked by: #223 (A3.1 tests)
- Blocking: A3.3
