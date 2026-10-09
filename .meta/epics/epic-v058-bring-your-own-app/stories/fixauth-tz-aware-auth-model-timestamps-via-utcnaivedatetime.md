---
type: story
id: st-v058-byoa-16
title: "fix(auth): tz-aware auth model timestamps via UTCNaiveDateTime and utc_now"
status: todo
priority: high
assignee: null
labels:
  - size:S
  - planned
  - area:auth
  - layer:domain
estimate: null
epic_ref:
  id: ep-v058-byoa-01
created_at: 2026-09-28T00:00:00Z
updated_at: 2026-09-28T00:00:00Z
---

## Summary

Add `auth/_types.py` `UTCNaiveDateTime`, which keeps the naive `timestamp` DDL and returns aware UTC values. Switch `auth/models.py:26,59,89` to `default_factory=utc_now, sa_type=UTCNaiveDateTime()`. No migration is needed.

**Spec:** [`docs/specs/bring-your-own-app.md`](../../../../docs/specs/bring-your-own-app.md) — section: A.8

## Files to Change

- `src/hyperadmin/auth/_types.py`
- `src/hyperadmin/auth/models.py`
- `tests/unit/test_auth_datetime_types.py`

## Scenarios

```
Scenario: created_at is aware UTC
  Given a new User
  When  it is saved and reloaded
  Then  created_at is an aware UTC datetime

Scenario: naive bind is stored unchanged
  Given a naive datetime bound to UTCNaiveDateTime
  When  it is saved and reloaded
  Then  the value is unchanged and tagged UTC

Scenario: aware bind is normalised
  Given an aware +02:00 datetime
  When  it is saved
  Then  the stored value is naive UTC

Scenario: DDL is unchanged
  Given the existing hyperadmin_users table
  When  create_all runs
  Then  no column type change is emitted
```

## Acceptance Criteria

- [ ] created_at is aware UTC
- [ ] naive bind is stored unchanged
- [ ] aware bind is normalised
- [ ] DDL is unchanged
- [ ] `poe lint` and `poe test:unit` pass

## Blocked by

- `featcore-timezones-module-and-settings-timezone` (st-v058-byoa-14)

## Parent

- Epic: `epic-v058-bring-your-own-app` (v0.5.8 — Bring Your Own App)
