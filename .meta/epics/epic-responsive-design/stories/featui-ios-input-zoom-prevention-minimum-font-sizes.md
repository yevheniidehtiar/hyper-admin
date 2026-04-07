---
type: story
id: Rsp4_iosz_05
title: "feat(ui): iOS input zoom prevention with minimum font sizes"
status: todo
priority: high
assignee: null
labels:
  - frontend
  - forms
  - size:S
  - planned
  - responsive
  - accessibility
estimate: null
epic_ref: Rsp4_Gamma_01
github:
  issue_number: null
  repo: yevheniidehtiar/hyper-admin
  last_sync_hash: null
  synced_at: null
created_at: 2026-04-07T00:00:00Z
updated_at: 2026-04-07T00:00:00Z
---

## Summary

iOS Safari automatically zooms into form inputs with font-size below 16px. The current `.ha-input` and `.ha-select` use `--ha-font-size-sm` (0.875rem = 14px), causing an unwanted zoom on focus that disorients users and requires manual zoom-out. Fix by setting minimum 16px font-size on all form inputs at mobile breakpoints.

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

- `src/hyperadmin/static/css/_forms.css` -- mobile font-size override for .ha-input, .ha-select, .ha-textarea
- `src/hyperadmin/static/css/_responsive.css` -- ensure 16px minimum at mobile breakpoint

## Implementation notes

- Add to mobile base styles (below md breakpoint): `.ha-input, .ha-select, .ha-textarea { font-size: var(--ha-font-size-base); }` (1rem = 16px)
- At md breakpoint, revert to `font-size: var(--ha-font-size-sm);`
- This is a well-known iOS issue, no meta viewport manipulation needed

## Agent

- **Size:** S
- **Tier:** Sonnet
- **blocked_by:** #452
