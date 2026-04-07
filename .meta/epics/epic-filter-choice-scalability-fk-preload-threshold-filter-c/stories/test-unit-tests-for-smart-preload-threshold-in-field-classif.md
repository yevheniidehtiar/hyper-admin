---
type: story
id: 4idYM4Dfgczu
title: "test: unit tests for smart preload threshold in field classification"
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
  issue_number: 236
  repo: yevheniidehtiar/hyper-admin
  last_sync_hash: sha256:99305ef334855dcc7e0f52d6f6ea297383942294c85d67300abca7b28781e795
  synced_at: 2026-04-07T17:23:23.790Z
created_at: 2026-03-27T00:42:51Z
updated_at: 2026-03-29T18:26:20Z
---

## Context
Part of Epic #213 (C1: Smart FK preload threshold).
FK `preload=True` default loads ALL related records as `<option>` tags — browser crash on 10M+ row targets.

## Acceptance criteria
- [ ] Test that `classify_field()` returns `preload=False` when related table row count exceeds `preload_threshold`
- [ ] Test configurable threshold via AdminOptions (default 500)
- [ ] Test enum fields always `preload=True` regardless of threshold
- [ ] Test M2M fields always `preload=False` regardless of threshold
- [ ] Test FK to small table (<500 rows) still `preload=True`

## Files
- `tests/unit/test_field_preload_threshold.py` (new)

## Dependencies
- Blocked by: none
- Blocking: C1.2
