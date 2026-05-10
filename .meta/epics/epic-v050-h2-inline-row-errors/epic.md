---
type: epic
id: ep-v050-h2-01
title: "fix(inlines): per-row error highlighting in nested formsets"
status: todo
priority: medium
owner: null
labels:
  - size:S
  - planned
  - frontend
  - upstream-readiness
  - H2
milestone_ref:
  id: 1U5Neu25VVR2
created_at: 2026-05-10T00:00:00Z
updated_at: 2026-05-10T00:00:00Z
---

## Overview

Closing gap on upstream readiness **H2** (inline / nested forms — shipped in
v0.5.0). The current `inline_row.html` template renders per-field `aria-invalid`
and a `<ul class="ha-field-errors">` list, but a failing row is not visually
distinguished at the row level — operators scanning a long formset can miss the
failure. The H2 qualification check requires the failing row to be highlighted
in place.

Bugfix-sized; no SDD required per `sdd-conventions.md`. BDD scenarios in the
single story.

## Tracks

### Track A: Template + style
- `inline_row.html` gains a row-level `aria-invalid` and a `ha-inline-row-error` class when any field on the row has errors.
- `data-testid="inline-{prefix}-row-{index}-error"` exposed when the row is in error state, to let E2E assert the highlight without inspecting CSS.

## Scenarios

```
Scenario: nested formset save with one failing child highlights that row
  Given a parent + 3 inline children, child index 1 missing a required field
  When  the parent form is submitted
  Then  the response re-renders the formset
  And   the inline row at index 1 has data-testid="inline-children-row-1-error"
  And   the row has aria-invalid="true" at the row level
  And   the other two rows have no error testid

Scenario: all-valid submission renders no row-level error marker
  Given a parent + 3 inline children, all valid
  When  the form is submitted and the page re-renders for any reason
  Then  no inline row carries the row-level error testid
```

## Acceptance Criteria

- [ ] Row-level `aria-invalid="true"` on `<tr>` when any field on the row has errors
- [ ] `data-testid="inline-{prefix}-row-{index}-error"` exposed when the row is in error
- [ ] `ha-inline-row-error` class for styling (no change to E2E selector convention)
- [ ] CSS rule giving the row a visible accent (border-left or background)
- [ ] Two E2E scenarios added to existing nested-formset test file
- [ ] Visual snapshot refreshed
- [ ] `poe lint` and `poe test:e2e -k inline` pass

## Parent

- Milestone: v0.5.0 (follow-up patch)
- Tracking: `epic-upstream-readiness` (H2)
