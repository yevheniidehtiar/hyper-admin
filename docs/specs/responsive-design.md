# SDD: Responsive Design — Mobile-First CSS Overhaul

| Field | Value |
|---|---|
| Author | Claude Code |
| Status | Approved |
| Issue | TBD (epic issue to be created via gitpm push) |
| Milestone | v0.4.0 — Responsive Design |
| Created | 2026-05-03 |
| Last updated | 2026-05-10 (Approved retroactively — milestone shipped) |

---

## Problem

HyperAdmin is desktop-only. Every admin view assumes a minimum 1024px viewport. On
phones (375px) and tablets (768px) the sidebar overlaps content, data tables overflow
horizontally, form inputs are too small to tap, and the navbar collapses onto critical
actions. No WCAG 2.1 AA compliance exists for mobile interactions (focus trap, touch
targets, screen reader support).

This blocks adoption by teams whose users access admin panels on mobile devices and
fails accessibility requirements for any publicly hosted admin.

## Goals

- Every admin view is fully usable at 375px and 768px viewports.
- Mobile-first CSS: base styles target mobile, enhanced with `min-width` media queries.
- WCAG 2.1 AA: touch targets ≥ 44px, focus management, screen reader support,
  `prefers-reduced-motion` respected everywhere animation is used.
- Zero new Python dependencies — pure CSS + Alpine.js (already included) + HTMX
  (already included).
- Every story verifiable in `examples/simple` or `examples/erp`.

## Non-Goals

- HTMX skeleton loading states (deferred to v0.4.1).
- Mobile empty state designs (deferred to v0.4.1).
- CSS touch feedback (:active micro-interactions, deferred to v0.4.1).
- Mobile typography scale polish (deferred to v0.4.1).
- Orientation handling / scroll-to-top after HTMX navigation (deferred to v0.4.1).
- New Python dependencies or changes to the Python public API.
- i18n / RTL layout (milestone v0.4.1).

## BDD Scenarios

Representative scenarios per cycle (full set in individual story files).

```
Scenario: breakpoint tokens are defined as design tokens
  Given the HyperAdmin CSS loads
  When  inspecting :root custom properties
  Then  --ha-bp-sm (640px), --ha-bp-md (768px), --ha-bp-lg (1024px), --ha-bp-xl (1280px) are defined
  And   --ha-sidebar-width-tablet (12rem) is defined

Scenario: desktop layout is preserved at 1280px
  Given the default HyperAdmin CSS loads
  When  viewport is 1280x720
  Then  the sidebar is visible inline and the main content fills the remaining width
  And   no horizontal scrollbar appears

Scenario: hamburger button visible on mobile
  Given viewport width is 375px
  When  the admin page loads
  Then  a hamburger menu button is visible in the navbar
  And   the sidebar is hidden

Scenario: tapping hamburger opens sidebar as overlay with focus trap
  Given viewport width is 375px and the page is loaded
  When  the user taps the hamburger button
  Then  the sidebar slides in as an overlay with role="dialog" and aria-label
  And   focus moves into the sidebar and is trapped there
  And   prefers-reduced-motion: reduce disables the slide animation

Scenario: data table renders as stacked cards on mobile
  Given a list view with 5 rows
  When  the viewport is 375px
  Then  each row is rendered as a card with field labels and values stacked vertically
  And   no horizontal scrollbar appears

Scenario: form inputs are touch-friendly on mobile
  Given a create or update view
  When  the viewport is 375px
  Then  all inputs have a minimum height of 44px
  And   font-size on all inputs is >= 16px (prevents iOS Safari auto-zoom)

Scenario: skip-to-content link is the first focusable element
  Given any admin page
  When  the user presses Tab as the first interaction
  Then  a "Skip to main content" link appears and is focused
  And   activating it moves focus to the main content landmark

Scenario: visual regression baseline captured
  Given the full test suite passes at 375px, 768px, and 1280px
  When  the visual regression baseline story runs
  Then  screenshot snapshots are stored for each breakpoint
  And   future CI runs fail if pixel diff exceeds threshold
```

## Design

### Architecture

CSS/template-only change — no Python modules modified. Affected file targets:

```
src/hyperadmin/static/css/
  _tokens.css        — breakpoint custom properties (C1-A)
  _responsive.css    — mobile-first base rules (C1-B)
  _layout.css        — layout grid at breakpoints (C1-B)
  _sidebar.css       — sidebar collapse + overlay rules (C1-B, C2-A)
  _fieldsets.css     — fieldset responsive adjustments (C1-B)
  _table.css         — stacked-card layout at mobile (C1-C)
  _navbar.css        — hamburger visibility, overflow (C2-A)
  _forms.css         — touch target heights, iOS font-size (C2-B, C2-E)
  _inlines.css       — inline formset mobile layout (C2-B)
  _accessibility.css — skip-to-content, prefers-reduced-motion (C2-B, C2-F)
  _content.css       — page header responsive rules (C2-C)
  _pagination.css    — stacked filter bar on mobile (C2-D)
  _filter.css        — filter bar collapse (C2-D)
  _search.css        — search input mobile sizing (C2-D)

src/hyperadmin/templates/
  _base.html         — skip-to-content link, viewport meta (C2-F)
  _navbar.html       — hamburger button, Alpine.js toggle (C2-A)
  _sidebar.html      — overlay, backdrop, role=dialog (C2-A)
  table.html         — data-responsive-card markup (C1-C)
  inline_formset.html — mobile-friendly inline layout (C2-B)
```

