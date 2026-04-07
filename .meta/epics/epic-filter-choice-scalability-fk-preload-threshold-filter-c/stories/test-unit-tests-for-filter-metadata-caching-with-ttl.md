---
type: story
id: ceCydi5Q5_d6
title: "test: unit tests for filter metadata caching with TTL"
status: todo
priority: medium
assignee: null
labels:
  - agent-task
  - area:tests
  - area:core
  - size:M
  - performance
estimate: null
epic_ref:
  id: PFtDf4Pyy04h
github:
  issue_number: 240
  repo: yevheniidehtiar/hyper-admin
  last_sync_hash: sha256:2f3937cb03d805eeba18c624c553a42d68c1ad2fade5ebb449b7554f06e7e2cf
  synced_at: 2026-04-07T17:23:23.790Z
created_at: 2026-03-27T00:44:01Z
updated_at: 2026-03-29T18:26:16Z
---

## Context
Part of Epic #213 (C2: Filter metadata caching).
`build_filter_metadata()` loads 1000 items per FK field on every list request with no caching.

## Acceptance criteria
- [ ] Test that repeated calls within TTL return cached result (no extra DB query)
- [ ] Test cache invalidation after TTL expires
- [ ] Test per-model cache isolation (model A cache doesn't affect model B)
- [ ] Test `filter_cache_ttl_seconds=0` disables caching (backward compat)
- [ ] Test cache invalidation on CUD operations

## Files
- `tests/unit/test_filter_metadata_cache.py` (new)

## Dependencies
- Blocked by: none
- Blocking: C2.2
