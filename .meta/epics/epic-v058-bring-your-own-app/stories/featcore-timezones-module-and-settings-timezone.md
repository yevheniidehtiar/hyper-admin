---
type: story
id: st-v058-byoa-14
title: "feat(core): timezones module and settings.timezone"
status: todo
priority: high
assignee: null
labels:
  - size:M
  - planned
  - area:core
  - layer:domain
estimate: null
epic_ref:
  id: ep-v058-byoa-01
created_at: 2026-09-28T00:00:00Z
updated_at: 2026-09-28T00:00:00Z
---

## Summary

Add a pure `core/timezones.py` containing `utc_now`, `is_auto_now_factory`, `parse_datetime_input`, `format_datetime_input` and `to_display`, built on `zoneinfo` only. Add the setting `timezone` (`HYPERADMIN_TIMEZONE`, default `UTC`), validated with `ZoneInfo`.

**Spec:** [`docs/specs/bring-your-own-app.md`](../../../../docs/specs/bring-your-own-app.md) — section: A.7

## Files to Change

- `src/hyperadmin/core/timezones.py`
- `src/hyperadmin/core/settings.py`
- `tests/unit/test_timezones.py`

## Scenarios

```
Scenario: naive input is localised for aware columns
  Given tz Europe/Amsterdam and kind aware
  When  parse_datetime_input('2026-07-01T10:00') runs
  Then  2026-07-01T08:00Z is returned

Scenario: naive columns keep wall-clock time
  Given kind naive
  When  parse_datetime_input('2026-07-01T10:00') runs
  Then  a naive 10:00 datetime is returned

Scenario: aware values format in the display timezone
  Given an aware 08:00Z value and tz Europe/Amsterdam
  When  format_datetime_input runs
  Then  '2026-07-01T10:00:00' is returned

Scenario: tz-aware lambda is auto-now
  Given lambda: datetime.now(timezone.utc)
  When  is_auto_now_factory runs
  Then  True is returned

Scenario: invalid timezone setting is rejected
  Given HYPERADMIN_TIMEZONE=Mars/Olympus
  When  settings load
  Then  a validation error is raised

Scenario: DST gap is deterministic
  Given the Europe/Amsterdam spring-forward gap
  When  02:30 is parsed
  Then  the fold=0 result is returned
```

## Acceptance Criteria

- [ ] naive input is localised for aware columns
- [ ] naive columns keep wall-clock time
- [ ] aware values format in the display timezone
- [ ] tz-aware lambda is auto-now
- [ ] invalid timezone setting is rejected
- [ ] DST gap is deterministic
- [ ] `poe lint` and `poe test:unit` pass

## Blocked by

- `reviewspec-approve-byoa-sdd` (st-v058-byoa-00)

## Parent

- Epic: `epic-v058-bring-your-own-app` (v0.5.8 — Bring Your Own App)
