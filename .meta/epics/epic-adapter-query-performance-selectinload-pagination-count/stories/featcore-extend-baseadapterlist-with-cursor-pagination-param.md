---
type: story
id: xUfHSOgU6OWv
title: "feat(core): extend BaseAdapter.list() with cursor pagination params"
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
  issue_number: 227
  repo: yevheniidehtiar/hyper-admin
  last_sync_hash: sha256:49c5db11d1bc89c3070ae293ac1595131da6d1a12d316f81172aa360e559665e
  synced_at: 2026-04-05T09:13:33.559Z
created_at: 2026-03-27T00:41:20Z
updated_at: 2026-03-27T00:41:20Z
---

## Context
Part of Epic #211 (A4: Keyset/cursor pagination).

## Acceptance criteria
- [ ] `AdminOptions` gains `pagination_mode: Literal["offset", "keyset"] = "offset"`
- [ ] `BaseAdapter.list()` gains `after_cursor: str | None = None` and `before_cursor: str | None = None`
- [ ] Return type extended: `tuple[list[Any], int, str | None]` (items, total, next_cursor)
- [ ] Backward compat: offset mode returns `None` for cursor
- [ ] All tests from A4.1 pass

## Files
- `src/hyperadmin/core/adapters.py`
- `src/hyperadmin/core/options.py`

## Dependencies
- Blocked by: #226 (A4.1 tests)
- Blocking: A4.3
