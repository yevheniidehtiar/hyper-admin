---
type: story
id: st-v054-charts-01
title: "feat(widgets): SVG chart primitives (line, bar, stacked bar, sparkline + frame)"
status: in_review
priority: high
assignee: null
labels:
  - size:M
  - planned
  - frontend
  - upstream-readiness
  - H15
estimate: null
epic_ref:
  id: ep-v054-charts-01
created_at: 2026-05-11T00:00:00Z
updated_at: 2026-10-17T00:00:00Z
---

## Summary

Implement the server-rendered SVG chart primitives from the design system
(`docs/design/system/components/Chart/`): Python chart classes in `widgets/charts.py`
that compute all geometry from already-aggregated, already-thinned series, and Jinja
macros in `templates/components/charts/` that print it. Accessible SVG (`<title>`,
`<desc>`, focusable points with full `aria-label`s), a "Show as table" `<details>`
fallback, and loading / no-data / error states in the chart frame. Colours only from
the `--ha-chart-1` … `--ha-chart-6` tokens. No Chart.js, no client chart code.

Revised 2026-10-17: Chart.js is out (owner decision) and `PieChart` is dropped (the
design system defines no pie); see the SDD revision note.

**Spec:** [`docs/specs/chart-components.md`](../../../../docs/specs/chart-components.md)

## Files to Change

- **New:** `src/hyperadmin/widgets/__init__.py`, `charts.py`, `_marks.py`, `_scale.py`
- **New:** `src/hyperadmin/templates/components/charts/{frame,line,bar,stacked_bar,sparkline,_svg}.html`
- **New:** `src/hyperadmin/static/css/_charts.css` (imported from `hyperadmin.css`)
- **New:** `tests/unit/test_charts_svg.py`, `tests/unit/test_chart_scale.py`
- **New:** `tests/e2e/test_chart_visual.py` + baselines `tests/e2e/snapshots/responsive/**/charts-1024px.png`

## Scenarios

```
Scenario: BarChart renders one bar per category
  Given a dataset [(A, 10), (B, 20), (C, 30)]
  When  the bar macro renders
  Then  the output contains exactly three focusable <rect class="f1"> bars

Scenario: long category label is truncated with ellipsis
  Given a category label "supercalifragilisticexpialidocious" (>18 chars)
  When  the chart renders with default width
  Then  the rendered tspan text ends with "…"

Scenario: data-table fallback enumerates the source rows
  When  the chart frame renders
  Then  the output contains a <details data-testid="chart-data-table-{key}"> with one <tr> per data point

Scenario: a point's tooltip appears on keyboard focus
  When  a line chart point's hit area receives keyboard focus
  Then  its tooltip is visible and the others stay hidden
```

## Acceptance Criteria

- [x] Line, bar, stacked-bar and sparkline classes implemented; each has its macro; frame macro
- [x] SVG has `<title>` / `<desc>`; `role="group"` with focusable points, `role="img"` / `aria-hidden` for the sparkline
- [x] `<details>` table fallback in DOM order after the SVG
- [x] CSS palette `--ha-chart-1..6` used (no hard-coded colours)
- [x] Long-label truncation at the configured width
- [x] Scenarios above covered as unit / rendering / E2E tests
- [x] Visual snapshot committed for the chart components
- [x] `poe lint` and `poe test:unit` pass

## Blocked by

- `reviewspec-approve-sdd-chart-components` (done)

## Parent

- Epic: `epic-v054-chart-components`
