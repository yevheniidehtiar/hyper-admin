---
type: epic
id: Rsp4_Gamma_01
title: "Epic 4.3: Responsive Design — Mobile-First Admin UX"
status: todo
priority: high
owner: null
labels:
  - frontend
  - responsive
  - accessibility
  - ui
milestone_ref:
  id: lQHUqC1sVwjC
github:
  issue_number: null
  repo: yevheniidehtiar/hyper-admin
  last_sync_hash: null
  synced_at: null
created_at: 2026-04-07T00:00:00Z
updated_at: 2026-04-07T00:00:00Z
---

## Epic: Responsive Design — Mobile-First Admin UX

Part of milestone: **v0.4.0 — Responsive Design**

### Goal

Transform HyperAdmin from a desktop-only admin into a genuinely usable mobile-first
experience. Every story must produce a visible, demoable improvement in the example apps
(simple + ERP) when viewed on mobile devices.

### Principles

1. **Mobile-first CSS**: base styles are mobile, enhance with `min-width` media queries.
2. **Accessibility mandatory**: every story must meet WCAG 2.1 AA — touch targets >= 44px,
   focus management, screen reader support, `prefers-reduced-motion` respected.
3. **Progressive enhancement**: the mobile experience must be genuinely good, not just
   "not broken."
4. **No new dependencies**: pure CSS + Alpine.js (already included) + HTMX (already included).
5. **Demo-app-first**: every story must be verifiable in `examples/simple` or `examples/erp`.

### Dependency Chain

```
#452 Mobile-first CSS architecture (FOUNDATION) [HIGH, L]
  ├── #458 Collapsible sidebar + focus trap + SR dialog [HIGH, L]
  │     ├── #465 Responsive navbar + a11y button names [HIGH, S]
  │     ├── Orientation handling [LOW, S] — stretch
  │     └── CSS transitions (reduced-motion) [LOW, S] — stretch
  ├── #461 Responsive data table card layout + SR support [HIGH, M]
  │     ├── #464 Mobile pagination & filter bar [HIGH, M]
  │     ├── HTMX skeleton loading states [MEDIUM, M]
  │     └── Mobile empty state designs [LOW, S] — stretch
  ├── #467 Touch-friendly forms + label a11y [HIGH, M]
  ├── iOS input zoom prevention [HIGH, S]
  ├── Skip-to-content landmarks [HIGH, S]
  ├── CSS-only touch feedback [HIGH, S]
  ├── Responsive page header / action bar [HIGH, S]
  ├── Mobile scroll-to-top after HTMX nav [MEDIUM, S]
  └── #470 Responsive login, detail, dashboard (final polish) [MEDIUM, S]
      └── E2E responsive test suite [MEDIUM, L]
```

### Sub-issues (18 active, ordered by UX impact + dependency)

**HIGH priority — must ship for v0.4.0 (core mobile admin experience):**
1. [ ] #452 refactor(ui): mobile-first CSS architecture with breakpoint tokens (FOUNDATION)
2. [ ] #458 feat(ui): collapsible sidebar with hamburger toggle, focus trap, SR dialog
3. [ ] #461 feat(ui): responsive data table with stacked card layout + SR support
4. [ ] #467 feat(ui): touch-friendly forms and inline formsets on mobile
5. [ ] feat(ui): iOS input zoom prevention with minimum font sizes
6. [ ] #464 feat(ui): mobile-optimized pagination and filter bar
7. [ ] feat(ui): skip-to-content and landmark enhancements for mobile
8. [ ] #465 feat(ui): responsive navbar with mobile optimizations
9. [ ] feat(ui): CSS-only touch feedback active states
10. [ ] feat(ui): responsive page header and action bar (NEW)

**MEDIUM priority — should ship for v0.4.0 (perceived quality):**
11. [ ] feat(ui): mobile typography and spacing polish
12. [ ] feat(ui): HTMX loading skeleton states for mobile
13. [ ] feat(ui): mobile scroll-to-top after HTMX navigation (NEW)
14. [ ] #470 feat(ui): responsive login, detail, and dashboard views
15. [ ] test(e2e): responsive design E2E test suite

**LOW priority — stretch goals, cut if timeline tight:**
16. [ ] feat(ui): orientation handling and viewport stability
17. [ ] feat(ui): CSS transitions with reduced-motion respect
18. [ ] feat(ui): mobile-friendly empty state designs
