---
type: story
id: st-ux-erp-12
title: "fix(widgets): one control per FK field instead of a search box plus a select"
status: backlog
priority: medium
assignee: null
labels:
  - planned
  - enhancement
  - forms
  - ui
  - area:templates
  - size:M
estimate: null
epic_ref:
  id: ep-ux-erp-01
created_at: 2026-11-07T07:21:09.976Z
updated_at: 2026-11-07T07:21:09.976Z
---

## Summary

Preloaded FK fields render a search box **and** a dropdown for the same value, with a `---------` placeholder. Users don't know which one to use.

Found by the UI/UX audit of `examples/erp` on `develop` @ `0014cc1` (2026-11-06): 51 pages × 6 devices (360/393 phone, 768/1180 tablet, 1280 laptop, 1920 desktop) × light/dark.

## Evidence

- Customer on `/admin/invoice/create`, Supplier on bills, Category on Field Showcase.

## Files to Change

- **Modified:** `src/hyperadmin/templates/widgets/relation_select_input.html`, `widgets/autocomplete.html`, `static/js/autocomplete.js`

## Scenarios

```
Scenario: a single searchable combobox
  Given the invoice create form
  Then  the Customer field is one combobox with the placeholder "Choose a customer…"
```

## Acceptance Criteria

- [ ] Keyboard and screen-reader behaviour follow the ARIA combobox pattern

