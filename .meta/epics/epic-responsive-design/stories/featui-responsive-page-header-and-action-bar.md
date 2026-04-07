---
type: story
id: Z2W5LQzXJIJw
title: "feat(ui): responsive page header and action bar"
status: todo
priority: high
assignee: null
labels:
  - frontend
  - ui
  - size:M
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

The page header (model name + "Create New" button, or detail heading + Edit/Delete buttons) overflows on narrow mobile screens. The heading and action buttons sit in a single row that does not wrap, causing horizontal overflow on 320px screens. Restructure the page header to stack vertically on mobile: heading on top, action buttons full-width below.

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

- [ ] Page header stacks vertically on mobile (heading above, actions below)
- [ ] Actions are full-width or wrapping on mobile
- [ ] Desktop layout unchanged (heading and actions side-by-side)
- [ ] Action buttons meet 44px touch target on mobile

## Files to modify

- `src/hyperadmin/static/css/_page-header.css` -- mobile stacking styles
- `src/hyperadmin/static/css/_responsive.css` -- page header mobile rules

## Implementation notes

- `.ha-page-header { flex-direction: column; align-items: stretch; }` at mobile
- `.ha-page-header-actions { display: flex; gap: var(--ha-space-2); flex-wrap: wrap; }` at mobile
- At md breakpoint: `flex-direction: row; justify-content: space-between; align-items: center;`
- The "Create New" button should use `width: 100%` on mobile for easy tapping

## Agent

- **Size:** M
- **Tier:** Sonnet
- **blocked_by:** #452
