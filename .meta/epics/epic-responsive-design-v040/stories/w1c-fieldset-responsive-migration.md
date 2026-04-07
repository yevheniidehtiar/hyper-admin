---
type: story
id: sRu4NeCGtawc
title: "refactor(ui): migrate fieldset media query to responsive layer"
status: todo
priority: medium
assignee: null
labels:
  - frontend
  - css
  - size:S
  - responsive
  - wave:1
estimate: null
epic_ref:
  id: cvr4sYoEN9CV
github:
  issue_number: null
  repo: yevheniidehtiar/hyper-admin
  last_sync_hash: null
  synced_at: null
created_at: 2026-04-07T00:00:00Z
updated_at: 2026-04-07T00:00:00Z
---

## Summary

Move the existing `@media (max-width: 768px)` query in `_fieldsets.css` to the centralized
`_responsive.css` file. Convert it to mobile-first (min-width) pattern. No visual change.

Split from #452 (W1-C). Can run in parallel with W1-A and W1-B since it touches only
`_fieldsets.css` (removing media query) — no file overlap.

## Scenarios

**Scenario: fieldset grid collapses on mobile**
  Given viewport width is 375px
  When  a form with ha-form-grid-2 loads
  Then  the grid displays as single column

**Scenario: fieldset grid expands on tablet**
  Given viewport width is 768px
  When  a form with ha-form-grid-2 loads
  Then  the grid displays as two columns

## Acceptance criteria

- [ ] Media query removed from `_fieldsets.css`
- [ ] Equivalent mobile-first rule added to `_responsive.css`
- [ ] No visual change at any viewport

## Files to modify

- `src/hyperadmin/static/css/_fieldsets.css` — remove `@media (max-width: 768px)` block
- `src/hyperadmin/static/css/_responsive.css` — add fieldset grid rule under `@media (min-width: 768px)`

## Implementation notes

- Current `_fieldsets.css` has a `@media (max-width: 768px)` rule for grid collapse
- Mobile-first approach: make single-column the default, add two-column at `min-width: 768px`
- W1-C can merge before W1-B since it only appends to `_responsive.css`

## Demo checkpoint

Open create/update form at 375px — single column. Widen to 768px — two columns.

## Agent

- **Size:** S
- **Tier:** Sonnet
- **blocked_by:** none
