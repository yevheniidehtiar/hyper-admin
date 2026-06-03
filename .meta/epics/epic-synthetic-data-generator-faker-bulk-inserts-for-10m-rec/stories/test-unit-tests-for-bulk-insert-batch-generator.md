---
type: story
id: ZnqW073pXFtY
title: "test: unit tests for bulk insert batch generator"
status: done
priority: medium
assignee: null
labels:
  - agent-task
  - ready
  - area:tests
  - size:S
  - performance
  - area:loadtest
estimate: null
epic_ref:
  id: SnjolGjNN_F7
github:
  issue_number: 248
  repo: yevheniidehtiar/hyper-admin
  last_sync_hash: sha256:8bf2a6e78c862daa69b898ca7d077479ade1b0c575e81faed33638b8918f74f5
  synced_at: 2026-04-07T17:23:23.790Z
created_at: 2026-03-27T01:05:33Z
updated_at: 2026-06-03T00:00:00Z
---

## Context
Part of Epic #246 (E: Synthetic Data Generator).

## Acceptance criteria
- [ ] Test batch splitting: 10,000 records with batch_size=5000 yields 2 batches
- [ ] Test correct row count per table after batch generation
- [ ] Test field value generation matches expected Faker types (names, emails, dates, enums)
- [ ] Test configurable batch_size parameter

## Files
- `tests/unit/loadtest/test_seeder.py` (new)

## Dependencies
- Blocked by: none
- Blocking: E2
