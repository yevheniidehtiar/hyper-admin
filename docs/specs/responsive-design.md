# SDD: Responsive Design Overhaul

| Field | Value |
|---|---|
| Author | Claude Code |
| Status | Draft |
| Issue | Epic 4.3 (v0.4.0) |
| Milestone | v0.4.0 — Responsive Design |
| Created | 2026-04-01 |
| Last updated | 2026-04-01 |

---

## Problem

HyperAdmin's current CSS is desktop-first with only 24 lines of responsive code. On mobile:
- The sidebar is completely hidden with no alternative navigation
- Tables overflow horizontally without a mobile-friendly layout
- Pagination and filters are not optimized for touch
- Form inputs lack adequate touch targets

This makes HyperAdmin unusable on mobile devices, which is increasingly unacceptable for admin interfaces that operators access from phones and tablets.

## Goals

- Mobile-first CSS architecture with standardized breakpoints (sm/md/lg/xl)
- Collapsible sidebar with hamburger menu on mobile (Alpine.js)
- Stacked card layout for data tables below 768px
- Touch-friendly forms, pagination, and filters on mobile
- No visual regression on desktop (1280px+)
- Comprehensive E2E tests for responsive behaviors

## Non-Goals

- Swipe gesture support (deferred — complexity vs. marginal benefit)
- PWA/offline support
- Native mobile app
- CSS framework adoption (remain framework-independent)
- i18n or RTL support (moved to v0.4.1)

## BDD Scenarios

See individual issue scenarios in the plan. Key scenarios:

```
Scenario: mobile base styles apply without media queries
  Given viewport width is 320px
  When  the page loads
  Then  layout is single-column, sidebar hidden, content full-width

Scenario: hamburger opens sidebar overlay on mobile
  Given viewport 375px, page loaded
  When  user taps hamburger button
  Then  sidebar slides in from left as overlay with backdrop

Scenario: table displays as stacked cards on mobile
  Given viewport 375px, list view with data
  When  inspecting table
  Then  each row renders as a card with label-value pairs

Scenario: desktop layout unchanged
  Given viewport 1280x720
  When  page loads
  Then  sidebar inline at 16rem, table horizontal, all spacing identical to current
```

## Design

### Architecture

**Affected modules:** Only `static/css/` and `templates/` — no Python module changes.

**CSS Layer Strategy:** All responsive overrides centralized in `_responsive.css` within the existing `@layer responsive` (highest specificity in the cascade). Component CSS files (`_sidebar.css`, `_table.css`, etc.) define base mobile styles; `_responsive.css` progressively enhances at each breakpoint.

**Breakpoint Tokens** (added to `_tokens.css`):

| Token | Value | Purpose |
|---|---|---|
| `--ha-bp-sm` | `640px` | Large phones landscape |
| `--ha-bp-md` | `768px` | Tablets, sidebar appears |
| `--ha-bp-lg` | `1024px` | Desktop, full sidebar |
| `--ha-bp-xl` | `1280px` | Large desktop, max-width cap |

Note: CSS custom properties cannot be used in `@media` queries directly. The tokens serve as documentation and are referenced by value in media queries.

**Mobile-First Rewrite Strategy:**

```css
/* Base styles = mobile (no media query) */
.ha-sidebar { display: none; }
.ha-layout { display: block; }

/* Tablet: sidebar appears, two-column */
@media (min-width: 768px) {
  .ha-sidebar { display: block; }
  .ha-layout { display: flex; }
}

/* Desktop: full sidebar width */
@media (min-width: 1024px) {
  :root { --ha-sidebar-width: 16rem; }
}
```

### Sidebar Toggle (Alpine.js)

```html
<!-- _base.html: shared state -->
<div x-data="{ sidebarOpen: false }">
  <!-- _navbar.html: hamburger button (visible < 1024px) -->
  <button @click="sidebarOpen = !sidebarOpen" data-testid="sidebar-toggle">
    <!-- hamburger icon -->
  </button>

  <!-- _sidebar.html: overlay on mobile -->
  <div class="ha-sidebar-backdrop" x-show="sidebarOpen" @click="sidebarOpen = false"></div>
  <aside class="ha-sidebar" :class="{ 'ha-sidebar--open': sidebarOpen }"
         @keydown.escape.window="sidebarOpen = false">
    <!-- nav items -->
  </aside>
</div>
```

### Table Card Layout

At mobile (`< 768px`), tables transform to stacked cards using CSS:

```css
/* Mobile card layout */
.ha-table thead { position: absolute; clip: rect(0,0,0,0); }
.ha-table tr { display: block; margin-bottom: var(--ha-space-4); }
.ha-table td { display: flex; justify-content: space-between; }
.ha-table td::before { content: attr(data-label); font-weight: 600; }
```

Template change: add `data-label="{{ column_name }}"` to each `<td>`.

### Data Model Changes

No data model changes.

### API / Protocol Changes

No API changes.

### Configuration Changes

No configuration changes.

## Edge Cases & Error Handling

| Edge Case | Handling |
|---|---|
| Very long model names in sidebar | `text-overflow: ellipsis; overflow: hidden` |
| Many columns in table card | Cards may be tall; acceptable for mobile |
| Inline formsets on mobile | Stack as cards using same `data-label` technique |
| Browser back-swipe conflict | No swipe gestures implemented (non-goal) |
| Print styles | Not addressed (non-goal for v0.4.0) |
| Very narrow viewport (< 320px) | Graceful degradation via fluid widths |

## Migration & Backward Compatibility

Backward compatible — no migration required. All changes are CSS and template only. No Python API changes. Custom templates extending HyperAdmin base templates will automatically inherit responsive behavior.

Users with custom CSS targeting `.ha-*` classes may need to verify their styles at mobile breakpoints.

## Open Questions

None — all design decisions resolved.

## Decision Log

| Decision | Rationale | Alternatives considered |
|---|---|---|
| Centralize responsive in `_responsive.css` | `@layer responsive` gives highest specificity; easier to audit | Embed queries in each component file — rejected (harder to audit, inconsistent) |
| Alpine.js for sidebar toggle | Already in stack, no new deps | CSS-only `:target` — rejected (URL hash pollution, no escape key) |
| Exclude swipe gestures | Complexity vs. benefit (browser conflicts, scroll interference) | Include swipe — deferred to future polish |
| CSS custom property tokens for breakpoints | Documentation + consistency | Sass variables — rejected (no preprocessor in stack) |
| `data-label` for card layout | Standard CSS technique, no JS needed | JS-based label injection — rejected (unnecessary complexity) |
