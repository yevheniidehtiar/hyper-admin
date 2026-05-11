# SDD: Chart Components (`hyperadmin.widgets.charts`)

| Field | Value |
|---|---|
| Author | Claude Code |
| Status | Draft |
| Issue | TBD |
| Milestone | v0.5.4 — Reporting & Charts |
| Created | 2026-05-11 |
| Last updated | 2026-05-11 |

---

## Problem

The H15 upstream check requires a chart bound to the same OLAP dataset H14
produces. HyperAdmin currently has no chart primitives. Consumers bolt on
chart libraries inconsistently — some pull in Chart.js, others build SVG by
hand, and dashboards diverge visually and behaviourally.

We want a built-in surface that (a) keeps simple cases dependency-free
(server-rendered SVG bar/line/stacked-bar/pie), (b) supports interactive
charts via Chart.js when richer affordances are needed, and (c) binds
declaratively to a `ReportView` from H14 so charts and tables share the same
data path.

## Goals

- New module `src/hyperadmin/widgets/charts.py` with four SVG primitives:
  `BarChart`, `LineChart`, `StackedBarChart`, `PieChart`.
- A `Chart` widget that wraps a `ReportView` and renders either SVG (default,
  no JS) or a Chart.js canvas (`mode="chartjs"`).
- HTMX-loaded chart fragment so the same chart can appear standalone, inside
  a detail panel (v0.5.6), or inside a future dashboard.
- Accessibility: SVG charts carry `role="img"`, `<title>`, `<desc>`, and a
  `<table>` data fallback collapsed under `<details>` for screen readers.
- No new JavaScript build pipeline — Chart.js is loaded via the existing
  vendored static asset slot (`templates/_base.html` already has a
  `{% block extra_js %}`).

## Non-Goals

- A full dashboard composer. v0.5.4 ships chart primitives + per-report chart.
  Composing several charts on one page is a thin consumer task (a Jinja
  template iterating widgets).
- Real-time / WebSocket-driven charts. Live updates land with the real-time
  milestone (v0.6.0).
- Custom theme system for charts. v0.5.4 uses the project's existing CSS
  variables; full theme support is later.
- Drill-down interactions (clicking a bar to filter the report). Deferred.
- Map / geospatial charts. Out of scope.

## BDD Scenarios

```
Scenario: SVG bar chart renders from a ReportView dataset
  Given OrderRevenueReport with rows=[Group("sku")] values=[Sum("amount")]
  And   a Chart(BarChart, report=OrderRevenueReport, mode="svg") widget
  When  GET /admin/reports/orders-revenue/chart returns the widget fragment
  Then  the body contains "<svg" with role="img" and aria-label "Orders revenue"
  And   the bar count equals the distinct sku count

Scenario: Chart.js mode renders a canvas with a data payload
  Given the same widget with mode="chartjs"
  When  the fragment renders
  Then  the body contains "<canvas data-testid=\"chart-orders-revenue\">"
  And   the body contains a <script type="application/json" data-chart-data=\"orders-revenue\"> with the dataset

Scenario: stacked bar chart renders one stack per column dimension
  Given the report has cols=[Group("status")] values=[Sum("amount")]
  And   the chart type is StackedBarChart
  When  the chart renders
  Then  the SVG has one <g class="stack"> per distinct status
  And   each bar's total equals SUM(amount) for that sku across all statuses

Scenario: chart fragment lazy-loads via HTMX in a host template
  Given a panel template referencing the chart with hx-get and hx-trigger="revealed once"
  When  the host page renders
  Then  the GET /admin/reports/orders-revenue/chart is NOT issued at first paint
  And   the GET fires only when the chart container scrolls into view

Scenario: SVG chart includes accessible data table fallback
  When  the SVG fragment renders
  Then  the body contains a <details data-testid="chart-data-table-orders-revenue"> with a <table> of (label, value) rows
  And   the table is in DOM order after the SVG so screen readers reach it

Scenario: chart respects the report's filter context
  Given the same chart and a CurrentPeriodDefault filter
  When  the chart is requested with ?status=late
  Then  the rendered bars reflect only the filtered subset
  And   the dataset shape matches GET /admin/reports/orders-revenue/?status=late
```

