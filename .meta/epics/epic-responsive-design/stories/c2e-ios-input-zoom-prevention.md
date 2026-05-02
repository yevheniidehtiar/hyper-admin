---
type: story
id: RspSyn_C2E_01
title: "feat(ui): iOS input zoom prevention with minimum font sizes"
status: done
priority: high
assignee: null
labels:
  - frontend
  - forms
  - size:S
  - responsive
  - accessibility
  - cycle:2
estimate: null
epic_ref:
  id: RspSynth_01
github: null
created_at: 2026-04-08T00:00:00Z
updated_at: 2026-04-08T00:00:00Z
---

## Summary

iOS Safari automatically zooms into form inputs with font-size below 16px. The current
`.ha-input` and `.ha-select` use `--ha-font-size-sm` (0.875rem = 14px), causing an unwanted
zoom on focus that disorients users and requires manual zoom-out. Fix by setting minimum
16px font-size on all form inputs at mobile breakpoints.

Cherry-picked from Gamma PPU experiment.

## Scenarios

**Scenario: tapping input does not trigger iOS zoom**
  Given viewport width is 375px on iOS Safari
  When  the user taps a text input on a create/edit form
  Then  the input receives focus without the page zooming in
  And   the viewport scale remains at 1.0

**Scenario: select dropdowns do not trigger iOS zoom**
  Given viewport width is 375px on iOS Safari
  When  the user taps a select dropdown
  Then  the native picker opens without the page zooming in

## Acceptance criteria

- [ ] All form inputs (input, select, textarea) have font-size >= 16px on mobile
- [ ] No iOS auto-zoom when focusing any form field
- [ ] Desktop font sizes remain at --ha-font-size-sm (no change above 768px)

## Files to modify

- `src/hyperadmin/static/css/_forms.css` -- add mobile font-size override for inputs
- `src/hyperadmin/static/css/_responsive.css` -- optional, if using centralized mobile rules

## Implementation notes

- At mobile breakpoint (base styles, no media query): `input, select, textarea { font-size: 1rem; }` (16px)
- At `@media (min-width: 768px)`: revert to `font-size: var(--ha-font-size-sm);`
- This is a one-line fix per element type but prevents a major iOS UX annoyance

## Demo checkpoint

Open a create form on iOS Safari (or Chrome DevTools iOS emulation):
1. Tap a text input -- no zoom
2. Tap a select dropdown -- no zoom
3. Verify desktop font sizes unchanged

## Agent

- **Size:** S
- **Tier:** Sonnet
- **blocked_by:** C1-B (mobile-first base layout)
