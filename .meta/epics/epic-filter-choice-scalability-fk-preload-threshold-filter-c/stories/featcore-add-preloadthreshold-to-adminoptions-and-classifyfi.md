---
type: story
id: Nxk4hCwfTwHy
title: "feat(core): add preload_threshold to AdminOptions and classify_field()"
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
  id: PFtDf4Pyy04h
github:
  issue_number: 237
  repo: yevheniidehtiar/hyper-admin
  last_sync_hash: sha256:e9a8730296d899581c27fbf82aa4f169aa93e9be718eadf207e25df323d9e46d
  synced_at: 2026-04-07T17:23:23.790Z
created_at: 2026-03-27T00:42:58Z
updated_at: 2026-03-27T00:42:58Z
---

## Context
Part of Epic #213 (C1: Smart FK preload threshold).

## Acceptance criteria
- [ ] `AdminOptions` gains `preload_threshold: int = 500`
- [ ] `classify_field()` accepts estimated row count for FK target table
- [ ] When row count > threshold, forces `preload=False`
- [ ] Enum fields exempt (always preload)
- [ ] All tests from C1.1 pass

## Files
- `src/hyperadmin/core/options.py`
- `src/hyperadmin/core/fields.py`

## Dependencies
- Blocked by: #236 (C1.1 tests)
- Blocking: C1.3
