---
type: story
id: jRREDrVrVQqp
title: "feat(loadtest): batch data generator with Faker + SQLAlchemy Core bulk inserts"
status: todo
priority: medium
assignee: null
labels:
  - agent-task
  - area:examples
  - size:M
  - performance
  - area:loadtest
estimate: null
epic_ref:
  id: SnjolGjNN_F7
github:
  issue_number: 249
  repo: yevheniidehtiar/hyper-admin
  last_sync_hash: sha256:e6db30603e65fa33fccd772104dfc0eda2501b8e69643cc197ccb576c0afc45e
  synced_at: 2026-04-07T17:23:23.790Z
created_at: 2026-03-27T01:05:38Z
updated_at: 2026-03-29T18:26:11Z
---

## Context
Part of Epic #246 (E: Synthetic Data Generator).

## Acceptance criteria
- [ ] Generate batches of N rows per ERP table using Faker for realistic field values
- [ ] Use `connection.execute(insert(Model).values(batch))` for bulk inserts
- [ ] Configurable `batch_size` (default 5000)
- [ ] Support all 14 ERP models: Contact, Account, Invoice, InvoiceItem, Bill, BillItem, JournalEntry, JournalLine + auth models
- [ ] Respect seeding order: Accounts → Contacts → Invoices → InvoiceItems → Bills → BillItems → JournalEntries → JournalLines
- [ ] All tests from E1 pass

## Files
- `examples/erp/loadtest/seeder.py` (new)
- `examples/erp/loadtest/__init__.py` (new)

## Dependencies
- Blocked by: #248 (E1 tests)
- Blocking: E6, E7, E8, E9
