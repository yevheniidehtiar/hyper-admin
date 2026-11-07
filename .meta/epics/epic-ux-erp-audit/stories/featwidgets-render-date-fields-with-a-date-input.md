---
type: story
id: st-ux-erp-07
title: "feat(widgets): render `date` fields with a date input"
status: backlog
priority: high
assignee: null
labels:
  - planned
  - enhancement
  - forms
  - area:views
  - frontend
  - size:S
estimate: null
epic_ref:
  id: ep-ux-erp-01
created_at: 2026-11-07T07:21:07.358Z
updated_at: 2026-11-07T07:21:07.358Z
---

## Summary

`date` fields (invoice/bill dates, journal entry date) render as plain text boxes: no picker, no date keyboard on phones, and the expected format is a guess. `datetime` fields already get a picker.

Found by the UI/UX audit of `examples/erp` on `develop` @ `0014cc1` (2026-11-06): 51 pages × 6 devices (360/393 phone, 768/1180 tablet, 1280 laptop, 1920 desktop) × light/dark.

## Evidence

- `input[name=date_issued]` is `type=text` on `/admin/invoice/create`; `FieldShowcase.launched_at` (datetime) gets a picker.

## Files to Change

- **Modified:** `src/hyperadmin/views/forms.py` (`_is_datetime_annotation` / widget mapping: `date` → `DateInput`)
- **New:** `src/hyperadmin/templates/widgets/date_input.html`

## Scenarios

```
Scenario: date field uses the native date picker
  Given a model with a date field
  When  its create form renders
  Then  the input has type=date and accepts the ISO value on submit
```

## Acceptance Criteria

- [ ] `date` and `Optional[date]` map to the date widget
- [ ] Existing values round-trip unchanged

