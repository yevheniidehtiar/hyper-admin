# SDD: Chart Components (`hyperadmin.widgets.charts`)

| Field | Value |
|---|---|
| Author | Claude Code |
| Status | Approved (revised 2026-10-17: server-rendered SVG only, aligned with the design system) |
| Issue | TBD |
| Milestone | v0.5.4 — Reporting & Charts |
| Created | 2026-05-11 |
| Last updated | 2026-10-17 |

---

## Revision note (2026-10-17)

The project owner decided: **no Chart.js, ever.** Charts are SVG generated on the backend and
built from the design system (`docs/design/system/components/Chart/README.md` + `preview.html`,
tokens in `docs/design/system/tokens.css`, component CSS in
`docs/design/system/components/bundle.css`). Where this spec and the design system disagree, the
**design system wins**. This revision therefore:

- removes the Chart.js mode, the vendored UMD bundle, `Admin(chart_mode=...)` and the optional
  interactive layer (the design system's "optional interactive layer" is dropped with it: tooltips,
  focus and the period switch already work without client-side chart code);
- aligns the primitives with the design system: **line, bar, stacked bar, sparkline** plus the
  **chart frame**;
- drops `PieChart`: the design system defines no pie or donut component, its palette and marks are
  specified for x/y plots only, and part-to-whole comparisons read more accurately as a stacked
  bar or a sorted bar chart. A pie can come back only after the design system defines one;
- resolves the Open Questions (see the Decision Log);
- cancels `featwidgets-chartjs-mode-and-vendor`.

## Problem

The H15 upstream check requires a chart bound to the same OLAP dataset H14 produces. HyperAdmin
has no chart primitives. Consumers bolt on chart libraries inconsistently, and dashboards diverge
visually and behaviourally from the rest of the admin.

We want a built-in surface that renders every chart as server-side SVG from the design system,
needs no JavaScript to show a chart, and binds declaratively to a `ReportView` from H14 so charts
and tables share the same data path.

## Goals

- Module `src/hyperadmin/widgets/` with `charts.py`: `LineChart`, `BarChart`, `StackedBarChart`,
  `Sparkline`, plus `Series` and `PeriodOption` value types.
- The chart classes take **already-aggregated, already-thinned** series and compute all geometry
  server-side: y scale and round ticks (zero always in the domain), x positions and bands, line
  paths (gaps for missing values), bar and segment rectangles, tooltip boxes, end-of-line labels,
  x-label thinning and truncation.
- Jinja macros in `templates/components/charts/`: `frame.html`, `line.html`, `bar.html`,
  `stacked_bar.html`, `sparkline.html` (+ shared `_svg.html`), following the design-system README.
- Accessibility per the design system: `<title>` + `<desc>`; `role="group"` with
  `aria-labelledby` / `aria-describedby` when the plot holds focusable points (line, bar, stacked
  bar), `role="img"` (or `aria-hidden` when decorative) for the sparkline; one focusable hit area
  per x position with every value in `aria-label`; tooltips on hover, keyboard focus and tap;
  a `<details class="ha-details">` "Show as table" fallback after the SVG.
- Loading (skeleton with `aria-busy`), no-data (empty state with the chart icon and the reason) and
  error (danger text + Retry that re-requests the fragment) states in the same frame.
- HTMX-loaded chart fragment so the same chart can appear standalone, inside a detail panel
  (v0.5.6), or inside a future dashboard (route lands in `featviews-chart-fragment-route-and-e2e`).

## Non-Goals

- Any client-side charting library or "interactive mode". No Chart.js, no vendored chart bundle.
- Pie / donut charts (not in the design system; see the revision note).
- Data aggregation or thinning inside the chart classes: the view (or `ReportView`) hands over
  points ready to draw.
- A full dashboard composer, real-time charts (v0.6.0), drill-down, map/geospatial charts.

## BDD Scenarios

