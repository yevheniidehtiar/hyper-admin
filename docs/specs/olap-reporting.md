# SDD: OLAP / Pivot Reporting (`hyperadmin.reports`)

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

HyperAdmin has no first-class way to declare an aggregated, pivoted, time-
bucketed report. Consumers reinvent it: hand-written endpoints that
`SELECT`/`GROUP BY` raw SQL, ship ad-hoc CSV exports, and skip the admin's
permission/audit machinery. The H14 upstream check is: "OLAP report
sales-by-SKU × month, quarter bucketing, CSV+XLSX export, charted." Without a
declarative report layer, every consumer carries an ad-hoc copy of this.

## Goals

- New `src/hyperadmin/reports/` package: declarative `ReportView` registered
  on the admin alongside `ModelAdmin`.
- Declarative aggregates: `Sum`, `Count`, `StringAggComma`, `Min`, `Max`,
  `Many2One` (resolves to the related row's display).
- Crosstab dimensions: one row group, N column groups (e.g. row = SKU, cols =
  year/quarter/month).
- Time-series bucketing: `day`, `week`, `month`, `quarter`, `year`, plus
  `auto` that picks based on the requested date range.
- Filter integration: a `ReportView` can declare a filter set via `filters/`
  from v0.5.6 — the H12 sidebar drives the report.
- CSV and XLSX export endpoints, permission-aware (`view_report_{slug}`).
- Cached materialisation seam: a `ReportView` can opt into reading from a
  pre-built fact table without changing the calling code — the dispatcher
  picks the source.

## Non-Goals

- Self-service report builder UI. v0.5.4 ships declarative reports defined in
  code. A drag-and-drop editor is later milestone material.
- Materialised-view refresh scheduling. The cache seam is invocation-only; a
  scheduler is consumer-side.
- Multi-fact joins beyond simple FK-to-display. Composite OLAP cubes are out
  of scope.
- ROLAP query optimisation tuning. The default uses the adapter's `select`
  with `selectinload`; consumers tune at the SQL layer.
- Pivot drill-down to row-level detail. v0.5.4 surfaces aggregates only; a
  "click a cell to see the rows" interaction is deferred.

## BDD Scenarios

```
Scenario: report registers and lists in the admin nav
  Given OrderRevenueReport(ReportView, model=Order, slug="orders-revenue") is registered
  When  the user opens /admin/
  Then  the sidebar has a "Reports" group containing "Orders revenue"
  And   the link targets /admin/reports/orders-revenue/

Scenario: sum aggregate over one row group renders a grid
  Given the report declares rows=[Group("sku")] cols=[] values=[Sum("amount")]
  When  the user opens /admin/reports/orders-revenue/
  Then  the response is a table with one row per distinct sku
  And   the value column equals SUM(amount) per sku

Scenario: time-bucketed crosstab renders rows × month columns
  Given rows=[Group("sku")] cols=[TimeBucket("created_at", period="month")] values=[Sum("amount")]
  And   the dataset spans Jan to Mar 2026
  When  the user opens the report
  Then  the table has columns "2026-01", "2026-02", "2026-03" and SKU rows
  And   each cell equals SUM(amount) for that (sku, month)

Scenario: auto bucketing picks quarter for a year-range request
  Given the same report with cols=[TimeBucket("created_at", period="auto")]
  And   the user filters to 2025-01-01 .. 2025-12-31
  When  the report renders
  Then  the column headers are "2025-Q1" .. "2025-Q4"

Scenario: CSV export streams the same dataset
  When  GET /admin/reports/orders-revenue/export.csv with the same filters
  Then  the response Content-Type is "text/csv"
  And   Content-Disposition is "attachment; filename=orders-revenue.csv"
  And   the first row is the column header

Scenario: XLSX export streams the same dataset
  When  GET /admin/reports/orders-revenue/export.xlsx
  Then  the response Content-Type is "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
  And   opening the file with openpyxl yields the same rows as the CSV

Scenario: permission codename gates report access
  Given user lacks "view_report_orders_revenue"
  When  GET /admin/reports/orders-revenue/
  Then  response is 403

Scenario: cached fact-table source replaces the live query
  Given OrderRevenueReport.cache = FactTableSource(model=OrderRevenueFact)
  When  the report is rendered
  Then  the SQL executed reads from OrderRevenueFact, not Order
  And   the rendered grid equals the live-query reference set
```

## Design

### Architecture

```
reports/                   — NEW top-level package
  __init__.py              — re-exports: ReportView, Group, TimeBucket, Sum, Count, ...
  aggregates.py            — Sum, Count, Min, Max, StringAggComma, Many2One
  view.py                  — ReportView base class + registration
  crosstab.py              — pivot builder (rows × cols → grid)
  bucketing.py             — TimeBucket, auto-period resolver
  export.py                — CSV/XLSX streamers
  cache.py                 — FactTableSource seam
views/dynamic.py           — minor: registry exposes report routes alongside model routes
templates/reports/         — list.html, detail.html, export buttons
```

The dispatch order on a request:

1. Permission check (codename derived from slug).
2. Filter parse (reuses `filters/` from v0.5.6).
3. Source selection — live adapter query vs `FactTableSource`.
4. Aggregate execution.
5. Crosstab assembly.
6. Render: HTML grid, CSV stream, or XLSX stream.

### Data Model Changes

No required DB tables. `FactTableSource` operates on a consumer-owned SQLModel —
HyperAdmin does not create or migrate fact tables.

### API / Protocol Changes

```python
class ReportView:
    slug: str
    label: str
    model: type[SQLModel]
    rows: list[Group | TimeBucket]
    cols: list[Group | TimeBucket]
    values: list[Aggregate]
    filters: list[FilterDef | str] | None = None
    cache: FactTableSource | None = None
    permission: str | None = None     # default f"view_report_{slug}"

class Aggregate(Protocol):
    field: str
    def sql(self, dialect: str) -> str: ...

class Group:
    def __init__(self, field: str, *, label: str | None = None): ...

class TimeBucket:
    def __init__(self, field: str, *, period: Literal["day","week","month","quarter","year","auto"]): ...
```

Routes (per registered `ReportView`):

```
GET /admin/reports/{slug}/             → HTML grid
GET /admin/reports/{slug}/export.csv   → CSV stream
GET /admin/reports/{slug}/export.xlsx  → XLSX stream
```

Reports are registered via `admin.register_report(ReportClass)` mirroring
`admin.register(ModelAdmin)`.

### Configuration Changes

No new `Admin()` arg. No env vars. Reports are discovered via the existing
admin registry pattern.

## Edge Cases & Error Handling

| Case | Handling |
|---|---|
| Empty result set | renders an empty grid with a "No data" cell |
| `TimeBucket(period="auto")` with no date filter | range falls back to the column's min/max in the dataset; if either is null, single-bucket grid |
| Aggregate references unknown field | raised at `register_report` time (`ValueError`) |
| FK in `Group` (`Group("supplier_id")`) | grouped by FK id; column header uses related row's display when joinable, else raw id |
| XLSX export with >1M cells | streamed in chunks via `openpyxl.write_only` (no memory blowup) |
| Filter parse error | report renders with the inline filter-error decoration (same UX as list views) |
| Permission denied | 403 — same template fragment as model views |
| `cache` returns wrong shape | sanity-check at register time: cache's columns must be a superset of `rows + cols + values` |

## Migration & Backward Compatibility

Additive. No existing public API surface changes. The dashboard-builder
milestone is renamed to "Reporting & Charts"; no past commits or PRs are
affected since the milestone has not yet shipped.

## Open Questions

- [ ] Should reports be served under `/admin/reports/` (sibling of model routes) or `/admin/<model>/reports/` (nested)? Proposal: top-level — a report can span multiple models in v0.5.4+ (a `FactTableSource`) so nesting under one model is wrong.
- [ ] Should `Many2One` aggregate render the related row's display or its pk? Proposal: display, falling back to pk if no display available.
- [ ] Should XLSX export include a "Filters used" cover sheet for audit? Proposal: yes — small, helpful for downstream audit trails.

## Decision Log

| Decision | Rationale | Alternatives considered |
|---|---|---|
| `reports/` as a top-level package | Mirrors `filters/` boundary; reports can compose multiple models | Stash under `core/reports/` (couples core); under `views/reports/` (couples to view layer) |
| Pivot in memory after a single grouped query | Predictable, portable across adapters; avoids DB-specific PIVOT syntax | DB-side `PIVOT` (SQL Server) / `crosstab` (Postgres) — non-portable |
| Cache seam at the `ReportView` level | Drop-in fact table swap, no calling-code change | Plumb caching into every aggregate (more surface, less win) |
| CSV + XLSX in v0.5.4 | Both are required by the H14 acceptance check | CSV-only (fails the check); JSON-only (consumer-side conversion burden) |
| Auto bucketing rule: range ≤ 31d → day, ≤ 90d → week, ≤ 366d → month, ≤ 1100d → quarter, else year | Matches operator expectations; predictable | Always month (loses fidelity for short ranges); operator-must-pick (breaks "auto" promise) |
