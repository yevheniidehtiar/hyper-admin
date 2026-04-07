---
type: story
id: QxpKSmBCUYpr
title: "feat(views): pass search_fields from AdminOptions to adapter.list()"
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
  id: fkINeqAy7AVG
github:
  issue_number: 222
  repo: yevheniidehtiar/hyper-admin
  last_sync_hash: sha256:38226a3a0eef1ac70cd0ba4fe30b95190e78630ab98dc9d896515527ede6da2b
  synced_at: 2026-04-07T17:23:23.790Z
created_at: 2026-03-27T00:39:33Z
updated_at: 2026-03-29T18:26:26Z
---

## Context
Part of Epic #211 (A2: Configurable search fields).

## Acceptance criteria
- [ ] `list_view()` reads `self.options.search_fields` and passes to `adapter.list()`
- [ ] Default behavior unchanged when option not set

## Files
- `src/hyperadmin/views/dynamic.py`

## Dependencies
- Blocked by: #221 (A2.3 adapter impl)
- Blocking: D1.1
