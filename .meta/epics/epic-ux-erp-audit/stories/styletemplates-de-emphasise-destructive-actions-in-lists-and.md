---
type: story
id: st-ux-erp-15
title: "style(templates): de-emphasise destructive actions in lists and inline rows"
status: backlog
priority: medium
assignee: null
labels:
  - planned
  - enhancement
  - ui
  - css
  - area:templates
  - size:S
estimate: null
epic_ref:
  id: ep-ux-erp-01
created_at: 2026-11-07T07:21:11.537Z
updated_at: 2026-11-07T07:21:11.537Z
---

## Summary

Destructive actions carry the most visual weight: a red trash icon on every list row and solid red "Remove" buttons on inline rows, including blank ones (create starts with 2 empty item rows, edit adds extras).

Found by the UI/UX audit of `examples/erp` on `develop` @ `0014cc1` (2026-11-06): 51 pages × 6 devices (360/393 phone, 768/1180 tablet, 1280 laptop, 1920 desktop) × light/dark.

## Evidence

- Invoice list (all devices), invoice create/edit inline items.

## Files to Change

- **Modified:** `src/hyperadmin/static/css/_buttons.css`, `_inlines.css`, `components/inline_row.html`, inline formset extra count

## Scenarios

```
Scenario: delete is quiet until needed
  Given the invoice list
  Then  row delete icons are neutral and turn red on hover or focus
  And   a new invoice form starts with one empty item row
```

## Acceptance Criteria

- [ ] Confirm dialog unchanged

