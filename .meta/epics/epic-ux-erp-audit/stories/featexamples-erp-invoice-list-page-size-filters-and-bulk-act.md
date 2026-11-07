---
type: story
id: st-ux-erp-20
title: "feat(examples): ERP invoice list page size, filters and bulk actions"
status: backlog
priority: low
assignee: null
labels:
  - planned
  - enhancement
  - area:examples
  - needs-human
  - filtering
  - size:M
estimate: null
epic_ref:
  id: ep-ux-erp-01
created_at: 2026-11-07T07:21:14.178Z
updated_at: 2026-11-07T07:21:14.178Z
---

## Summary

A clerk with 500 invoices gets 10 rows per page, only Next (no page jump), a Status-only filter and no bulk actions. Needs a product decision on which to add to the showcase.

Found by the UI/UX audit of `examples/erp` on `develop` @ `0014cc1` (2026-11-06): 51 pages × 6 devices (360/393 phone, 768/1180 tablet, 1280 laptop, 1920 desktop) × light/dark.

## Evidence

- `/admin/invoice` on laptop and desktop.

## Files to Change

- **Modified:** `examples/erp/sales/admin.py`, `examples/erp/purchases/admin.py`

## Scenarios

```
Scenario: clerk finds overdue invoices quickly
  Then  the list offers date-range, customer and overdue filters, a page-size selector and "mark paid" as a bulk action
```

## Acceptance Criteria

- [ ] Owner agrees the scope before implementation

