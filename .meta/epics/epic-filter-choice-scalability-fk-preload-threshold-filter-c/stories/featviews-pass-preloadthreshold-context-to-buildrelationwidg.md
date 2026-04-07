---
type: story
id: tcxn220YlZuY
title: "feat(views): pass preload_threshold context to _build_relation_widgets"
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
  issue_number: 239
  repo: yevheniidehtiar/hyper-admin
  last_sync_hash: sha256:eb8f8dac227a055211dddb1fa249f797370612bafd60b51d2790d7ff74ae5a1f
  synced_at: 2026-04-07T17:23:23.790Z
created_at: 2026-03-27T00:43:06Z
updated_at: 2026-03-29T18:26:17Z
---

## Context
Part of Epic #213 (C1: Smart FK preload threshold).

## Acceptance criteria
- [ ] `_build_relation_widgets()` uses `preload_threshold` from AdminOptions
- [ ] Calls `estimate_row_count()` on related adapter to determine preload strategy
- [ ] Large FK tables automatically get lazy HTMX widget
- [ ] Small FK tables keep inline `<select>` behavior

## Files
- `src/hyperadmin/views/dynamic.py`

## Dependencies
- Blocked by: #238 (C1.3 adapter method)
- Blocking: D1.1
