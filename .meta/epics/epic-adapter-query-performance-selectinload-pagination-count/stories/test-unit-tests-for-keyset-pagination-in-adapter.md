---
type: story
id: 4Kdqy59ui3qU
title: "test: unit tests for keyset pagination in adapter"
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
  issue_number: 226
  repo: yevheniidehtiar/hyper-admin
  last_sync_hash: sha256:8e4608b5023e6dc4312165df6daf6a451b2ca4932cf5acad546a5f7210076837
  synced_at: 2026-04-05T09:13:33.559Z
created_at: 2026-03-27T00:41:17Z
updated_at: 2026-03-27T00:41:17Z
---

## Context
Part of Epic #211 (A4: Keyset/cursor pagination).
OFFSET-based pagination degrades linearly — OFFSET 10M scans 10M rows before returning results.

## Acceptance criteria
- [ ] Test cursor-based `list()` with `after_cursor` param returns correct next page
- [ ] Test ordering by PK works correctly with cursor
- [ ] Test that returned cursor can fetch next page (chain test)
- [ ] Test backward compat: offset mode still works when `pagination_mode="offset"`
- [ ] Test edge cases: empty table, last page, first page

## Files
- `tests/unit/test_adapter_keyset_pagination.py` (new)

## Dependencies
- Blocked by: none
- Blocking: A4.2
