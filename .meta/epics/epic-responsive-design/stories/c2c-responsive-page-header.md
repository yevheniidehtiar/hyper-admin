---
type: story
id: RspSyn_C2C_01
title: "feat(ui): responsive page header and action bar"
status: todo
priority: high
assignee: null
labels:
  - frontend
  - ui
  - size:M
  - responsive
  - cycle:2
estimate: null
epic_ref:
  id: RspSynth_01
github:
  issue_number: null
  repo: yevheniidehtiar/hyper-admin
  last_sync_hash: null
  synced_at: null
created_at: 2026-04-08T00:00:00Z
updated_at: 2026-04-08T00:00:00Z
---

## Summary

The page header (model name + "Create New" button, or detail heading + Edit/Delete buttons)
overflows on narrow mobile screens. The heading and action buttons sit in a single row that
does not wrap, causing horizontal overflow on 320px screens. Restructure the page header to
stack vertically on mobile: heading on top, action buttons full-width below.

Cherry-picked from Gamma PPU experiment.

## Scenarios

**Scenario: page header stacks on mobile**
  Given viewport width is 375px
  When  a list view loads
  Then  the page heading and "Create New" button stack vertically
  And   the "Create New" button is full-width with 44px touch target

**Scenario: detail page header wraps action buttons on mobile**
  Given viewport width is 375px
  When  a detail view loads
  Then  the heading is on one line
  And   Edit, Delete, and Back buttons wrap into a row below the heading
  And   each button has minimum 44px height

**Scenario: page header is inline on desktop**
  Given viewport width is 1024px
  When  a list view loads
  Then  the heading and "Create New" button sit side-by-side

## Acceptance criteria

- [ ] Page header stacks vertically on mobile with full-width action button
- [ ] Detail page header wraps action buttons below heading on mobile
- [ ] Desktop layout unchanged (inline heading + actions)
- [ ] All action buttons have 44px minimum touch target on mobile

## Files to modify

- `src/hyperadmin/static/css/_content.css` or `_layout.css` -- page header responsive rules
- `src/hyperadmin/static/css/_buttons.css` -- full-width action button on mobile

## Implementation notes

- Page header container: `flex-direction: column; gap: var(--ha-space-3);` at mobile
- At `@media (min-width: 768px)`: `flex-direction: row; justify-content: space-between;`
- "Create New" button: `width: 100%;` at mobile, `width: auto;` at desktop
- Action buttons container: `flex-wrap: wrap; gap: var(--ha-space-2);` at mobile

## Demo checkpoint

Open list view at 375px:
1. Heading and "Create New" stacked vertically
2. "Create New" button spans full width
3. Widen to 1024px -- heading and button sit side-by-side

## Agent

- **Size:** M
- **Tier:** Sonnet
- **blocked_by:** C1-B (mobile-first base layout)
