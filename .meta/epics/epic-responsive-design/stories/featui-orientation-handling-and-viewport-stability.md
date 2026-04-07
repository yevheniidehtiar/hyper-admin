---
type: story
id: Rsp4_orient03
title: "feat(ui): orientation handling and viewport stability"
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

Handle landscape orientation on mobile devices gracefully. Prevent layout shifts and ensure the admin remains usable when rotating between portrait and landscape. Use `dvh` viewport units where supported to handle mobile browser chrome (address bar) correctly.

## Scenarios

**Scenario: layout adapts when rotating from portrait to landscape**
  Given viewport is 375x812 (portrait, iPhone-like)
  When  the device rotates to landscape (812x375)
  Then  the sidebar overlay closes if it was open
  And   the layout adapts without horizontal overflow
  And   content remains readable and interactive

**Scenario: sidebar overlay uses dynamic viewport height**
  Given viewport width is 375px and the sidebar overlay is open
  When  the mobile browser address bar is visible or hidden
  Then  the sidebar overlay fills the available viewport height correctly
  And   there is no gap at the bottom of the overlay

## Acceptance criteria

- [ ] Layout adapts on orientation change without horizontal overflow
- [ ] Sidebar overlay closes on orientation change
- [ ] Dynamic viewport height (dvh) used for mobile overlays where supported

## Files to modify

- `src/hyperadmin/static/css/_sidebar.css` -- use min-height: 100dvh with 100vh fallback
- `src/hyperadmin/static/css/_layout.css` -- use min-height: 100dvh with fallback
- `src/hyperadmin/static/css/_responsive.css` -- orientation-specific adjustments
- `src/hyperadmin/templates/_sidebar.html` -- close overlay on resize/orientation change

## Implementation notes

- Use `min-height: 100vh; min-height: 100dvh;` (progressive enhancement)
- Alpine.js `@resize.window` to close sidebar on orientation change
- Test on iOS Safari (dynamic toolbar) and Android Chrome

## Agent

- **Size:** S
- **Tier:** Sonnet
- **blocked_by:** #458
