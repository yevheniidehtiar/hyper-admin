---
type: story
id: st-v058-byoa-24
title: "feat(adapters): apply FilterCondition lists with dict back-compat"
status: done
priority: high
assignee: null
labels:
  - size:S
  - planned
  - area:adapters
  - layer:logic
estimate: null
epic_ref:
  id: ep-v058-byoa-01
created_at: 2026-09-28T00:00:00Z
updated_at: 2026-10-17T00:00:00Z
---

## Summary

Add `adapters/_filter_clause.build_clause`, shared by both adapters. `BaseAdapter.list(filters=...)` accepts either a legacy dict or a sequence of `FilterCondition`, passed through `normalize_filters`.

**Spec:** [`docs/specs/bring-your-own-app.md`](../../../../docs/specs/bring-your-own-app.md) — section: D.3

## Files to Change

- `src/hyperadmin/adapters/_filter_clause.py`
- `src/hyperadmin/adapters/sqlmodel.py`
- `src/hyperadmin/adapters/sqlalchemy.py`
- `src/hyperadmin/core/adapters.py`
- `tests/unit/adapters/test_filter_conditions.py`

## Scenarios

```
Scenario: legacy dict filters still work
  Given adapter.list(filters={'is_active': True})
  When  list() runs
  Then  only active rows are returned

Scenario: range condition applies
  Given conditions quantity gte 2 and lte 4
  When  list() runs
  Then  only rows with 2<=quantity<=4 are returned

Scenario: isnull condition applies
  Given condition deleted_at isnull true
  When  list() runs
  Then  only rows with a NULL deleted_at are returned
```

## Acceptance Criteria

- [ ] legacy dict filters still work
- [ ] range condition applies
- [ ] isnull condition applies
- [ ] `poe lint` and `poe test:unit` pass

## Review amendments (2026-09-28)

- Adds `adapters/introspection.coerce_column_value` (moved from `-15`) and applies it to the choices cascade values.
- Range operators (`gte`, `lte`, `in`, `isnull`) are deferral candidates under Owner decision 8. If they are deferred, ship `exact` only and keep the `op` field.

## Review amendments (2026-10-17)

- `BaseAdapter.list_as_envelope`'s `filters` parameter and docstring now match `BaseAdapter.list`'s widened `Mapping[str, Any] | Sequence[FilterCondition] | None` contract.
- `docs/api/adapters.md` now documents that `filters` is a legacy dict or a `Sequence[FilterCondition]`, and points custom adapters at `normalize_filters`.
- `core/filtering.coerce_filter_value`'s `int` path now bound-checks to the signed 64-bit range, so an out-of-range cascade-filter value (e.g. `get_choices(..., fk="9"*25)`) raises `FilterValueError` instead of overflowing a DBAPI bind later (`OverflowError`, uncaught by `get_choices`'s `except ValueError`).
- Added `core/filtering.MAX_IN_VALUES` (100): `parse_filter_params` now rejects an oversized `__in` list as a field error, and `adapters/_filter_clause.build_clause` defensively rejects an oversized `in` `FilterCondition` built directly, before either reaches a driver-level parameter limit.

## Blocked by

- `featcore-typed-filter-coercion-and-filtercondition` (st-v058-byoa-19)
- `refactoradapters-pk-agnostic-get-get-related-update-delete-g` (st-v058-byoa-22)

## Parent

- Epic: `epic-v058-bring-your-own-app` (v0.5.8 — Bring Your Own App)
