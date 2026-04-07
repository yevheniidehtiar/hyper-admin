---
type: epic
id: cvr4sYoEN9CV
title: "Epic 4.0: Responsive Design Overhaul"
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
updated_at: 2026-04-07T00:00:00Z
---

## Epic: Responsive Design Overhaul

Part of milestone: **v0.4.0 -- Responsive Design** (target: 2026-05-30)

### Goal

Transform HyperAdmin from desktop-only to mobile-first responsive. Every admin view
must be fully usable on phones (375px) and tablets (768px) with touch-friendly controls.
All changes must be CSS/template-only -- no new Python dependencies.

### Optimized Wave Plan (3 agents per cycle)

#### Cycle 1 -- Foundation (3 agents, zero file conflicts, no dependencies)

| Slot | Story | ID | Size | Files |
|------|-------|----|------|-------|
| A | Breakpoint tokens | `dyx7PkkdpBto` | S | `_tokens.css` |
| B | Mobile-first base layout + fieldset migration | `v8xvLKJfP_46` | M | `_responsive.css`, `_layout.css`, `_sidebar.css`, `_fieldsets.css` |
| C | Responsive data table with card layout | `KKpriYWS0U9B` | M | `_table.css`, `table.html` |

Conflict check: **ZERO overlap**. All 3 run truly in parallel.

#### Cycle 2 -- Components + Login/Detail (3 agents with stagger)

| Slot | Story | ID | Size | Files | Depends on |
|------|-------|----|------|-------|-----------|
| A | Collapsible sidebar + hamburger | `8P_VPRTVAWHF` | M | `_sidebar.css`, `_navbar.html`, `_sidebar.html`, `_base.html` | W1-B |
| B | Touch-friendly forms | `I0BwE7nn-Qpf` | M | `_forms.css`, `_inlines.css`, `_accessibility.css`, `inline_formset.html` | W1-B |
| C | Mobile pagination & filter bar | `miwk_JpwDtKy` | M | `_pagination.css`, `_filter.css`, `_search.css` | W1-B |

Conflict check: **ZERO overlap**.

**Stagger pickup**: When Slot C finishes (pagination is smaller scope), pick up:
- Login, detail & dashboard views (`xtGoFKkfxC7P`, size:S) -- `_login.css`, `_buttons.css` -- zero conflict with slots A/B

#### Cycle 3 -- Navbar + Testing (3 agents)

| Slot | Story | ID | Size | Files | Depends on |
|------|-------|----|------|-------|-----------|
| A | Responsive navbar | `TAhnnvjjZxyA` | S | `_navbar.css` | W2-A (hamburger) |
| B | E2E responsive test suite | `B57RGgp05uU0` | M | `tests/e2e/test_responsive.py` | all Cycle 2 |
| C | Demo app responsive showcase | `15CEiBOvAi6d` | S | `examples/erp/` | all Cycle 2 |

Conflict check: **ZERO overlap**.

**Stagger pickup**: When Slot A finishes (navbar is size:S), pick up:
- Visual regression baseline (`Fm1NkN9kfAW1`, size:S) -- `tests/e2e/test_visual_regression.py`

### Sub-issues (11 stories)

| Wave | ID | Title | Size | Depends on |
|------|----|-------|------|-----------|
| C1-A | `dyx7PkkdpBto` | Breakpoint tokens | S | none |
| C1-B | `v8xvLKJfP_46` | Mobile-first base layout | M | none |
| C1-C | `KKpriYWS0U9B` | Responsive data table | M | none |
| C2-A | `8P_VPRTVAWHF` | Collapsible sidebar | M | C1-B |
| C2-B | `I0BwE7nn-Qpf` | Touch-friendly forms | M | C1-B |
| C2-C | `miwk_JpwDtKy` | Mobile pagination/filter | M | C1-B |
| C2-D | `xtGoFKkfxC7P` | Login/detail/dashboard | S | C1-B (stagger pickup) |
| C3-A | `TAhnnvjjZxyA` | Responsive navbar | S | C2-A |
| C3-B | `B57RGgp05uU0` | E2E responsive tests | M | all C2 |
| C3-C | `15CEiBOvAi6d` | Demo app showcase | S | all C2 |
| C3-D | `Fm1NkN9kfAW1` | Visual regression baseline | S | C3-B (stagger pickup) |

