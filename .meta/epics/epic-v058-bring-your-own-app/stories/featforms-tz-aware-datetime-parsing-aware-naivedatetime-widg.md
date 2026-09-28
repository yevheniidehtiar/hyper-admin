---
type: story
id: st-v058-byoa-32
title: "feat(forms): tz-aware datetime parsing, Aware/NaiveDatetime widgets, broader auto-now detection, preserve unchanged values"
status: todo
priority: high
assignee: null
labels:
  - size:M
  - planned
  - area:views
  - layer:views
estimate: null
epic_ref:
  id: ep-v058-byoa-01
created_at: 2026-09-28T00:00:00Z
updated_at: 2026-09-28T00:00:00Z
---

## Summary

`validate()` localises datetime strings using `adapter.datetime_kind` and the display timezone. `_is_datetime_annotation` covers `AwareDatetime`, `NaiveDatetime` and `Annotated`. `_is_auto_now_field` uses `is_auto_now_factory`. An unchanged submitted value keeps the original datetime.

**Spec:** [`docs/specs/bring-your-own-app.md`](../../../../docs/specs/bring-your-own-app.md) — section: A.6, A.7

## Files to Change

- `src/hyperadmin/views/forms.py`
- `src/hyperadmin/views/dynamic.py`
- `tests/unit/test_forms_datetime.py`

## Scenarios

```
Scenario: aware column localised
  Given tz Europe/Amsterdam
  And   an aware column
  When  '2026-07-01T10:00' is validated
  Then  the instance holds 08:00Z

Scenario: naive column kept
  Given a naive column
  When  '2026-07-01T10:00' is validated
  Then  the naive value is kept

Scenario: AwareDatetime widget
  Given a field annotated AwareDatetime
  When  the form is built
  Then  DateTimeInput is chosen

Scenario: utc_now hidden
  Given default_factory=utc_now
  When  the form is built
  Then  the field is excluded

Scenario: unchanged value preserved
  Given the submitted string equals the formatted initial value
  When  the form validates
  Then  the original datetime with microseconds is kept

Scenario: invalid datetime
  Given 'not-a-date' submitted
  When  the form validates
  Then  a translated field error is shown
```

## Acceptance Criteria

- [ ] aware column localised
- [ ] naive column kept
- [ ] AwareDatetime widget
- [ ] utc_now hidden
- [ ] unchanged value preserved
- [ ] invalid datetime
- [ ] `poe lint` and `poe test:unit` pass

## Blocked by

- `refactorforms-pk-aware-pydanticform-and-inlineformset-pk-cod` (st-v058-byoa-31)

## Parent

- Epic: `epic-v058-bring-your-own-app` (v0.5.8 — Bring Your Own App)
