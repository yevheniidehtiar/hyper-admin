---
type: story
id: st-ux-erp-19
title: "feat(examples): ERP dashboard with open, overdue and monthly figures"
status: backlog
priority: low
assignee: null
labels:
  - planned
  - enhancement
  - area:examples
  - needs-human
  - dashboard
  - size:M
estimate: null
epic_ref:
  id: ep-ux-erp-01
created_at: 2026-11-07T07:21:13.668Z
updated_at: 2026-11-07T07:21:13.668Z
---

## Summary

The dashboard is a welcome paragraph and three links. A bookkeeper would expect open and overdue invoices, bills due and this month's result. Needs a product decision on scope.

Found by the UI/UX audit of `examples/erp` on `develop` @ `0014cc1` (2026-11-06): 51 pages × 6 devices (360/393 phone, 768/1180 tablet, 1280 laptop, 1920 desktop) × light/dark.

## Evidence

- `/admin/` on every device.

## Files to Change

- **Modified:** `examples/erp/templates/dashboard.html` (KPI tiles via existing chart/report components)

## Scenarios

```
Scenario: dashboard answers "what needs attention"
  Then  the dashboard shows open, overdue and due-this-week counts that link to filtered lists
```

## Acceptance Criteria

- [ ] Owner agrees the scope before implementation

