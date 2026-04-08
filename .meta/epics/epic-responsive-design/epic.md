---
type: epic
id: RspSynth_01
title: "epic(ui): Responsive Design -- Mobile-First CSS Overhaul"
status: in_progress
priority: high
owner: null
labels:
  - frontend
  - responsive
  - css
  - ui
milestone_ref:
  id: lQHUqC1sVwjC
github:
  issue_number: null
  repo: yevheniidehtiar/hyper-admin
  last_sync_hash: null
  synced_at: null
created_at: 2026-04-07T00:00:00Z
updated_at: 2026-04-08T00:00:00Z
---

## Epic: Responsive Design -- Mobile-First CSS Overhaul

Part of milestone: **v0.4.0 -- Responsive Design** (target: 2026-05-30)

**Spec:** `docs/specs/responsive-design.md`

### Goal

Transform HyperAdmin from desktop-only to mobile-first responsive. Every admin view
must be fully usable on phones (375px) and tablets (768px) with touch-friendly controls.
All changes must be CSS/template-only -- no new Python dependencies.

### Principles

1. **Mobile-first CSS**: base styles are mobile, enhance with `min-width` media queries.
2. **Accessibility mandatory**: every story must meet WCAG 2.1 AA -- touch targets >= 44px,
   focus management, screen reader support, `prefers-reduced-motion` respected.
3. **No new dependencies**: pure CSS + Alpine.js (already included) + HTMX (already included).
4. **Demo-app-first**: every story must be verifiable in `examples/simple` or `examples/erp`.

### Optimized Cycle Plan (3 agents per cycle)

#### Cycle 1 -- Foundation (3 agents, zero file conflicts, no dependencies)

| Slot | Story | Size | Files |
|------|-------|------|-------|
| C1-A | Breakpoint tokens | S | `_tokens.css` |
| C1-B | Mobile-first base layout | M | `_responsive.css`, `_layout.css`, `_sidebar.css`, `_fieldsets.css` |
| C1-C | Responsive data table (self-contained) | M | `_table.css`, `table.html` |

Conflict check: **ZERO overlap**. All 3 run truly in parallel.

#### Cycle 2 -- Components (3 agents + stagger pickups)

| Slot | Story | Size | Depends on |
|------|-------|------|-----------|
| C2-A | Sidebar + focus trap + SR dialog | M | C1-B |
| C2-B | Touch-friendly forms | M | C1-B |
| C2-C | Page header + action bar | M | C1-B |
| C2-D stagger | Pagination / filter bar | M | C1-B |
| C2-E stagger | iOS zoom prevention | S | C1-B |
| C2-F stagger | Skip-to-content landmarks | S | C1-B |

Conflict check: **ZERO overlap** between C2-A/B/C. Stagger picks up as agents free.

#### Cycle 3 -- Polish + Testing (3 agents + stagger)

| Slot | Story | Size | Depends on |
|------|-------|------|-----------|
| C3-A | Responsive navbar | S | C2-A |
| C3-B | Login/detail/dashboard views | S | C2-A, C2-B, C2-C, C2-D |
| C3-C | E2E responsive tests | M | all C2 |
| C3-D stagger | Visual regression baseline | S | C3-C |

### Sub-issues (14 stories)

| Cycle | Story | Size | Depends on |
|-------|-------|------|-----------|
| C1-A | Breakpoint tokens | S | none |
| C1-B | Mobile-first base layout | M | none |
| C1-C | Responsive data table | M | none (self-contained) |
| C2-A | Collapsible sidebar + focus trap | M | C1-B |
| C2-B | Touch-friendly forms | M | C1-B |
| C2-C | Page header + action bar | M | C1-B |
| C2-D | Pagination / filter bar | M | C1-B |
| C2-E | iOS zoom prevention | S | C1-B |
| C2-F | Skip-to-content landmarks | S | C1-B |
| C3-A | Responsive navbar | S | C2-A |
| C3-B | Login/detail/dashboard views | S | C2-A, C2-B, C2-C, C2-D |
| C3-C | E2E responsive tests | M | all C2 |
| C3-D | Visual regression baseline | S | C3-C |
| defer | Docs: responsive guide | S | C3-B (low priority, deferrable) |

