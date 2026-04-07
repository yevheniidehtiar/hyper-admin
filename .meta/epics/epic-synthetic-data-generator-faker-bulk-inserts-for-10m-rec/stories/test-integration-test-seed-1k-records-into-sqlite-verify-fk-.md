---
type: story
id: M0pkQ7lmoEon
title: "test: integration test — seed 1K records into SQLite, verify FK integrity"
status: todo
priority: medium
assignee: null
labels:
  - agent-task
  - area:tests
  - agent:claude
  - size:M
  - performance
  - area:loadtest
estimate: null
epic_ref:
  id: SnjolGjNN_F7
github:
  issue_number: 255
  repo: yevheniidehtiar/hyper-admin
  last_sync_hash: sha256:00e8cc4a7a5aad017ec4c83dd42fe43795a540caf44041727cb6781c24e0c75f
  synced_at: 2026-04-07T17:23:23.790Z
created_at: 2026-03-27T01:06:59Z
updated_at: 2026-03-27T01:07:00Z
---

## Context
Part of Epic #246 (E: Synthetic Data Generator).

## Acceptance criteria
- [ ] Seed 1K records across all ERP tables into SQLite
- [ ] Assert all FK columns reference existing parent records (zero orphans)
- [ ] Assert row counts match expected ratios (e.g., InvoiceItems > Invoices)
- [ ] Assert enum values are within defined ranges
- [ ] Completes in <30s

## Files
- `tests/integration/test_seed_integrity.py` (new)

## Dependencies
- Blocked by: #249 (E2), #251 (E4), #254 (E7)
- Blocking: F9