### 3-Cycle Delivery Plan (zero file conflict per cycle)

```
Cycle 1 — Foundation (3 agents, true parallel, no deps):
  C1-A  _tokens.css only
  C1-B  _responsive.css, _layout.css, _sidebar.css, _fieldsets.css
  C1-C  _table.css, table.html  (self-contained — no token dep)

Cycle 2 — Components (3 slots + 3 stagger pickups):
  C2-A  _sidebar.css (overlay), _navbar.css, _navbar.html, _sidebar.html, _base.html
  C2-B  _forms.css, _inlines.css, _accessibility.css, inline_formset.html
  C2-C  _content.css
  C2-D  _pagination.css, _filter.css, _search.css   (stagger)
  C2-E  _forms.css mobile font-size only             (stagger — tiny, non-conflicting)
  C2-F  _accessibility.css skip link, _base.html     (stagger)

Cycle 3 — Polish + Testing (3 slots + stagger):
  C3-A  _navbar.css responsive rules
  C3-B  _login.css, login/detail/dashboard templates
  C3-C  tests/e2e/test_responsive_*.py
  C3-D  visual regression snapshots                  (stagger)
```

Critical path: `C1-B → C2-A → C3-C` (3 × medium stories across 3 cycles).

### Data Model Changes

No data model changes. CSS/template-only.

### API / Protocol Changes

No API changes. No changes to `__init__.py` exports.

### Configuration Changes

No configuration changes. No new `Admin()` or `AdminOptions` parameters.

## Edge Cases & Error Handling

| Case | Handling |
|---|---|
| iOS Safari auto-zoom on input focus | All mobile inputs get `font-size: 1rem` (≥16px) via `_forms.css` media query in C2-E |
| Sidebar overlay scroll-through on mobile | `overflow: hidden` on `<body>` when overlay is open, managed by Alpine.js |
| Keyboard trap in sidebar overlay | `role="dialog"` + `aria-modal="true"` + Alpine.js focus-trap plugin (C2-A) |
| `prefers-reduced-motion: reduce` | All CSS transitions gated with `@media (prefers-reduced-motion: no-preference)` |
| Desktop regression at 1280×720 | C1-B scenario explicitly asserts layout parity; visual regression baseline (C3-D) guards it |
| 320px minimum viewport (very small phones) | Page header story (C2-C) catches action bar overflow at 320px |
| Table with 10+ columns on mobile | Stacked-card layout in C1-C hides column headers; field label shown per value |

## Migration & Backward Compatibility

Backward compatible — no migration required. All changes are additive CSS and
template additions. No Python or public API surface changes. Existing desktop
layout is preserved via `min-width` media queries.

## Open Questions

- [x] Should table stacked-card use `data-label` attributes for field names?
  → Yes. `data-label` is set server-side in `table.html`, read by CSS
  `::before` pseudo-element. No JS required.
- [x] Alpine.js focus-trap: built-in plugin or custom?
  → Alpine.js ships `@alpinejs/focus` (already a dep). Use `x-trap` directive.
- [x] Visual regression tooling?
  → Playwright screenshot assertions. Stored in `tests/e2e/snapshots/`. CI
  compares on each run; update with `--update-snapshots` flag.

## Decision Log

| Decision | Rationale | Alternatives considered |
|---|---|---|
| Split #452 (size:L) into C1-A tokens (S) + C1-B layout (M) | Enables true Cycle 1 parallelism; tokens are a pure additive 5-line change, separating them removes the serial bottleneck | Keep #452 monolithic (Alpha/Gamma approach) — adds 1 extra wave to critical path |
| C1-C table self-contained (no token dep) | Allows 3-agent Cycle 1 with zero file conflict; table uses its own breakpoint values | Make table depend on tokens — forces serialisation |
| WCAG 2.1 AA as mandatory (not stretch) | iOS zoom prevention + skip-to-content are size:S stories with outsized a11y impact; cost is negligible, risk of skipping is reputation | Defer all a11y to v0.4.1 (Beta's approach) |
| Defer 7 Gamma stories to v0.4.1 | Skeleton states, empty states, orientation, scroll-to-top, touch feedback, typography are polish — none block basic mobile usability | Include all 17 Gamma stories in v0.4.0 — risks milestone overrun |
| Alpine.js `x-trap` for focus management | Already a declared dependency; zero new JS | Custom focus-trap or dialog element — more code, no benefit |
