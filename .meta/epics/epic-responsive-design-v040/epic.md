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

Part of milestone: **v0.4.0 — Responsive Design** (target: 2026-05-30)

### Goal

Transform HyperAdmin from desktop-only to mobile-first responsive. Every admin view
must be fully usable on phones (375px) and tablets (768px) with touch-friendly controls.
All changes must be CSS/template-only — no new Python dependencies.

### Wave Plan (3 agents per wave)

#### Wave 1 — Foundation (no dependencies)
Three independent foundation stories that unblock everything else:
- **W1-A**: Breakpoint tokens in `_tokens.css` (size:S) — adds CSS custom properties
- **W1-B**: Mobile-first base layout rewrite (size:M) — rewrites `_responsive.css`, `_layout.css`, `_sidebar.css`
- **W1-C**: Fieldset responsive migration (size:S) — moves fieldset media query to responsive layer

#### Wave 2 — Parallel Components (each depends only on W1-B)
Three component stories that can run in parallel (no file conflicts):
- **W2-A**: Collapsible sidebar with hamburger (#458 reworked) — `_sidebar.css`, `_navbar.html`, `_sidebar.html`, `_base.html`
- **W2-B**: Responsive data table with card layout (#461 reworked) — `_table.css`, `table.html`
- **W2-C**: Touch-friendly forms (#467 reworked) — `_forms.css`, `_inlines.css`, `_accessibility.css`, `inline_formset.html`

#### Wave 3 — Secondary Components (after Wave 2)
Three more stories, each with narrow file scopes:
- **W3-A**: Mobile pagination & filter bar (#464 reworked) — `_pagination.css`, `_filter.css`, `_search.css`
- **W3-B**: Responsive navbar (#465 reworked) — `_navbar.css`
- **W3-C**: Login, detail & dashboard views (#470 reworked) — `_login.css`, `_buttons.css`

#### Wave 4 — Integration & E2E Testing
- **W4-A**: E2E responsive test suite — Playwright viewport tests for all views
- **W4-B**: Visual regression baseline — screenshot comparison at key breakpoints
- **W4-C**: Demo app responsive showcase — example app page demonstrating all responsive features

### Sub-issues
- [ ] W1-A: Breakpoint tokens (size:S)
- [ ] W1-B: Mobile-first base layout rewrite (size:M)
- [ ] W1-C: Fieldset responsive migration (size:S)
- [ ] W2-A: Collapsible sidebar with hamburger (size:M)
- [ ] W2-B: Responsive data table with card layout (size:M)
- [ ] W2-C: Touch-friendly forms on mobile (size:M)
- [ ] W3-A: Mobile pagination & filter bar (size:M)
- [ ] W3-B: Responsive navbar (size:S)
- [ ] W3-C: Login, detail & dashboard views (size:S)
- [ ] W4-A: E2E responsive test suite (size:M)
- [ ] W4-B: Visual regression baseline (size:S)
- [ ] W4-C: Demo app responsive showcase (size:S)

### Original Stories (superseded, now epic_ref: null)
- #452 → split into W1-A + W1-B + W1-C
- #458, #461, #464, #465, #467, #470 → reworked as W2/W3 stories with narrower scopes
