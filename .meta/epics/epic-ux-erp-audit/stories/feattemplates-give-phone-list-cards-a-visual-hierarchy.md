---
type: story
id: st-ux-erp-14
title: "feat(templates): give phone list cards a visual hierarchy"
status: backlog
priority: medium
assignee: null
labels:
  - planned
  - enhancement
  - responsive
  - ui
  - area:templates
  - size:M
estimate: null
epic_ref:
  id: ep-ux-erp-01
created_at: 2026-11-07T07:21:11.052Z
updated_at: 2026-11-07T07:21:11.052Z
---

## Summary

On phones each list card stacks 6 label/value rows with equal weight, so about 4 invoices fit on a screen, and the only visible action is a red Delete.

Found by the UI/UX audit of `examples/erp` on `develop` @ `0014cc1` (2026-11-06): 51 pages × 6 devices (360/393 phone, 768/1180 tablet, 1280 laptop, 1920 desktop) × light/dark.

## Evidence

- `/admin/invoice` at 393×852.

## Files to Change

- **Modified:** `src/hyperadmin/templates/components/table_body.html`, `src/hyperadmin/static/css/_table.css`

## Scenarios

```
Scenario: card shows the key facts first
  Given the invoice list on a phone
  Then  each card title is "number · customer", amount and status sit on one line, dates are secondary
  And   tapping the card opens the record
```

## Acceptance Criteria

- [ ] At least 6 cards visible per screen at 393×852 with the ERP data

