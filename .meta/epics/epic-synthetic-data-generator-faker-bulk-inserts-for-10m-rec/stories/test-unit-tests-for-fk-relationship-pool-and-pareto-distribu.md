---
type: story
id: c8hIRs-NOX8J
title: "test: unit tests for FK relationship pool and Pareto distribution"
status: todo
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
  issue_number: 250
  repo: yevheniidehtiar/hyper-admin
  last_sync_hash: sha256:ad8aa370c1eee2e86a9c4bf0e9fc9f79358689e463bf20caafbc2a802e16dd36
  synced_at: 2026-04-07T17:23:23.790Z
created_at: 2026-03-27T01:05:41Z
updated_at: 2026-03-29T18:26:10Z
---

## Context
Part of Epic #246 (E: Synthetic Data Generator).

## Acceptance criteria
- [ ] Test FK ID pool population from parent table IDs
- [ ] Test Pareto distribution sampling: ~80% of child records reference ~20% of parents
- [ ] Test referential integrity: all sampled IDs exist in parent pool
- [ ] Test configurable skew parameter

## Files
- `tests/unit/loadtest/test_fk_pool.py` (new)

## Dependencies
- Blocked by: none
- Blocking: E4