### Dependency Graph

```
Cycle 1 (3 agents, true parallel):
  C1-A (tokens, S) --------+
  C1-B (layout, M) --------+---> Cycle 2 starts
  C1-C (table, M) ---------+

Cycle 2 (3 agents + stagger):
  C2-A (sidebar, M) --------+
  C2-B (forms, M) ----------+
  C2-C (page header, M) ----+---> Cycle 3 starts
  C2-D (pagination, M) -----+    (stagger)
  C2-E (iOS zoom, S) -------+    (stagger)
  C2-F (skip-to-content, S) +    (stagger)

Cycle 3 (3 agents + stagger):
  C3-A (navbar, S) ----------+
  C3-B (login/detail, S) ----+---> Milestone complete
  C3-C (e2e tests, M) -------+
  C3-D (visual reg, S) ------+    (stagger)
```

### Critical Path

```
C1-B (layout, M) --> C2-A (sidebar, M) --> C3-C (e2e tests, M)
```

Total critical path: M + M + M = 3 medium stories across 3 cycles.

### File Target Map (Zero-Conflict Guarantee)

| Story | CSS files | Template files |
|-------|-----------|---------------|
| C1-A tokens | `_tokens.css` | -- |
| C1-B layout | `_responsive.css`, `_layout.css`, `_sidebar.css`, `_fieldsets.css` | -- |
| C1-C table | `_table.css` | `table.html` |
| C2-A sidebar | `_sidebar.css` (overlay rules), `_navbar.css` | `_navbar.html`, `_sidebar.html`, `_base.html` |
| C2-B forms | `_forms.css`, `_inlines.css`, `_accessibility.css` | `inline_formset.html` |
| C2-C page header | `_content.css` (new section) | -- |
| C2-D pagination | `_pagination.css`, `_filter.css`, `_search.css` | -- |
| C2-E iOS zoom | `_forms.css` (mobile font-size only) | -- |
| C2-F skip-to-content | `_accessibility.css` (skip link) | `_base.html` (skip link element) |

### Scope Notes

**Core v0.4.0 (must-ship):** 13 stories (all except docs)
**Deferrable (low priority):** docs responsive guide (#472)
**Deferred to v0.4.1:** HTMX skeleton states, mobile empty states, orientation handling, scroll-to-top, CSS touch feedback, typography polish

### Agent Tier Assignment

All CSS/template stories use Sonnet tier. E2E test suite uses Opus.

### Risk Mitigation

1. **_responsive.css contention**: Eliminated by self-contained media query strategy per component
2. **Desktop regression**: C1-B scenario explicitly requires visual parity at 1280x720
3. **Touch target compliance**: Forms and pagination mandate 44px minimum heights
4. **Focus trap in sidebar**: Mandatory `role="dialog"` + aria-label for screen readers
5. **iOS zoom**: Font-size >= 16px on all mobile inputs prevents Safari auto-zoom

### Origin

This plan is a synthesis from the Parallel Planning Universes (PPU) experiment.
See `.claude/experiments/ppu-analysis-report.md` for full analysis.

- **Structure**: Beta's 3-cycle architecture with file-target map and stagger pickups
- **Scope**: Beta's 11 + 3 cherry-picked from Gamma (iOS zoom, skip-to-content, page header)
- **A11y**: Gamma's WCAG 2.1 AA mandate, focus trap, and SR scenarios folded into existing stories
- **Organization**: Alpha's consolidation into a single epic directory

### Acceptance Criteria

- [ ] Mobile-first CSS with breakpoint tokens
- [ ] Collapsible sidebar with hamburger toggle, focus trap, and SR dialog
- [ ] Data tables as stacked cards on mobile
- [ ] Touch-friendly forms, pagination, and page headers
- [ ] iOS input zoom prevention
- [ ] Skip-to-content and landmark enhancements
- [ ] Responsive navbar, login, detail, and dashboard views
- [ ] Comprehensive E2E viewport tests with visual regression baseline
