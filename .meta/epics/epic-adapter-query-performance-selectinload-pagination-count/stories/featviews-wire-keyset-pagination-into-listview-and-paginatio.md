---
type: story
id: DbFmSvYPY4pw
title: "feat(views): wire keyset pagination into list_view and pagination template"
status: todo
priority: medium
assignee: null
labels:
  - agent-task
  - area:views
  - agent:claude
  - size:M
  - performance
estimate: null
epic_ref:
  id: bz_SWmq9yUG6
github:
  issue_number: 229
  repo: yevheniidehtiar/hyper-admin
  last_sync_hash: sha256:f97c6b40f9f7414a37f19d26ac449bcc4aaa6d2f1b0ad98459e83fdd491be4ab
  synced_at: 2026-04-05T09:13:33.559Z
created_at: 2026-03-27T00:41:28Z
updated_at: 2026-03-27T00:41:28Z
---

## Context
Part of Epic #211 (A4: Keyset/cursor pagination).

## Acceptance criteria
- [ ] `list_view()` detects `pagination_mode` from AdminOptions
- [ ] When keyset: passes cursor params to adapter, includes next_cursor in template context
- [ ] Pagination context includes `has_next`, `has_prev`, `next_cursor`, `prev_cursor`
- [ ] Default (offset) behavior unchanged

## Files
- `src/hyperadmin/views/dynamic.py`

## Dependencies
- Blocked by: #228 (A4.3 adapter impl), C2.3 (#234)
- Blocking: A4.5
