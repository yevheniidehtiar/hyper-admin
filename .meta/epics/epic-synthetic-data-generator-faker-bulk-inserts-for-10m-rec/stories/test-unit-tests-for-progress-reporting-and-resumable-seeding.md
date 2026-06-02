---
type: story
id: 9KevfLdaLuOv
title: "test: unit tests for progress reporting and resumable seeding"
status: done
priority: medium
assignee: null
labels:
  - agent-task
  - area:tests
  - size:S
  - performance
  - area:loadtest
estimate: null
epic_ref:
  id: SnjolGjNN_F7
github:
  issue_number: 252
  repo: yevheniidehtiar/hyper-admin
  last_sync_hash: sha256:7cab3e084fb4aadcbbc6131afbab9144adf59ded90e350d0a969ec26cf38c673
  synced_at: 2026-04-07T17:23:23.790Z
created_at: 2026-03-27T01:06:36Z
updated_at: 2026-06-03T00:00:00Z
---

## Context
Part of Epic #246 (E: Synthetic Data Generator).

## Acceptance criteria
- [ ] Test progress callbacks receive correct (current, total) counts
- [ ] Test high-water mark save to JSON file
- [ ] Test resume from high-water mark skips already-seeded tables
- [ ] Test cleanup of checkpoint file on completion

## Files
- `tests/unit/loadtest/test_progress.py` (new)

## Dependencies
- Blocked by: none
- Blocking: E6
