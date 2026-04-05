---
type: story
id: XGIY92eOLRA4
title: "docs: scalability configuration guide"
status: todo
priority: medium
assignee: null
labels:
  - agent-task
  - area:docs
  - size:M
  - performance
estimate: null
epic_ref:
  id: 0ayKU0p1nvDC
github:
  issue_number: 244
  repo: yevheniidehtiar/hyper-admin
  last_sync_hash: sha256:db7bfece254e70e9ed07ce024378c38d1b4e72e7b16539139c751274eec72491
  synced_at: 2026-04-05T09:13:33.559Z
created_at: 2026-03-27T00:44:13Z
updated_at: 2026-03-29T18:26:14Z
---

## Context
Part of Epic #214 (D1: E2E scalability validation & documentation).

## Acceptance criteria
- [ ] Document all new AdminOptions fields with examples:
  - `list_select_related`, `detail_select_related`
  - `search_fields`
  - `count_cache_ttl_seconds`
  - `pagination_mode`
  - `preload_threshold`
  - `filter_cache_ttl_seconds`
- [ ] Document engine kwargs for production (pool_size, max_overflow)
- [ ] Document rate limiter setup
- [ ] PostgreSQL vs SQLite performance considerations
- [ ] Tuning guide for 10M+ record scenarios
- [ ] Include code examples for each optimization

## Files
- `docs/guides/scalability.md` (new)

## Dependencies
- Blocked by: #243 (D1.1 E2E tests)
- Blocking: none
