---
type: story
id: st-ux-erp-03
title: "fix(templates): show an error when a form submit fails with a server error"
status: backlog
priority: high
assignee: null
labels:
  - planned
  - bug
  - forms
  - area:templates
  - frontend
  - ui
  - size:S
estimate: null
epic_ref:
  id: ep-ux-erp-01
created_at: 2026-11-07T07:21:05.248Z
updated_at: 2026-11-07T07:21:05.248Z
---

## Summary

When an HTMX form submit gets a 5xx, the page stays on the form with the user's edits and **no message**, so the user assumes it saved. After a reload the change is gone.

Found by the UI/UX audit of `examples/erp` on `develop` @ `0014cc1` (2026-11-06): 51 pages × 6 devices (360/393 phone, 768/1180 tablet, 1280 laptop, 1920 desktop) × light/dark.

## Evidence

- After the 500 above: URL unchanged, no visible alert (only hidden success/CSRF templates in the DOM), edited value still in the input.

## Files to Change

- **Modified:** `src/hyperadmin/static/js/` HTMX error handling (`htmx:responseError`)
- **Modified:** `src/hyperadmin/templates/components/error_toast.html` (or an alert above the form)

## Scenarios

```
Scenario: server error on save is visible
  Given the server answers a form submit with HTTP 500
  When  the user clicks Update
  Then  an alert says the record was not saved and the edits are kept
  And   the alert is announced to screen readers (role=alert)
```

## Acceptance Criteria

- [ ] 5xx and network failures on any HTMX submit show a translated error
- [ ] Focus moves to the alert; the form keeps the user's input