## Design

### Architecture

```
widgets/charts.py            — NEW: BarChart, LineChart, StackedBarChart, PieChart, Chart wrapper
templates/widgets/charts/    — bar.svg.html, line.svg.html, stacked_bar.svg.html, pie.svg.html, chartjs.html
templates/widgets/chart_fallback.html  — accessible <details><table>
views/dynamic.py             — minor: chart fragment route on each ReportView ("/chart")
static/vendor/chart-js/      — vendored chart.umd.js (small footprint, only loaded when mode="chartjs")
```

The `Chart` wrapper is a small Python class consumed by Jinja:

```python
class Chart:
    def __init__(
        self,
        kind: type[BarChart | LineChart | StackedBarChart | PieChart],
        *,
        report: type[ReportView],
        mode: Literal["svg", "chartjs"] = "svg",
        title: str | None = None,
        height: int = 280,
    ): ...

    def fragment_url(self) -> str: ...  # f"/admin/reports/{slug}/chart"
```

In templates, an admin author writes:

```jinja
{{ chart(BarChart, report=OrderRevenueReport, mode="chartjs") }}
```

…or, more typically, lets the report's auto-generated chart render via
`{% include "widgets/charts/auto.html" %}` on the report detail page.

### Data Model Changes

No DB changes.

### API / Protocol Changes

- New chart-fragment route per `ReportView`:
  `GET /admin/reports/{slug}/chart` → HTML fragment (SVG or Chart.js canvas).
- `Chart` widget exported from `hyperadmin.widgets`.
- Chart classes (`BarChart`, etc.) exported from `hyperadmin.widgets.charts`.

### Configuration Changes

`Admin()` gains `chart_mode: Literal["svg", "chartjs"] = "svg"` as the default
when a report's chart doesn't specify one. No env var.

## Edge Cases & Error Handling

| Case | Handling |
|---|---|
| Report returns empty dataset | SVG renders an axis frame with "No data" label; Chart.js canvas renders empty axes |
| `PieChart` with negative values | values clamped to 0 with a warning logged once per chart per process |
| `StackedBarChart` with `cols=[]` | falls back to plain `BarChart` (logs once) |
| Long category labels in SVG | truncated mid-character with ellipsis at a configurable width (default 18 chars) |
| Chart.js mode requested but static asset missing | server-rendered SVG fallback rendered; log at WARNING |
| HTMX request lazy-load with `revealed once` | endpoint serves fragment only on visible trigger; no eager prefetch |
| Filter querystring passed through | forwarded to the underlying `ReportView` request unchanged |

## Migration & Backward Compatibility

Additive. No existing surface changes. The `chart_mode` default is `svg`, so
existing reports (none yet exist) and admins that don't use charts pay zero
cost.

## Open Questions

- [ ] Vendor Chart.js (UMD bundle, ~70KB gzip) or load from a public CDN? Proposal: vendor — air-gapped deployments matter; one extra file in `static/`.
- [ ] Should the SVG palette use CSS variables for colours (`--ha-chart-1` … `--ha-chart-7`) or hard-code? Proposal: CSS variables — consumers can override without forking templates.
- [ ] Should the data-table fallback be on by default or opt-in? Proposal: on by default — accessibility wins over visual purity.

## Decision Log

| Decision | Rationale | Alternatives considered |
|---|---|---|
| Default to SVG, opt into Chart.js | No JS for the common case; interactivity available when needed | Chart.js for everything (bundle bloat); D3 (steeper API surface, build pipeline) |
| Charts live under `widgets/` not `reports/` | They are presentation primitives reusable outside reports (e.g. a stat in a panel) | `reports/charts.py` (couples; can't reuse) |
| Bind charts to a `ReportView` by class reference | Single source of truth — chart can't drift from the table | Bind to raw dataset / dict (fragile across changes) |
| Vendor Chart.js (when mode="chartjs") | Predictable in air-gapped CI and on-prem | CDN (network dependency); custom canvas charts (too much work) |
| Per-report `/chart` fragment route | Trivial HTMX integration; cacheable independently of the table | One mega route returning JSON consumed by browser JS (loses server-rendered SVG path) |