### Dependency Graph (Optimized)

```
Cycle 1 (3 agents, true parallel):
  C1-A (tokens, S) ----+
  C1-B (layout, M) ----+---> Cycle 2 starts
  C1-C (table, M) -----+

Cycle 2 (3 agents + stagger):
  C2-A (sidebar, M) --------+
  C2-B (forms, M) ----------+---> Cycle 3 starts
  C2-C (pagination, M) --+  |
                          |  |
  C2-D (login/detail, S) +--+    (stagger: agent freed from C2-C picks up C2-D)

Cycle 3 (3 agents + stagger):
  C3-A (navbar, S) ------+
  C3-B (e2e tests, M) ---+---> Milestone complete
  C3-C (demo, S) --------+
                          |
  C3-D (visual reg, S) --+       (stagger: agent freed from C3-A picks up C3-D)
```

**Total: 3 cycles to complete 11 stories** (down from 4, a 25% reduction)

### Shared File Strategy: `_responsive.css`

- C1-B does the full mobile-first rewrite with section placeholders
- All component stories add responsive rules WITHIN their own CSS files
  using self-contained `@media` queries
- This eliminates the shared-file bottleneck entirely

### Critical Path

```
C1-B (layout, M) --> C2-A (sidebar, M) --> C3-A (navbar, S)
                                       \-> C3-B (e2e tests, M)
```

The critical path is: base layout -> sidebar hamburger -> E2E tests.
Total critical path size: M + M + M = 3 medium stories.

### Original Stories (superseded)
- #452 split into C1-A + C1-B
- #458, #461, #464, #465, #467, #470 reworked with narrower scopes and cycle labels

### Time to First Demoable Mobile Experience

**Answer: End of Cycle 1** -- specifically when C1-C (data table cards) completes.

C1-C is independent (no dependencies) and produces a visible mobile feature:
open any list view at 375px viewport and see stacked cards instead of a table.
This is demoable even before the base layout rewrite (C1-B) completes, because
the card CSS uses self-contained media queries within `_table.css`.

**First full mobile demo**: End of Cycle 2, when sidebar toggle, forms, and
pagination are all responsive. A user can navigate the entire admin on a phone.

### Agent Tier Assignment

All stories in this epic are **CSS/template only** (no Python logic), so Sonnet
tier is sufficient. Reserve Opus for the E2E test suite (C3-B) which requires
understanding the full responsive behavior across all views.

| Story | Tier |
|-------|------|
| C1-A Breakpoint tokens | Sonnet |
| C1-B Base layout rewrite | Sonnet |
| C1-C Data table cards | Sonnet |
| C2-A Sidebar hamburger | Sonnet |
| C2-B Touch-friendly forms | Sonnet |
| C2-C Pagination/filter | Sonnet |
| C2-D Login/detail/dashboard | Sonnet |
| C3-A Navbar responsive | Sonnet |
| C3-B E2E responsive tests | Opus |
| C3-C Demo app showcase | Sonnet |
| C3-D Visual regression | Sonnet |

### Risk Mitigation

1. **_responsive.css contention**: Eliminated by self-contained media query strategy
2. **Desktop regression**: C1-B scenario explicitly requires visual parity at 1280x720
3. **Touch target compliance**: W2-B and W2-C scenarios mandate 44px minimum heights
4. **Alpine.js scope conflicts**: C2-A sidebar toggle uses scoped `x-data` on body wrapper
5. **CSS specificity wars**: All responsive rules use `@layer responsive` (highest specificity)

### Size Summary

| Size | Count |
|------|-------|
| S | 6 |
| M | 5 |
| L | 0 |
| **Total** | **11 stories across 3 cycles** |
