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
#452 Mobile-first CSS architecture + mobile typography (FOUNDATION) [HIGH, L]
  ├── #458 Collapsible sidebar + focus trap + SR dialog [HIGH, L]
  │     ├── #465 Responsive navbar [HIGH, S]
  │     ├── Orientation handling [MEDIUM, S]
  │     └── CSS transitions (reduced-motion) [LOW, S] — stretch
  ├── #461 Responsive data table card layout + SR support [HIGH, M]
  │     ├── #464 Mobile pagination & filter bar [HIGH, M]
  │     ├── HTMX skeleton loading states [MEDIUM, M]
  │     └── Mobile empty state designs [LOW, S] — stretch
  ├── #467 Touch-friendly forms [HIGH, M]
  ├── iOS input zoom prevention [HIGH, S]
  ├── Skip-to-content landmarks [HIGH, S]
  ├── CSS-only touch feedback [MEDIUM, S]
  └── #470 Responsive login, detail, dashboard (final polish) [MEDIUM, S]
      └── E2E responsive test suite [MEDIUM, L]
```

### Sub-issues (15 active, ordered by priority + dependency)

**HIGH priority — must ship for v0.4.0:**
- [ ] #452 refactor(ui): mobile-first CSS architecture with breakpoint tokens + mobile typography
- [ ] #458 feat(ui): collapsible sidebar with hamburger menu toggle (includes focus trap + SR dialog)
- [ ] #461 feat(ui): responsive data table with stacked card layout (includes SR card announcements)
- [ ] #464 feat(ui): mobile-optimized pagination and filter bar
- [ ] #465 feat(ui): responsive navbar with mobile optimizations
- [ ] #467 feat(ui): touch-friendly forms and inline formsets on mobile
- [ ] feat(ui): iOS input zoom prevention with minimum font sizes
- [ ] feat(ui): skip-to-content and landmark enhancements for mobile

**MEDIUM priority — should ship for v0.4.0:**
- [ ] feat(ui): CSS-only touch feedback active states
- [ ] feat(ui): orientation handling and viewport stability
- [ ] feat(ui): HTMX loading skeleton states for mobile
- [ ] #470 feat(ui): responsive login, detail, and dashboard views
- [ ] test(e2e): responsive design E2E test suite

**LOW priority — stretch goals, cut if timeline tight:**
- [ ] feat(ui): CSS transitions with reduced-motion respect
- [ ] feat(ui): mobile-friendly empty state designs
