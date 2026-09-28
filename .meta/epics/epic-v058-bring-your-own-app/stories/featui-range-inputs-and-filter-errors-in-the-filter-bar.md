---
type: story
id: st-v058-byoa-47
title: "feat(ui): range inputs and filter errors in the filter bar"
status: todo
priority: high
assignee: null
labels:
  - size:M
  - planned
  - area:templates
  - layer:ui
  - frontend
estimate: null
epic_ref:
  id: ep-v058-byoa-01
created_at: 2026-09-28T00:00:00Z
updated_at: 2026-09-28T00:00:00Z
---

## Summary

`build_filter_metadata` gains date, datetime and number range kinds. The filter bar renders `filter-{field}-from`/`-to` inputs and a `filter-error` element.

**Spec:** [`docs/specs/bring-your-own-app.md`](../../../../docs/specs/bring-your-own-app.md) — section: D.3

## Files to Change

- `src/hyperadmin/core/discovery.py`
- `src/hyperadmin/templates/components/filter_bar.html`
- `tests/unit/test_filter_metadata.py`
- `tests/e2e/test_filters_typed.py`

## Scenarios

```
Scenario: date range filter
  Given list_filter ['created_at']
  When  the user fills filter-created_at-from and filter-created_at-to and applies
  Then  only rows in range are listed

Scenario: filter error shown
  Given an invalid value
  When  it is submitted
  Then  get_by_test_id('filter-error') is visible
```

## Acceptance Criteria

- [ ] date range filter
- [ ] filter error shown
- [ ] `poe lint` and `poe test:unit` pass (and `poe test:e2e`)

## Review amendments (2026-09-28)

- **Deferral candidate** (Owner decision 8). Nothing on the critical path depends on this story, and `-51` is no longer blocked by it.

## Blocked by

- `featviews-typed-whitelisted-filters-in-list-view` (st-v058-byoa-44)

## Parent

- Epic: `epic-v058-bring-your-own-app` (v0.5.8 — Bring Your Own App)
