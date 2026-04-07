---
type: story
id: KJRf5FFTkAp4
title: "feat(examples): ERP SQLModel domain models (contacts, sales, purchases, accounting)"
status: done
priority: medium
assignee: null
labels:
  - in-progress
  - agent-task
  - area:examples
  - size:L
estimate: null
epic_ref:
  id: w5uOHybW-qhx
github:
  issue_number: 192
  repo: yevheniidehtiar/hyper-admin
  last_sync_hash: sha256:85051f0e29977db21e2e66887c0abf5aa2615e1aab691e8532dd50280f5fb19d
  synced_at: 2026-04-07T17:23:23.790Z
created_at: 2026-03-25T13:41:11Z
updated_at: 2026-03-30T16:09:12Z
---

> **Part of:** #172
> **Depends on:** #191

## Acceptance Criteria
- [ ] `examples/erp/contacts/models.py`: `Contact`, `Address`
- [ ] `examples/erp/sales/models.py`: `Invoice`, `InvoiceItem`, `TaxRate`
- [ ] `examples/erp/purchases/models.py`: `Bill`, `BillItem`
- [ ] `examples/erp/accounting/models.py`: `Account`, `JournalEntry`, `JournalLine`
- [ ] All relationships wired with `back_populates`; `table=True`; `create_all` succeeds with no FK violations
- [ ] `mypy` clean

## Files
- `examples/erp/contacts/models.py`
- `examples/erp/sales/models.py`
- `examples/erp/purchases/models.py`
- `examples/erp/accounting/models.py`

