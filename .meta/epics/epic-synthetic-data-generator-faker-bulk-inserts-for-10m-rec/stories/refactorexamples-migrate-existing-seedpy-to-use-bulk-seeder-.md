---
type: story
id: 1GKiU6BeIgGD
title: "refactor(examples): migrate existing seed.py to use bulk seeder module"
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
  id: NZPmV9cxHHIZ
github:
  issue_number: 256
  repo: yevheniidehtiar/hyper-admin
  last_sync_hash: sha256:f80da3405da7bb13c5f9294c1e1412da8225ad9405208f92d5c59dd28e4d211c
  synced_at: 2026-04-05T09:13:33.559Z
created_at: 2026-03-27T01:07:42Z
updated_at: 2026-03-29T18:26:05Z
---

## Context
Part of Epic #246 (E: Synthetic Data Generator).

## Acceptance criteria
- [ ] Keep small-scale path (30 contacts, 50 invoices) for demo/dev mode
- [ ] Add bulk path that delegates to `loadtest/seeder.py` when `SEED_COUNT` env var is set
- [ ] Existing `seed_db()` function signature unchanged (backward compat)
- [ ] ERP example starts normally with both paths

## Files
- `examples/erp/seed.py` (modify)

## Dependencies
- Blocked by: #249 (E2), #251 (E4)
- Blocking: none
