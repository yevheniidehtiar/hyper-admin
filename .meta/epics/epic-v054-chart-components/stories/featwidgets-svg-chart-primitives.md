---
type: story
id: st-v054-charts-01
title: "feat(widgets): SVG chart primitives (bar, line, stacked-bar, pie)"
status: todo
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
updated_at: 2026-05-11T00:00:00Z
---

## Summary

Implement the four server-rendered SVG chart primitives in
`widgets/charts.py` + matching Jinja templates. Each chart produces
accessible SVG (`role="img"`, `<title>`, `<desc>`) and a paired
`<details><table>` data-table fallback. Uses the CSS variable palette
`--ha-chart-1` … `--ha-chart-7` so consumers can theme without forking
templates.

**Spec:** [`docs/specs/chart-components.md`](../../../../docs/specs/chart-components.md)

## Files to Change

- **New:** `src/hyperadmin/widgets/charts.py` — `BarChart`, `LineChart`, `StackedBarChart`, `PieChart`, `Chart` wrapper
- **New:** `src/hyperadmin/templates/widgets/charts/bar.svg.html`
- **New:** `src/hyperadmin/templates/widgets/charts/line.svg.html`
- **New:** `src/hyperadmin/templates/widgets/charts/stacked_bar.svg.html`
- **New:** `src/hyperadmin/templates/widgets/charts/pie.svg.html`
- **New:** `src/hyperadmin/templates/widgets/chart_fallback.html`
- **Modified:** existing CSS — chart palette variables
- **New:** `tests/unit/test_charts_svg.py`

## Scenarios

```
Scenario: BarChart renders one bar per category
  Given a dataset [(A, 10), (B, 20), (C, 30)]
  When  BarChart.render(dataset) is called
  Then  the output contains exactly three <rect class="bar"> elements

Scenario: long category label is truncated with ellipsis
  Given a category label "supercalifragilisticexpialidocious" (>18 chars)
  When  the chart renders with default width
  Then  the rendered tspan text ends with "…"

Scenario: data-table fallback enumerates the source rows
  When  the chart renders
  Then  the output contains a <details data-testid="chart-data-table-{title-slug}"> with one <tr> per data point
```

## Acceptance Criteria

- [ ] Four chart classes implemented; each has its template
- [ ] SVG has `role="img"`, `<title>`, `<desc>` populated from `Chart.title`
- [ ] `<details><table>` fallback in DOM order after the SVG
- [ ] CSS palette `--ha-chart-1..7` used (no hard-coded colours)
- [ ] Long-label truncation at the configured width
- [ ] Three scenarios above covered as unit / rendering tests
- [ ] Visual snapshots committed for each chart kind
- [ ] `poe lint` and `poe test:unit` pass

## Blocked by

- `reviewspec-approve-sdd-chart-components`

## Parent

- Epic: `epic-v054-chart-components`
