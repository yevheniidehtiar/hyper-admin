---
type: story
id: WnjWJpDNp5lG
title: "feat(loadtest): FK ID pool manager with Pareto distribution sampling"
status: todo
priority: medium
assignee: null
labels:
  - agent-task
  - area:examples
  - agent:claude
  - size:M
  - performance
  - area:loadtest
estimate: null
epic_ref:
  id: SnjolGjNN_F7
github:
  issue_number: 251
  repo: yevheniidehtiar/hyper-admin
  last_sync_hash: sha256:0150502d26306408000cf212eec225d9d82e41ac69306462e7fdc6a748d6fd75
  synced_at: 2026-04-07T17:23:23.790Z
created_at: 2026-03-27T01:05:44Z
updated_at: 2026-03-27T01:05:44Z
---

## Context
Part of Epic #246 (E: Synthetic Data Generator).

## Acceptance criteria
- [ ] Pre-generate parent IDs after seeding parent tables
- [ ] Sample parent IDs with configurable Pareto skew (default: 80/20)
- [ ] Maintain pools across tables (e.g., Contact IDs shared by Invoice and Bill)
- [ ] Thread-safe for potential parallel seeding
- [ ] All tests from E3 pass

## Files
- `examples/erp/loadtest/seeder.py` (extend)

## Dependencies
- Blocked by: #250 (E3 tests)
- Blocking: E7, E8, E9