```
Scenario: BarChart renders one bar per category
  Given a dataset [(A, 10), (B, 20), (C, 30)]
  When  the bar macro renders
  Then  the SVG contains exactly three focusable <rect class="f1"> bars labelled "A: 10" … "C: 30"

Scenario: long category label is truncated with ellipsis
  Given a category label "supercalifragilisticexpialidocious" (> 18 chars)
  When  the chart renders at the default width
  Then  the label's <tspan> ends with "…" and the full label is kept in the label's <title>

Scenario: SVG chart includes accessible data table fallback
  When  the chart frame renders
  Then  the body contains <details data-testid="chart-data-table-{key}"> with one row per x label
  And   the table is in DOM order after the SVG so screen readers reach it

Scenario: a point's tooltip appears on keyboard focus
  Given a line chart in a chart frame
  When  the hit area for one month receives keyboard focus
  Then  that month's tooltip is visible and the other tooltips stay hidden

Scenario: stacked bar chart renders one stack per x label
  Given a StackedBarChart with series Services, Licences, Other
  When  the chart renders
  Then  the SVG has one <g class="stack"> per x label, segments separated by a 1px surface line
  And   each stack's hit area reads "Q1: Services 120, Licences 40, Other 20"

Scenario: chart frame states
  When  the frame renders with state="loading" | no data | state="error"
  Then  it shows a skeleton with aria-busy | the empty state with the reason | danger text + Retry

Scenario: SVG bar chart renders from a ReportView dataset            (chart-route item)
  Given OrderRevenueReport with rows=[Group("sku")] values=[Sum("amount")]
  When  GET /admin/reports/orders-revenue/chart returns the frame fragment
  Then  the bar count equals the distinct sku count

Scenario: chart fragment lazy-loads via HTMX in a host template       (chart-route item)
  Given a panel template referencing the chart with hx-get and hx-trigger="revealed once"
  Then  the GET fires only when the chart container scrolls into view

Scenario: chart respects the report's filter context                  (chart-route item)
  When  the chart is requested with ?status=late
  Then  the rendered bars reflect only the filtered subset
```

## Design

### Architecture

```
widgets/__init__.py            — public surface: LineChart, BarChart, StackedBarChart, Sparkline,
                                 Series, PeriodOption, Chart (type alias of the framed kinds)
widgets/charts.py              — chart classes: validation, scale, geometry
widgets/_marks.py              — positioned marks (Tick, AxisLabel, LinePath, Rect, Tooltip, …)
widgets/_scale.py              — nice_scale, tick values, number formatting, truncation
templates/components/charts/   — frame.html, line.html, bar.html, stacked_bar.html,
                                 sparkline.html, _svg.html (shared <svg>, axes)
static/css/_charts.css         — ha-chart, ha-spark, ha-chartframe__tools, ha-seg, ha-legend,
                                 ha-details, ha-skel (imported from hyperadmin.css)
views/…                        — chart fragment route (later item, not in this change)
```

Chart colours come only from the existing tokens `--ha-chart-1` … `--ha-chart-6`,
`--ha-chart-grid`, `--ha-chart-axis` (light + dark already in `_tokens.css` / `_dark-mode.css`,
values from `docs/design/system/tokens.css`), so consumers retheme without forking templates.

```python
from hyperadmin.widgets import LineChart, PeriodOption, Series

chart = LineChart(
    "revenue",                       # becomes data-testid="chart-revenue" and element ids
    title="Revenue and costs, last 12 months",
    desc="Revenue grew from €42k to €71k; costs rose more slowly.",   # one-sentence takeaway
    labels=["Nov", "Dec", ...],      # x labels, already formatted for the locale
    series=[Series("Revenue", [42, 45, ...]), Series("Costs", [30, 31, ...])],
    x_title="Month",                 # first column of the table fallback
    format_value=lambda v: f"€{v:g}k",
    format_tick=lambda v: f"€{v:g}k",
)
```

```jinja
{%- from "components/charts/frame.html" import chart_frame -%}
{{ chart_frame(chart, caption="Last 12 months · EUR", periods=[
     PeriodOption("6M", url_6m), PeriodOption("12M", url_12m, active=True)]) }}
```

Geometry rules (from the design-system preview, 800×240 design width; 44/16/12/28 px margins):

