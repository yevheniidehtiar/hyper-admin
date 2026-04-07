---
type: story
id: Rsp4_skip_01
title: "feat(ui): skip-to-content and landmark enhancements for mobile"
status: todo
priority: high
assignee: null
labels:
  - frontend
  - accessibility
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

Enhance the existing skip-to-content link and ARIA landmarks for mobile navigation. On mobile, the sidebar overlay means users need a way to skip past it quickly. Ensure all landmarks (nav, main, complementary) are properly labeled so screen reader users can jump between them.

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

## Files to modify

- `src/hyperadmin/templates/_base.html` -- verify landmark roles
- `src/hyperadmin/templates/_sidebar.html` -- add aria-label="Model navigation"
- `src/hyperadmin/templates/_navbar.html` -- ensure wrapped in <header> or role="banner"
- `src/hyperadmin/static/css/_accessibility.css` -- mobile skip-link adjustments

## Agent

- **Size:** S
- **Tier:** Sonnet
- **blocked_by:** #452
