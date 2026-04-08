---
type: story
id: RspSyn_C2F_01
title: "feat(ui): skip-to-content and landmark enhancements for mobile"
status: todo
priority: high
assignee: null
labels:
  - frontend
  - accessibility
  - size:S
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

Enhance the existing skip-to-content link and ARIA landmarks for mobile navigation. On
mobile, the sidebar overlay means users need a way to skip past it quickly. Ensure all
landmarks (nav, main, complementary) are properly labeled so screen reader users can jump
between them.

Cherry-picked from Gamma PPU experiment.

## Scenarios

**Scenario: skip-to-content link bypasses sidebar overlay on mobile**
  Given viewport width is 375px and the sidebar overlay is open
  When  a keyboard user activates the skip-to-content link
  Then  focus moves to the main content area
  And   the sidebar overlay closes

**Scenario: landmarks are labeled for screen reader navigation**
  Given any viewport width and a screen reader
  When  the page loads
  Then  the navbar has role="banner" or is a <header> element
  And   the sidebar has role="complementary" with aria-label="Model navigation"
  And   the main content has role="main"
  And   screen reader users can jump between landmarks using shortcut keys

## Acceptance criteria

- [ ] Skip-to-content link bypasses sidebar and closes overlay on mobile
- [ ] All major page regions have appropriate ARIA landmarks and labels
- [ ] Skip link is visually hidden but accessible via keyboard Tab

## Files to modify

- `src/hyperadmin/templates/_base.html` -- add/enhance skip-to-content link
- `src/hyperadmin/templates/_sidebar.html` -- add `role="complementary"` and `aria-label`
- `src/hyperadmin/static/css/_accessibility.css` -- skip link styles (visible on focus)

## Implementation notes

- Skip link: `<a href="#main-content" class="ha-skip-link">Skip to content</a>`
- CSS: `.ha-skip-link { position: absolute; left: -9999px; } .ha-skip-link:focus { left: 0; }`
- On activation, dispatch Alpine event to close sidebar if open
- Landmarks: `<header>` for navbar, `<aside aria-label="Model navigation">` for sidebar, `<main id="main-content">` for content

## Demo checkpoint

1. Open admin at 375px, press Tab -- skip link appears
2. Press Enter on skip link -- focus moves to main content, sidebar closes if open
3. Open VoiceOver/NVDA -- landmarks are navigable

## Agent

- **Size:** S
- **Tier:** Sonnet
- **blocked_by:** C1-B (mobile-first base layout)