| Element | Rule |
|---|---|
| Y scale | round steps (1, 2, 2.5, 5 × 10ⁿ), about four intervals, zero always included |
| Line | 2px path per series, series 2 also dashed `6 4`; missing values break the line |
| Line x labels | thinned to ≥ 96px apart, anchored at the last point |
| End labels | at the line end when ≤ 2 series; moved below on collision; else the legend |
| Bar | 60 % of the band, `rx=3`, focusable, value label above when it fits |
| Stacked bar | segments `f1…f6`, 1px `ha-surface-raised` separator, one hit area per stack |
| Tooltip | `<g>` with transparent hit rect (`tabindex=0`, full `aria-label`), point, `.tip` box that flips left near the end |
| Sparkline | 200×40, min–max scaled, last point marked, decorative unless titled |
| Labels | truncated to the room they get (max 18 chars) with "…", full text in `<title>` |
| RTL | the frame mirrors; the plot and the table fallback stay `direction: ltr` |

Validation: the key must be an identifier (`[A-Za-z0-9][A-Za-z0-9_-]*`); 1–6 series (the palette
has six slots); each series has one value per label; `BarChart` takes exactly one series;
`StackedBarChart` values must be ≥ 0.

### Data Model Changes

No DB changes.

### API / Protocol Changes

- `hyperadmin.widgets` exports `LineChart`, `BarChart`, `StackedBarChart`, `Sparkline`, `Series`,
  `PeriodOption`, `Chart`.
- Chart fragment route `GET /admin/reports/{slug}/chart` → the frame HTML fragment (later item).

### Configuration Changes

None. (`Admin(chart_mode=...)` is dropped.)

## Edge Cases & Error Handling

| Case | Handling |
|---|---|
| Every value missing / no labels | frame renders the no-data state with the view's reason |
| Some values missing | line breaks at the gap; that x position has no hit area if all series miss it; table shows "—" |
| Negative values | bars hang below the zero line, value label underneath; `StackedBarChart` rejects them |
| All values equal (or zero) | the scale still spans one round step so the axis is drawable |
| More than 6 series | `ValueError` — the design system has six categorical colours |
| Long category labels | truncated to the room per label (≤ 18 chars) with "…", full text in `<title>` |
| Narrow bars | value labels that do not fit the band are omitted (the hit area still reads the value) |
| Query error / timeout | frame `state="error"` with the message and a Retry button re-requesting the fragment |
| Slow query | frame `state="loading"`: skeleton with the chart's aspect ratio and `aria-busy` |
| Untrusted labels / names | Jinja autoescape; no `|safe` on chart text |

## Migration & Backward Compatibility

Additive. No existing surface changes; nothing loads unless a template imports a chart macro.

## Open Questions

All resolved — see the Decision Log.

- [x] Vendor Chart.js or load it from a CDN? → Neither: no Chart.js at all (owner decision).
- [x] CSS variables or hard-coded colours? → CSS variables, the design-system tokens
      `--ha-chart-1` … `--ha-chart-6` (six slots, not seven) + `--ha-chart-grid` / `--ha-chart-axis`.
- [x] Data-table fallback on by default or opt-in? → On by default, as the design system's
      "Show as table" `<details>` after every framed chart.

## Decision Log

| Decision | Rationale | Alternatives considered |
|---|---|---|
| Server-rendered SVG only, no Chart.js | Owner decision: no client chart library; charts follow the design system and work without JavaScript | Chart.js opt-in mode (rejected 2026-10-17); D3 (build pipeline) |
| Design system wins over this spec | Single visual source of truth for every component | Spec-local styling |
| Primitives: line, bar, stacked bar, sparkline + frame | Exactly the set the design system defines | Pie chart (not in the design system; part-to-whole reads better as stacked / sorted bars) |
| Geometry computed in Python, macros only print it | Testable without a browser; templates stay declarative | Arithmetic in Jinja (float drift, untestable) |
| Charts take aggregated, thinned points | Aggregation belongs to `ReportView`; the chart stays a presentation primitive | Chart-side aggregation |
| Palette via CSS variables, six slots | Matches the tokens; dark mode and consumer overrides for free | Hard-coded colours; a seventh colour |
| Data-table fallback on by default | Accessibility over visual purity; design-system requirement | Opt-in |
| Charts live under `widgets/`, not `reports/` | Reusable outside reports (stat-card sparkline, panels) | `reports/charts.py` |
| Bind charts to a `ReportView` by class reference (route item) | Chart can't drift from the table | Raw dataset / dict |
| Per-report `/chart` fragment route (route item) | Trivial HTMX integration; cacheable independently of the table | JSON endpoint + browser rendering |
