---
type: story
id: st-ux-erp-04
title: "feat(templates): format money and decimal values in lists, cards and reports"
status: backlog
priority: high
assignee: null
labels:
  - planned
  - enhancement
  - area:templates
  - frontend
  - ui
  - size:M
estimate: null
epic_ref:
  id: ep-ux-erp-01
created_at: 2026-11-07T07:21:05.786Z
updated_at: 2026-11-07T07:21:05.786Z
---

## Summary

Amounts have no currency and no thousands separators, drop trailing zeros (`3013.3`, `6656.2`), show `0.0` for empty debit/credit, and are left-aligned. Accounting users can't scan or trust the figures.

Found by the UI/UX audit of `examples/erp` on `develop` @ `0014cc1` (2026-11-06): 51 pages × 6 devices (360/393 phone, 768/1180 tablet, 1280 laptop, 1920 desktop) × light/dark.

## Evidence

- Invoice list, bill list, journal lines, P&L report (`1048282.18`) on every device.
- Float noise was fixed in `855e959`; formatting is still missing.

## Files to Change

- **Modified:** `src/hyperadmin/views/template_filters.py` (decimal/money filter, locale-aware via Babel)
- **Modified:** `src/hyperadmin/templates/components/table_body.html`, `_table.css` (right-align numeric columns, tabular figures)
- **Modified:** `examples/erp` models/admins (money as `Decimal`, opt into the formatter), `examples/erp/templates/reports/profit_loss.html`

## Scenarios

```
Scenario: amounts are formatted
  Given an invoice with total 3013.3 in locale en
  When  the invoice list is shown
  Then  the total reads "3,013.30" and is right-aligned

Scenario: zero side of a journal line is blank
  Given a journal line with debit 947.28 and credit 0
  Then  the credit cell is empty
```

## Acceptance Criteria

- [ ] Two decimals, locale grouping, optional currency code per field
- [ ] Numeric columns right-aligned with tabular figures in table and card views

