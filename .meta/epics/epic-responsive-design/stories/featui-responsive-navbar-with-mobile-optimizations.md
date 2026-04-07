---
type: story
id: TAhnnvjjZxyA
title: "feat(ui): responsive navbar with mobile optimizations"
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
  issue_number: 465
  repo: yevheniidehtiar/hyper-admin
  last_sync_hash: sha256:34e05b315ee970b1d39cb9189b86f6893ac7beb77fbb412b9ae341958cd1863d
  synced_at: 2026-04-07T17:23:23.791Z
created_at: 2026-04-01T21:45:17Z
updated_at: 2026-04-01T21:45:17Z
---

## Summary

Optimize the navbar for mobile viewports. Reduced padding, brand and actions remain accessible without overflow, touch targets verified.

## Scenarios

**Scenario: navbar adjusts spacing on mobile**
  Given viewport width is 375px
  When  the page loads
  Then  the navbar uses reduced horizontal padding
  And   the brand, theme toggle, and user menu are visible without overflow

**Scenario: navbar actions remain accessible on small screens**
  Given viewport width is 320px
  When  the page loads
  Then  the theme toggle button is visible and tappable
  And   the user dropdown button is visible and tappable
  And   both have minimum 44px touch targets

**Scenario: navbar buttons have accessible names for screen readers**
  Given viewport width is 375px and a screen reader is active
  When  the page loads
  Then  the hamburger button has aria-label="Open navigation"
  And   the theme toggle button has aria-label="Toggle dark mode"
  And   the user dropdown button has an accessible name

## Acceptance criteria

- [ ] Navbar uses reduced padding on mobile
- [ ] Brand, theme toggle, and user dropdown remain visible and accessible on 320px
- [ ] All navbar buttons have accessible names for screen readers

## Files to modify

- `src/hyperadmin/static/css/_navbar.css`
- `src/hyperadmin/static/css/_responsive.css`
- `src/hyperadmin/static/css/_accessibility.css` — add `.ha-theme-toggle` to coarse pointer touch target rule

## Agent

- **Size:** S
- **Tier:** Sonnet
- **blocked_by:** #458
