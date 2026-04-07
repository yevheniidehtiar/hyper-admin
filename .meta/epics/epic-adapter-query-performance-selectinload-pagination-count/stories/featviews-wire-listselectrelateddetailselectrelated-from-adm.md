---
type: story
id: zPmQgPhzRGt0
title: "feat(views): wire list_select_related/detail_select_related from AdminOptions into view handlers"
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
  issue_number: 218
  repo: yevheniidehtiar/hyper-admin
  last_sync_hash: sha256:70947879f6850f4a11014502ebcd2b7a33c98e6ad32fd8fa0fe824d730d73e11
  synced_at: 2026-04-07T17:23:23.790Z
created_at: 2026-03-27T00:39:01Z
updated_at: 2026-03-29T18:26:31Z
---

## Context
Part of Epic #211 (A1: Configurable relationship loading strategy).

## Acceptance criteria
- [ ] `list_view()` reads `self.options.list_select_related` and passes as `load_relations` to `adapter.list()`
- [ ] `detail_view()` reads `self.options.detail_select_related` and passes to `adapter.get()`
- [ ] Default behavior unchanged when options not set

## Files
- `src/hyperadmin/views/dynamic.py`

## Dependencies
- Blocked by: #217 (A1.3 adapter impl)
- Blocking: D1.1
