---
type: story
id: st-ux-erp-17
title: "fix(examples): one name for the P&L report and a readable phone layout"
status: backlog
priority: low
assignee: null
labels:
  - planned
  - enhancement
  - area:examples
  - ui
  - size:S
estimate: null
epic_ref:
  id: ep-ux-erp-01
created_at: 2026-11-07T07:21:12.588Z
updated_at: 2026-11-07T07:21:12.588Z
---

## Summary

The report has three names: "Profit & Loss" (sidebar), "Annual Profit / Loss Report" (page), "Annual Profit & Loss — 2026" (tab). On phones the totals card leaves its left half empty.

Found by the UI/UX audit of `examples/erp` on `develop` @ `0014cc1` (2026-11-06): 51 pages × 6 devices (360/393 phone, 768/1180 tablet, 1280 laptop, 1920 desktop) × light/dark.

## Evidence

- `/admin/erp/profit-loss` on phone and laptop.

## Files to Change

- **Modified:** `examples/erp/templates/reports/profit_loss.html`, `examples/erp/reports/plugin.py`

## Scenarios

```
Scenario: consistent naming
  Then  the sidebar, page heading and browser tab all say "Profit & Loss"
```

## Acceptance Criteria

- [ ] Totals render as label and value on one row on phones

