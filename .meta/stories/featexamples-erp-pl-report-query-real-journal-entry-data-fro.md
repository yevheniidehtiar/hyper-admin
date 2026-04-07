---
type: story
id: -ezipzIoElCr
title: "feat(examples): ERP P&L report — query real journal entry data from database"
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
  issue_number: 352
  repo: yevheniidehtiar/hyper-admin
  last_sync_hash: sha256:200d0e0a0f78e2c6c1c7dba36950f19a701b1f4ada590c32976a138650cb6182
  synced_at: 2026-04-07T17:23:23.791Z
created_at: 2026-03-30T15:13:58Z
updated_at: 2026-03-30T15:19:14Z
---

## Parent Epic
Part of #172

## What
Replace hardcoded placeholder data in `examples/erp/reports/views.py` with actual database queries that aggregate revenue and expense journal entries by year.

## Current State
The P&L view returns hardcoded data:
```python
report_data = [
    {"year": 2024, "revenue": 150000.0, "expenses": 120000.0, "profit": 30000.0},
    {"year": 2025, "revenue": 180000.0, "expenses": 140000.0, "profit": 40000.0},
]
```

## Target State
- Query `JournalLine` joined with `Account` and `JournalEntry`
- Group by year (from `JournalEntry.date_posted`)
- Sum credits on Revenue accounts as revenue
- Sum debits on Expense accounts as expenses
- Compute profit = revenue - expenses

## Acceptance Criteria
- [ ] P&L report shows dynamically computed data from seeded journal entries
- [ ] Revenue/expense figures change when seed data changes
- [ ] No hardcoded financial figures remain
- [ ] Template continues to work with the same context variables
