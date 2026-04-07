---
type: story
id: 8P_VPRTVAWHF
title: "feat(ui): collapsible sidebar with hamburger menu toggle"
status: todo
priority: medium
assignee: null
labels:
  - frontend
  - ui
  - size:M
  - planned
  - responsive
  - wave:2
estimate: null
epic_ref:
  id: cvr4sYoEN9CV
github:
  issue_number: 458
  repo: yevheniidehtiar/hyper-admin
  last_sync_hash: sha256:478c9cd03698d8d06d7670423440d407f2e975fd99c172a4ded76a633fdae021
  synced_at: 2026-04-07T17:23:23.791Z
created_at: 2026-04-01T21:44:15Z
updated_at: 2026-04-01T21:44:15Z
---

## Summary

Replace the "hidden on mobile" sidebar with a slide-in overlay triggered by a hamburger button in the navbar. Use Alpine.js for toggle state. Add backdrop overlay. Close on navigation, escape key, and backdrop click.

## Scenarios

**Scenario: hamburger button visible on mobile**
  Given viewport width is 375px
  When  the admin page loads
  Then  a hamburger menu button is visible in the navbar
  And   the sidebar is hidden

**Scenario: tapping hamburger opens sidebar as overlay**
  Given viewport width is 375px and the page is loaded
  When  the user taps the hamburger button
  Then  the sidebar slides in from the left as an overlay
  And   a semi-transparent backdrop appears behind it

**Scenario: tapping backdrop closes sidebar**
  Given the sidebar overlay is open on mobile
  When  the user taps the backdrop
  Then  the sidebar slides out and the backdrop disappears

**Scenario: pressing Escape closes sidebar**
  Given the sidebar overlay is open on mobile
  When  the user presses the Escape key
  Then  the sidebar closes

**Scenario: hamburger is hidden on desktop**
  Given viewport width is 1024px
  When  the page loads
  Then  the hamburger button is not visible
  And   the sidebar is displayed inline as normal

## Acceptance criteria

- [ ] Hamburger button visible on mobile, hidden on desktop
- [ ] Tapping hamburger opens sidebar as slide-in overlay
- [ ] Tapping backdrop closes sidebar
- [ ] Escape key closes sidebar
- [ ] Hamburger hidden on desktop, sidebar inline

## Files to modify

- `src/hyperadmin/templates/_navbar.html` — add hamburger button (`data-testid="sidebar-toggle"`)
- `src/hyperadmin/templates/_sidebar.html` — Alpine.js open/close state, backdrop div
- `src/hyperadmin/templates/_base.html` — shared `x-data="{ sidebarOpen: false }"` on body wrapper
- `src/hyperadmin/static/css/_sidebar.css` — mobile overlay styles (position fixed, transform, transition)
- `src/hyperadmin/static/css/_navbar.css` — hamburger button styles
- `src/hyperadmin/static/css/_responsive.css` — sidebar overlay breakpoint rules

## Implementation notes

- Use Alpine.js `x-data="{ sidebarOpen: false }"` on parent element in `_base.html`
- Sidebar mobile: `position: fixed; transform: translateX(-100%); transition: transform`
- When open: `transform: translateX(0)`
- Backdrop: `position: fixed; inset: 0; background: rgba(0,0,0,0.5); z-index: 39`
- Sidebar z-index: 40 (above backdrop at 39, above navbar at 30)
- At `min-width: 1024px`, hamburger hides and sidebar reverts to inline flow

## Demo checkpoint

Open any admin page at 375px viewport width:
1. Verify sidebar is hidden and hamburger icon visible in navbar
2. Tap hamburger -- sidebar slides in from left with dark backdrop
3. Tap backdrop or press Escape -- sidebar slides out
4. Widen to 1024px -- hamburger disappears, sidebar shows inline

## Agent

- **Size:** M
- **Tier:** Sonnet
- **blocked_by:** W1-B (v8xvLKJfP_46)
