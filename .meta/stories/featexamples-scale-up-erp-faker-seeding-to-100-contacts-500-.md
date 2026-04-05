---
type: story
id: h9o-evYavGZN
title: "feat(examples): scale up ERP Faker seeding to 100+ contacts, 500+ invoices, 800+ bills"
status: done
priority: medium
assignee: null
labels:
  - agent-task
  - area:examples
  - size:S
estimate: null
epic_ref: null
github:
  issue_number: 351
  repo: yevheniidehtiar/hyper-admin
  last_sync_hash: sha256:47ce34b325d50745e35df612e821fa687e2ab8fe6e37e7f3c799837d1b1e47db
  synced_at: 2026-04-05T09:13:33.559Z
created_at: 2026-03-30T15:13:43Z
updated_at: 2026-03-30T15:19:32Z
---

## Parent Epic
Part of #172

## What
Scale up `examples/erp/seed.py` from current volumes (30 contacts, 50 invoices, 30 bills) to the target volumes specified in the epic:
- 100+ contacts
- 500+ invoices with 1-5 line items each
- 800+ bills with 1-3 line items each
- Corresponding journal entries for sent/paid invoices and to-pay/paid bills

## Acceptance Criteria
- [ ] `seed.py` generates >= 100 contacts, >= 500 invoices, >= 800 bills
- [ ] All journal entries are balanced (debits == credits)
- [ ] Seeding completes in under 30 seconds on SQLite
- [ ] No changes to model definitions
