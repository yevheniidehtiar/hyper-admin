---
type: story
id: st-ux-erp-13
title: "feat(templates): status pills for enum columns, with an overdue variant"
status: backlog
priority: medium
assignee: null
labels:
  - planned
  - enhancement
  - ui
  - area:templates
  - area:examples
  - size:S
estimate: null
epic_ref:
  id: ep-ux-erp-01
created_at: 2026-11-07T07:21:10.511Z
updated_at: 2026-11-07T07:21:10.511Z
---

## Summary

Status is plain text, so Draft, Sent, Paid and Cancelled look alike, and overdue invoices (Sent, due date passed) are not flagged. `components/pill.html` already exists.

Found by the UI/UX audit of `examples/erp` on `develop` @ `0014cc1` (2026-11-06): 51 pages × 6 devices (360/393 phone, 768/1180 tablet, 1280 laptop, 1920 desktop) × light/dark.

## Evidence

- Invoice and bill lists on every device.

## Files to Change

- **Modified:** `src/hyperadmin/templates/components/table_body.html` (enum → pill), `examples/erp/sales/admin.py`

## Scenarios

```
Scenario: status is shown as a pill
  Given an invoice with status Paid
  Then  its status cell is a pill with the success tone and the text "Paid"
```

## Acceptance Criteria

- [ ] Tones configurable per enum value; colour is never the only signal

