---
type: story
id: st-v050-h2-01
title: "fix(inlines): row-level error highlighting in nested formsets"
status: todo
priority: medium
assignee: null
labels:
  - size:S
  - planned
  - frontend
  - tests
  - upstream-readiness
  - H2
estimate: null
epic_ref:
  id: ep-v050-h2-01
created_at: 2026-05-10T00:00:00Z
updated_at: 2026-05-10T00:00:00Z
---

## Summary

Apply row-level error markers to `inline_row.html` so operators can spot a
failing child immediately when scanning a long inline formset. Adds a
`data-testid` for the row error state and a CSS class for the visual accent.

## Files to Change

- **Modified:** `src/hyperadmin/templates/components/inline_row.html` — `aria-invalid` and `data-testid` at `<tr>` level, `ha-inline-row-error` class
- **Modified:** `src/hyperadmin/static/css/...` (the relevant existing inline stylesheet) — `.ha-inline-row-error` rule
- **Modified:** `tests/e2e/test_inlines.py` (or the closest existing inline E2E) — two new scenarios
- **Modified:** visual snapshot baseline if affected

## Scenarios

```
Scenario: nested formset save with one failing child highlights that row
  Given a parent + 3 inline children, child index 1 missing a required field
  When  the parent form is submitted
  Then  the inline row at index 1 has data-testid="inline-<prefix>-row-1-error"
  And   the row's aria-invalid is "true"
  And   the other rows have no row-level error testid

Scenario: all-valid submission renders no row-level error marker
  Given a parent + 3 inline children, all valid
  When  the form is submitted and re-renders for any reason
  Then  no inline row carries the row-level error testid
```

## Acceptance Criteria

- [ ] `<tr>` gains `aria-invalid="true"` when any field on the row has errors
- [ ] `<tr>` gains `data-testid="inline-{prefix}-row-{index}-error"` in error state
- [ ] `ha-inline-row-error` class applied for visual accent
- [ ] Existing per-field error testids unchanged (backward compatible)
- [ ] Two E2E scenarios in place with G/W/T comments
- [ ] Visual snapshot refreshed
- [ ] `poe lint` and `poe test:e2e -k inline` pass

## Parent

- Epic: `epic-v050-h2-inline-row-errors`
