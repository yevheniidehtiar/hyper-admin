---
type: story
id: st-ux-erp-06
title: "fix(forms): readable validation messages and an error summary"
status: backlog
priority: high
assignee: null
labels:
  - planned
  - enhancement
  - forms
  - i18n
  - area:views
  - accessibility
  - size:M
estimate: null
epic_ref:
  id: ep-ux-erp-01
created_at: 2026-11-07T07:21:06.837Z
updated_at: 2026-11-07T07:21:06.837Z
---

## Summary

Field errors show raw Pydantic text ("Input should be a valid date or datetime, input is too short", "Input should be a valid integer, unable to parse string as an integer"). Long forms give no summary, so on a phone the user can't tell why Create did nothing.

Found by the UI/UX audit of `examples/erp` on `develop` @ `0014cc1` (2026-11-06): 51 pages × 6 devices (360/393 phone, 768/1180 tablet, 1280 laptop, 1920 desktop) × light/dark.

## Evidence

- Empty ERP invoice create form → three raw messages, no summary, first error not focused.

## Files to Change

- **Modified:** `src/hyperadmin/views/forms.py` / `translate_error_lazy` (map error types: missing, date_parsing, int_parsing, …)
- **Modified:** `src/hyperadmin/templates/form_layout.html` (error summary linking to fields)
- **Modified:** `src/hyperadmin/locale/*/LC_MESSAGES/messages.po`

## Scenarios

```
Scenario: friendly message for a missing date
  Given the invoice create form with Date issued empty
  When  the user clicks Create
  Then  the field says "Enter a date"
  And   an error summary at the top lists every invalid field and has focus
```

## Acceptance Criteria

- [ ] No Pydantic wording reaches the UI for common error types
- [ ] Summary links move focus to the field

