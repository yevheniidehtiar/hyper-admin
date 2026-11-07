---
type: story
id: st-filters-number-range
title: "feat(filters): number ranges, and ranges for plain string list_filter fields"
status: backlog
priority: low
assignee: null
labels:
  - size:M
  - area:core
  - frontend
estimate: null
epic_ref: null
created_at: 2026-11-07T00:00:00Z
updated_at: 2026-11-07T00:00:00Z
---

## Summary

The rest of `st-v058-byoa-47`, which closed as superseded by `DateRangeFilter`. Add a `NumberRangeFilter` to
`hyperadmin.filters` with Min/Max inputs and an inline error, and let a plain string `list_filter` entry on a
date, datetime or number field get the matching range filter instead of an exact-match `<select>`.

## Files to Change

- `src/hyperadmin/filters/number.py` (new)
- `src/hyperadmin/filters/__init__.py`
- `src/hyperadmin/templates/components/filters/number_range.html` (new)
- `src/hyperadmin/core/discovery.py`
- `tests/unit/test_filters_number.py` (new)
- `tests/e2e/test_filters_number_range.py` (new)

## Scenarios

```
Scenario: number range filter narrows the list
  Given ProductAdmin(list_filter=[NumberRangeFilter(field="price")]) and products priced 5, 50 and 500
  When  the user enters Min 10 and Max 100 and applies
  Then  only the product priced 50 is listed

Scenario: invalid number shows an inline error
  Given the same ProductAdmin
  When  the user enters Min "abc" and applies
  Then  the filter shows an inline error and the list is not filtered

Scenario: plain string list_filter on a date field becomes a range
  Given OrderAdmin(list_filter=["created_at"])
  When  the list page renders
  Then  the filter offers From/To date inputs instead of a select
```

## Acceptance Criteria

- [ ] number range filter narrows the list
- [ ] invalid number shows an inline error
- [ ] plain string list_filter on a date field becomes a range
- [ ] `poe lint`, `poe test:cov-diff` (100% of changed lines) and the E2E tests pass
