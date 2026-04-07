---
type: story
id: Rsp4_trans07
title: "feat(ui): CSS transitions with reduced-motion respect"
status: todo
priority: low
assignee: null
labels:
  - frontend
  - ui
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

Add smooth CSS transitions for all responsive layout changes: sidebar slide-in/out, card layout appearance, pagination stack transition. All transitions must respect `prefers-reduced-motion`. The existing `_accessibility.css` already disables animations globally for reduced-motion, but this story ensures all new transitions are implemented with that media query in mind.

## Scenarios

**Scenario: sidebar slides in with smooth transition**
  Given viewport width is 375px and prefers-reduced-motion is not set
  When  the user taps the hamburger to open the sidebar
  Then  the sidebar slides in from the left over 250ms
  And   the backdrop fades in simultaneously

**Scenario: transitions are disabled for reduced-motion preference**
  Given the user has prefers-reduced-motion enabled
  When  the user opens the sidebar on mobile
  Then  the sidebar appears instantly without sliding animation
  And   the backdrop appears instantly without fade

## Acceptance criteria

- [ ] Sidebar overlay uses smooth slide + fade transition
- [ ] All transitions respect prefers-reduced-motion (instant appearance)
- [ ] No layout shift during transitions

## Files to modify

- `src/hyperadmin/static/css/_sidebar.css` -- slide transition for overlay
- `src/hyperadmin/static/css/_responsive.css` -- transition timing for layout changes

## Implementation notes

- Sidebar: `transition: transform var(--ha-duration-slow) var(--ha-ease-default);`
- Backdrop: `transition: opacity var(--ha-duration-slow) var(--ha-ease-default);`
- The existing `_accessibility.css` `prefers-reduced-motion` rule already sets `transition-duration: 0.01ms !important` globally, so all new transitions are automatically covered
- No additional reduced-motion handling needed per-component

## Agent

- **Size:** S
- **Tier:** Sonnet
- **blocked_by:** #458
