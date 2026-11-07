---
type: story
id: st-ux-erp-02
title: "fix(widgets): FK select drops the current value when it is outside the preloaded options"
status: backlog
priority: critical
assignee: null
labels:
  - planned
  - bug
  - forms
  - area:views
  - frontend
  - size:S
estimate: null
epic_ref:
  id: ep-ux-erp-01
created_at: 2026-11-07T07:21:04.735Z
updated_at: 2026-11-07T07:21:04.735Z
---

## Summary

On an edit page the relation `<select>` only renders the preloaded options. When the record's current FK value is not among them, nothing is `selected`, the field shows `---------` and the record can no longer be saved ("Input should be a valid integer"). About half the ERP invoices are affected (100 contacts, 50 options).

Found by the UI/UX audit of `examples/erp` on `develop` @ `0014cc1` (2026-11-06): 51 pages × 6 devices (360/393 phone, 768/1180 tablet, 1280 laptop, 1920 desktop) × light/dark.

## Evidence

- `/admin/invoice/1/edit`: `select[name=customer_id]` has 51 options, value `""`; the list shows the invoice's customer.
- 7 of 15 invoice edits failed with 422 on `customer_id` for this reason.

## Files to Change

- **Modified:** `src/hyperadmin/core/fields.py` / choice building (always include the current value as an option)
- **Modified:** `src/hyperadmin/templates/widgets/relation_select_input.html`
- **New:** unit + E2E test with more targets than the preload window

## Scenarios

```
Scenario: current FK value is shown even when not preloaded
  Given an invoice whose customer is not in the preloaded option window
  When  the user opens its edit page
  Then  the Customer field shows that customer as selected
  And   saving without changes succeeds
```

## Acceptance Criteria

- [ ] Selected value always rendered, for single and multi relation selects
- [ ] Above the preload limit the widget falls back to remote autocomplete only

