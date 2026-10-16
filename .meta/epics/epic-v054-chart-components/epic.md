---
type: epic
id: ep-v054-charts-01
title: "epic(widgets): chart components bound to ReportView"
status: todo
priority: high
owner: null
labels:
  - size:L
  - planned
  - frontend
  - backend
  - upstream-readiness
  - H15
milestone_ref:
  id: 8DidH5NiN6cP
created_at: 2026-05-11T00:00:00Z
updated_at: 2026-05-11T00:00:00Z
---

## Overview

Implements upstream readiness capability **H15**: SVG primitives
(`LineChart`, `BarChart`, `StackedBarChart`, `Sparkline` + chart frame) and an
HTMX-loaded chart fragment route per `ReportView`. Server-rendered SVG only,
built from the design system (`docs/design/system/components/Chart/`) — no
Chart.js (owner decision, 2026-10-17). Accessible by default — each chart
ships an inline `<details><table>` data fallback.

**SDD:** [`docs/specs/chart-components.md`](../../../docs/specs/chart-components.md)
(required — new module, cross-module integration with reports + filters).

## Tracks

### Track A: SVG primitives
- `widgets/charts.py` + `templates/widgets/charts/*.svg.html` for the four shapes.
- Accessible markup (`role="img"`, `<title>`, `<desc>`, data-table fallback).
- CSS variable palette (`--ha-chart-1` … `--ha-chart-7`).

### Track B: Chart.js mode + vendored bundle — cancelled 2026-10-17 (no Chart.js)
- `static/vendor/chart-js/chart.umd.js` (vendored, not from CDN).
- `templates/widgets/charts/chartjs.html` — canvas + JSON dataset slot.
- Graceful fallback to SVG if the vendor file is missing.

### Track C: Wrapper + route + dataset reuse
- `Chart` Python wrapper (`kind`, `report`, `mode`, `title`, `height`).
- New chart-fragment route `GET /admin/reports/{slug}/chart`.
- Filter querystring passed through to the bound `ReportView`.

### Track D: E2E + accessibility
- Six SDD scenarios covered by Playwright.
- Axe-style accessibility assertions on the SVG output.

## Scenarios

See SDD `## BDD Scenarios` (six scenarios: SVG render, Chart.js mode,
stacked bar, lazy-load, a11y data table, filter context pass-through).

## Acceptance Criteria

- [ ] SVG primitives (line, bar, stacked bar, sparkline + frame) implemented + visual snapshots
- [ ] `Chart` wrapper exported from `hyperadmin.widgets`
- [ ] `/admin/reports/{slug}/chart` fragment endpoint registered
- [ ] Filter querystring forwarded transparently
- [ ] Accessible data-table fallback on by default
- [ ] Six SDD scenarios pass (unit + E2E)
- [ ] `poe lint` and `poe test` pass

## Blocked by

- `reviewspec-approve-sdd-chart-components`
- Epic `epic-v054-olap-reporting` (binds to `ReportView`)

## Parent

- Milestone: `v054-dashboard-builder` (Reporting & Charts)
- Tracking: `epic-upstream-readiness` (H15)
