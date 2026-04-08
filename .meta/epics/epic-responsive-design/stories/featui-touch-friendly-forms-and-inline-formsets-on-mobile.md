---
type: story
id: I0BwE7nn-Qpf
title: "feat(ui): touch-friendly forms and inline formsets on mobile"
status: todo
priority: high
assignee: null
labels:
  - frontend
  - forms
  - size:M
  - planned
  - responsive
  - cycle:2
estimate: null
epic_ref:
  id: RspSynth_01
github:
  issue_number: 467
  repo: yevheniidehtiar/hyper-admin
  last_sync_hash: sha256:ed79c18002e36c1d26384c7204fcedb8620c56047a3cc0a8801ddc1ac153e92f
  synced_at: 2026-04-07T17:23:23.791Z
created_at: 2026-04-01T21:45:33Z
updated_at: 2026-04-01T21:45:33Z
---

## Summary

Ensure forms, fieldsets, and inline formsets are fully usable on mobile. Inputs have adequate touch target sizes, form grids collapse to single column, inline formset tables stack on mobile.

## Scenarios

**Scenario: form inputs have adequate padding on mobile**
  Given viewport width is 375px and a coarse pointer device
  When  a create/update form loads
  Then  all inputs, selects, and textareas have at least 44px height
  And   padding is increased for finger-friendly tapping

**Scenario: two-column form grid collapses to single column on mobile**
  Given viewport width is 375px
  When  a form with ha-form-grid-2 layout loads
  Then  the grid displays as a single column

**Scenario: fieldset toggle is touch-friendly on mobile**
  Given viewport width is 375px and a coarse pointer
  When  a form with collapsible fieldsets loads
  Then  the fieldset toggle button has at least 44px height

**Scenario: inline formset stacks on mobile**
  Given viewport width is 375px
  When  a form with inline formsets loads
  Then  each inline row displays as a stacked card instead of a table row
  And   the Remove button has adequate touch target size

## Acceptance criteria

- [ ] Form inputs have at least 44px height on coarse pointer devices
- [ ] Form inputs have font-size >= 16px on mobile (prevents iOS auto-zoom)
- [ ] Form grid collapses to single column on mobile
- [ ] Fieldset toggles are touch-friendly
- [ ] Inline formsets stack as cards on mobile

## Files to modify

- `src/hyperadmin/static/css/_forms.css` — adjust input padding for mobile
- `src/hyperadmin/static/css/_fieldsets.css` — mobile grid collapse
- `src/hyperadmin/static/css/_inlines.css` — mobile card layout for inline rows
- `src/hyperadmin/static/css/_accessibility.css` — add `.ha-fieldset-toggle`, `.ha-input`, `.ha-select` to coarse pointer rule
- `src/hyperadmin/static/css/_responsive.css` — form-specific mobile overrides
- `src/hyperadmin/templates/components/inline_formset.html` — add `data-label` attributes for card mode

## Implementation notes

- Increase input padding on mobile from `var(--ha-space-2) var(--ha-space-3)` to `var(--ha-space-3) var(--ha-space-3)` for 44px targets
- `ha-form-grid-2` defaults to `grid-template-columns: 1fr`, expands to `1fr 1fr` at md breakpoint
- Inline formsets use same `data-label` + CSS card technique as table (Issue #461)

## Agent

- **Size:** M
- **Tier:** Sonnet
- **blocked_by:** C1-B (mobile-first base layout)

## Demo checkpoint

Open a create form at 375px viewport:
1. Verify form grid is single-column
2. Verify all inputs have at least 44px height (use DevTools to measure)
3. If inline formsets exist, verify they display as stacked cards
4. Widen to 768px -- form grid becomes two-column
