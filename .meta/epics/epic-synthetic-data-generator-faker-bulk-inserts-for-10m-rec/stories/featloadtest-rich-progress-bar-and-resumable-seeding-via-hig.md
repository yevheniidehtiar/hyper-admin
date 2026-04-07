---
type: story
id: _xUWyXD1XaQr
title: "feat(loadtest): Rich progress bar and resumable seeding via high-water mark"
status: todo
priority: medium
assignee: null
labels:
  - agent-task
  - area:examples
  - size:S
  - performance
  - area:loadtest
estimate: null
epic_ref:
  id: SnjolGjNN_F7
github:
  issue_number: 253
  repo: yevheniidehtiar/hyper-admin
  last_sync_hash: sha256:cf58b7c7bff78ad5b56f194050590b9d91af857b903446d6e79921812271a132
  synced_at: 2026-04-07T17:23:23.790Z
created_at: 2026-03-27T01:06:42Z
updated_at: 2026-03-29T18:26:07Z
---

## Context
Part of Epic #246 (E: Synthetic Data Generator).

## Acceptance criteria
- [ ] Per-table Rich progress bar with ETA and speed (rows/sec)
- [ ] Save checkpoint (table name + row count) to JSON after each table completes
- [ ] On restart, skip completed tables based on checkpoint
- [ ] Clean up checkpoint file on successful completion
- [ ] All tests from E5 pass

## Files
- `examples/erp/loadtest/progress.py` (new)

## Dependencies
- Blocked by: #249 (E2 seeder), #252 (E5 tests)
- Blocking: none
