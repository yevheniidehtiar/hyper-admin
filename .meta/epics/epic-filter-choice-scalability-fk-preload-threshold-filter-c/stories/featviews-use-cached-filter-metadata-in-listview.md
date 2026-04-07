---
type: story
id: gAlhYeNF0add
title: "feat(views): use cached filter metadata in list_view"
status: todo
priority: medium
assignee: null
labels:
  - agent-task
  - area:views
  - size:S
  - performance
estimate: null
epic_ref:
  id: PFtDf4Pyy04h
github:
  issue_number: 242
  repo: yevheniidehtiar/hyper-admin
  last_sync_hash: sha256:fc10dae20b384f6ae48ed2ae20595f02d6e4945ad72afa5c177115d63632638a
  synced_at: 2026-04-07T17:23:23.790Z
created_at: 2026-03-27T00:44:06Z
updated_at: 2026-03-29T18:26:15Z
---

## Context
Part of Epic #213 (C2: Filter metadata caching).

## Acceptance criteria
- [ ] `list_view()` calls cached `build_filter_metadata()` with TTL from AdminOptions
- [ ] CUD handlers (`create_view`, `update_view`, `delete_view`) invalidate filter cache
- [ ] Default behavior unchanged when `filter_cache_ttl_seconds=0`

## Files
- `src/hyperadmin/views/dynamic.py`

## Dependencies
- Blocked by: #241 (C2.2 core cache)
- Blocking: A4.4 (#229), D1.1
