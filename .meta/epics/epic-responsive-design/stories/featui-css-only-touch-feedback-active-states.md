---
type: story
id: Rsp4_tch_f_02
title: "feat(ui): CSS-only touch feedback active states"
status: todo
priority: medium
assignee: null
labels:
  - frontend
  - ui
  - size:S
  - planned
  - responsive
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

Add CSS `:active` state feedback for all interactive elements on touch devices. On mobile, users need visual confirmation when they tap a button, link, or table row. Currently, taps produce no visual feedback, making the app feel unresponsive. Use pure CSS -- no JavaScript or new dependencies.

## Scenarios

**Scenario: buttons show active state on tap**
  Given viewport width is 375px and a coarse pointer device
  When  the user taps a .ha-btn button
  Then  the button shows a visible pressed state (darker background, slight scale)
  And   the state reverts when the finger is lifted

**Scenario: table row cards show active feedback on tap**
  Given viewport width is 375px and the list view shows card layout
  When  the user taps a card row
  Then  the card shows a subtle highlight or shadow change
  And   the feedback is instant (no animation delay)

## Acceptance criteria

- [ ] All .ha-btn, .ha-action-link, .ha-action-delete show :active feedback on touch
- [ ] Table card rows show :active feedback on mobile
- [ ] Sidebar links show :active feedback on mobile
- [ ] No :active styles fire when prefers-reduced-motion is set

## Files to modify

- `src/hyperadmin/static/css/_buttons.css` -- add :active states
- `src/hyperadmin/static/css/_table.css` -- card row :active state
- `src/hyperadmin/static/css/_sidebar.css` -- sidebar link :active state
- `src/hyperadmin/static/css/_responsive.css` -- touch-specific :active rules

## Implementation notes

- Use `@media (pointer: coarse)` to scope :active styles to touch devices
- Button :active: `transform: scale(0.97); background-color: var(--ha-color-primary-hover);`
- Card :active: `background-color: var(--ha-color-primary-50); box-shadow: var(--ha-shadow-xs);`
- Wrap in `@media (prefers-reduced-motion: no-preference)` for transform
- Add `-webkit-tap-highlight-color: transparent;` to prevent default mobile highlight

## Agent

- **Size:** S
- **Tier:** Sonnet
- **blocked_by:** #452
