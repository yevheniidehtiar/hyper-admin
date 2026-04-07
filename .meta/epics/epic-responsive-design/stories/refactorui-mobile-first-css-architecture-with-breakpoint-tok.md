---
type: story
id: evYLLYeqOdOC
title: "refactor(ui): mobile-first CSS architecture with breakpoint tokens"
status: todo
priority: high
assignee: null
labels:
  - frontend
  - size:L
  - planned
  - responsive
  - css
estimate: null
epic_ref: Rsp4_Gamma_01
github:
  issue_number: 452
  repo: yevheniidehtiar/hyper-admin
  last_sync_hash: sha256:f75948d7d156f89d03393fd41871e8b2e4220391870e36bebc6c7c296d4bb98e
  synced_at: 2026-04-07T17:23:23.791Z
created_at: 2026-04-01T21:43:05Z
updated_at: 2026-04-01T21:43:05Z
---

## Summary

Restructure the CSS from desktop-first to mobile-first. Add breakpoint custom properties as design tokens. Rewrite `_responsive.css` from 24 lines to a proper mobile-first responsive foundation. Ensure all existing desktop layouts remain unchanged (non-breaking refactor).

**Spec:** `docs/specs/responsive-design.md`

## Scenarios

**Scenario: breakpoint tokens are defined as design tokens**
  Given the HyperAdmin CSS loads
  When  inspecting :root custom properties
  Then  --ha-bp-sm (640px), --ha-bp-md (768px), --ha-bp-lg (1024px), --ha-bp-xl (1280px) are defined

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

**Scenario: mobile typography is scaled for small screens**
  Given viewport width is 375px
  When  a list view page loads
  Then  page headings use --ha-font-size-xl instead of --ha-font-size-2xl
  And   word-break: break-word prevents horizontal overflow from long strings

**Scenario: no desktop visual regression**
  Given the page loads at 1280x720
  When  comparing to current layout
  Then  all spacing, colors, typography identical

## Acceptance criteria

- [ ] Breakpoint tokens defined in `_tokens.css`
- [ ] Mobile-first base styles apply without media queries
- [ ] Tablet breakpoint restores two-column layout
- [ ] Desktop breakpoint restores full sidebar
- [ ] XL breakpoint caps container width
- [ ] Mobile typography scaled for small screens (headings, word-break)
- [ ] No visual regression at 1280x720

## Files to modify

- `src/hyperadmin/static/css/_tokens.css` — add breakpoint tokens, `--ha-sidebar-width-tablet`
- `src/hyperadmin/static/css/_responsive.css` — complete rewrite: mobile-first with `min-width` queries
- `src/hyperadmin/static/css/_layout.css` — start single-column, add flex at md
- `src/hyperadmin/static/css/_sidebar.css` — default `display: none`, show at md
- `src/hyperadmin/static/css/_fieldsets.css` — move existing 768px query to responsive layer

## Implementation notes

- All responsive overrides centralized in `_responsive.css` (leveraging `@layer responsive` highest specificity)
- Base (no-media-query) styles must be mobile styles
- `@media (min-width: 768px)` and `@media (min-width: 1024px)` progressively enhance
- Move the existing `@media (max-width: 768px)` in `_fieldsets.css` to `_responsive.css`

## Agent

- **Size:** L
- **Tier:** Opus
- **blocked_by:** #447
