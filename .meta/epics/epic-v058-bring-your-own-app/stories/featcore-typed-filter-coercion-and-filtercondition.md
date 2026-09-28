---
type: story
id: st-v058-byoa-19
title: "feat(core): typed filter coercion and FilterCondition"
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

Add a pure `core/filtering.py` with `FilterCondition`, `coerce_filter_value`, `parse_filter_params` (operators `exact`, `gte`, `lte`, `in` and `isnull`; whitelist `allowed`), `normalize_filters` and `FilterValueError`. It uses `core/timezones.py` to align date bounds on aware columns.

**Spec:** [`docs/specs/bring-your-own-app.md`](../../../../docs/specs/bring-your-own-app.md) — section: D.3

## Files to Change

- `src/hyperadmin/core/filtering.py`
- `tests/unit/test_filtering.py`

## Scenarios

```
Scenario: integer value is coerced
  Given annotation int
  When  coerce_filter_value(int, '3') runs
  Then  3 is returned

Scenario: UUID parse error
  Given annotation UUID
  When  raw is 'not-a-uuid'
  Then  FilterValueError names the field

Scenario: range params parse
  Given params filter_created_at__gte and __lte with created_at allowed
  When  parse_filter_params runs
  Then  two conditions gte and lte are returned

Scenario: non-whitelisted field is ignored
  Given allowed=['is_active']
  When  params contain filter_password_hash
  Then  no condition is produced
```

## Acceptance Criteria

- [ ] integer value is coerced
- [ ] UUID parse error
- [ ] range params parse
- [ ] non-whitelisted field is ignored
- [ ] `poe lint` and `poe test:unit` pass

## Blocked by

- `featcore-timezones-module-and-settings-timezone` (st-v058-byoa-14)

## Parent

- Epic: `epic-v058-bring-your-own-app` (v0.5.8 — Bring Your Own App)
