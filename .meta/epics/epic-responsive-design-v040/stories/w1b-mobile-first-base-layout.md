---
type: story
id: v8xvLKJfP_46
title: "refactor(ui): mobile-first base layout rewrite"
status: todo
priority: high
assignee: null
labels:
  - frontend
  - css
  - size:M
  - responsive
  - wave:1
estimate: null
epic_ref:
  id: cvr4sYoEN9CV
github:
  issue_number: null
  repo: yevheniidehtiar/hyper-admin
  last_sync_hash: null
  synced_at: null
created_at: 2026-04-07T00:00:00Z
updated_at: 2026-04-07T00:00:00Z
---

## Summary

Rewrite `_responsive.css` from desktop-first (max-width) to mobile-first (min-width).
Adjust `_layout.css` to default single-column and `_sidebar.css` to default hidden.
Desktop must remain visually identical (non-breaking refactor).

Split from #452 (W1-B). Depends on W1-A for breakpoint tokens.

## Scenarios

**Scenario: mobile base styles apply without media queries**
  Given viewport width is 320px
  When  the page loads
  Then  layout is single-column, sidebar hidden, content full-width

**Scenario: tablet breakpoint restores two-column layout**
  Given viewport width is 768px
  When  the page loads
  Then  sidebar visible at 12rem, content fills remaining space

**Scenario: desktop breakpoint restores full sidebar**
  Given viewport width is 1024px
  When  the page loads
  Then  sidebar at 16rem, layout matches current desktop design

**Scenario: xl breakpoint caps container width**
  Given viewport width is 1440px
  When  the page loads
  Then  container max-width 1280px, content centered

**Scenario: no desktop visual regression**
  Given the page loads at 1280x720
  When  comparing to current layout
  Then  all spacing, colors, typography identical

## Acceptance criteria

- [ ] Mobile base styles apply without media queries
- [ ] Tablet breakpoint restores two-column layout
- [ ] Desktop breakpoint restores full sidebar
- [ ] XL breakpoint caps container width
- [ ] No visual regression at 1280x720

## Files to modify

- `src/hyperadmin/static/css/_responsive.css` — complete rewrite: mobile-first with min-width queries
- `src/hyperadmin/static/css/_layout.css` — default single-column, flex at md
- `src/hyperadmin/static/css/_sidebar.css` — default display:none, show at md

## Implementation notes

- Base styles (no media query) = mobile: single column, sidebar hidden
- `@media (min-width: 768px)` = tablet: sidebar 12rem, flex layout
- `@media (min-width: 1024px)` = desktop: sidebar 16rem, full layout
- `@media (min-width: 1280px)` = xl: container max-width
- Use token values from W1-A for breakpoint references in comments

## Demo checkpoint

Resize browser window through 320px -> 768px -> 1024px -> 1440px.
Observe layout transitions. Desktop must look identical to current production.

## Agent

- **Size:** M
- **Tier:** Sonnet
- **blocked_by:** W1-A (dyx7PkkdpBto)
