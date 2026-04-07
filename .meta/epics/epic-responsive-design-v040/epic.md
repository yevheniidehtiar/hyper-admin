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

### Wave Plan (3 agents per wave, optimized for max parallelism)

#### Wave 1 -- Foundation (3 agents, zero file conflicts, no dependencies)
- **W1-A** `dyx7PkkdpBto`: Breakpoint tokens in `_tokens.css` (size:S)
- **W1-B** `v8xvLKJfP_46`: Mobile-first base layout + fieldset migration (size:M) -- `_responsive.css`, `_layout.css`, `_sidebar.css`, `_fieldsets.css`
- **W1-C** `KKpriYWS0U9B`: Responsive data table with card layout (size:M, promoted from old W2) -- `_table.css`, `table.html` (self-contained media queries)

File conflict check: W1-A=`_tokens.css`, W1-B=`_responsive/_layout/_sidebar/_fieldsets`, W1-C=`_table/table.html` -- **ZERO overlap**.

#### Wave 2 -- Parallel Components (3 agents, depends on W1-B only)
- **W2-A** `8P_VPRTVAWHF`: Collapsible sidebar with hamburger (#458) -- `_sidebar.css`, `_navbar.html`, `_sidebar.html`, `_base.html`
- **W2-B** `I0BwE7nn-Qpf`: Touch-friendly forms (#467) -- `_forms.css`, `_inlines.css`, `_accessibility.css`, `inline_formset.html`
- **W2-C** `miwk_JpwDtKy`: Mobile pagination & filter bar (#464) -- `_pagination.css`, `_filter.css`, `_search.css`

File conflict check: W2-A=sidebar+navbar templates, W2-B=forms+inlines+a11y, W2-C=pagination+filter+search -- **ZERO overlap**.

#### Wave 3 -- Secondary Components (2 agents, depends on W2-A)
- **W3-A** `TAhnnvjjZxyA`: Responsive navbar (#465) -- `_navbar.css` (depends on W2-A hamburger)
- **W3-B** `xtGoFKkfxC7P`: Login, detail & dashboard views (#470) -- `_login.css`, `_buttons.css`

File conflict check: W3-A=`_navbar.css`, W3-B=`_login/_buttons` -- **ZERO overlap**.

#### Wave 4 -- Integration & E2E Testing (3 agents, depends on all prior waves)
- **W4-A** `B57RGgp05uU0`: E2E responsive test suite -- `tests/e2e/test_responsive.py`
- **W4-B** `Fm1NkN9kfAW1`: Visual regression baseline -- `tests/e2e/test_visual_regression.py`
- **W4-C** `15CEiBOvAi6d`: Demo app responsive showcase -- `examples/erp/`

File conflict check: all unique files -- **ZERO overlap**.

### Sub-issues

- [ ] W1-A: Breakpoint tokens (size:S) `dyx7PkkdpBto`
- [ ] W1-B: Mobile-first base layout + fieldset migration (size:M) `v8xvLKJfP_46`
- [ ] W1-C: Responsive data table with card layout (size:M) `KKpriYWS0U9B`
- [ ] W2-A: Collapsible sidebar with hamburger (size:M) `8P_VPRTVAWHF`
- [ ] W2-B: Touch-friendly forms on mobile (size:M) `I0BwE7nn-Qpf`
- [ ] W2-C: Mobile pagination & filter bar (size:M) `miwk_JpwDtKy`
- [ ] W3-A: Responsive navbar (size:S) `TAhnnvjjZxyA`
- [ ] W3-B: Login, detail & dashboard views (size:S) `xtGoFKkfxC7P`
- [ ] W4-A: E2E responsive test suite (size:M) `B57RGgp05uU0`
- [ ] W4-B: Visual regression baseline (size:S) `Fm1NkN9kfAW1`
- [ ] W4-C: Demo app responsive showcase (size:S) `15CEiBOvAi6d`

### Dependency Graph

```
Wave 1 (parallel, no deps):
  W1-A ─────────────────────┐
  W1-B ─────────────────────┤── Wave 2 starts when W1-B done
  W1-C (independent) ───────┘

Wave 2 (parallel, W1-B done):
  W2-A ─────────┐
  W2-B ─────────┤── Wave 3 starts when W2-A done
  W2-C ─────────┘

Wave 3 (parallel, W2-A done):
  W3-A ─────────┐
  W3-B ─────────┤── Wave 4 starts when all Wave 3 done

Wave 4 (parallel, all done):
  W4-A ─────────┐
  W4-B ─────────┤── Milestone complete
  W4-C ─────────┘
```

### Shared File Strategy: `_responsive.css`

Multiple stories may need responsive rules. Strategy:
- W1-B does the full mobile-first rewrite with section placeholders
- Component stories (W2/W3) add their rules WITHIN their own CSS files using
  self-contained `@media` queries, NOT in `_responsive.css`
- This eliminates the shared-file bottleneck entirely

### Original Stories (superseded)
- #452 split into W1-A + W1-B (W1-C was the old fieldset migration, folded into W1-B)
- #458, #461, #464, #465, #467, #470 reworked with narrower scopes and wave labels

### Total Wall-Clock Estimate

- Wave 1: 1 cycle (3 agents)
- Wave 2: 1 cycle (3 agents)
- Wave 3: 1 cycle (2 agents)
- Wave 4: 1 cycle (3 agents)
- **Total: 4 cycles to complete 11 stories**
