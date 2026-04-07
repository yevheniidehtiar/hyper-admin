---
type: story
id: JrYScYz6_VKl
title: "feat(core): add search_fields to AdminOptions and BaseAdapter.list()"
status: todo
priority: medium
assignee: null
labels:
  - agent-task
  - area:core
  - size:S
  - performance
estimate: null
epic_ref:
  id: fkINeqAy7AVG
github:
  issue_number: 220
  repo: yevheniidehtiar/hyper-admin
  last_sync_hash: sha256:67297704f62f2c161c4d132aabf4fddf7a17096c9f0dcf815af0bac7e6817444
  synced_at: 2026-04-07T17:23:23.790Z
created_at: 2026-03-27T00:39:22Z
updated_at: 2026-03-29T18:26:29Z
---

## Context
Part of Epic #211 (A2: Configurable search fields).

## Acceptance criteria
- [ ] `AdminOptions` gains `search_fields: list[str] = []`
- [ ] `BaseAdapter.list()` signature includes `search_fields: list[str] | None = None`
- [ ] When `search_fields` is empty, adapter uses its default behavior (backward compat)
- [ ] All tests from A2.1 pass

## Files
- `src/hyperadmin/core/options.py`
- `src/hyperadmin/core/adapters.py`

## Dependencies
- Blocked by: #219 (A2.1 tests)
- Blocking: A2.3
