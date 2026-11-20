# hyperadmin-reports

First-party [HyperAdmin](../../README.md) plugin for OLAP / pivot reports.

It ships declarative aggregates (`Sum`, `Count`, `Min`, `Max`, `StringAggComma`, `Many2One`),
time bucketing (`TimeBucket`, `period="auto"`), an in-memory crosstab pivot and
`ReportView.run()` over a caller-supplied `AsyncSession` or session factory.

```python
from hyperadmin_reports import Group, ReportView, Sum, TimeBucket


class OrderRevenueReport(ReportView):
    slug = "orders-revenue"
    model = Order
    rows = [Group("sku")]
    cols = [TimeBucket("created_at", period="month")]
    values = [Sum("amount")]


result = await OrderRevenueReport.run(session)
grid = result.pivot()
```

## Admin pages and exports

Register reports before `Admin(...)` is built (the plugin declares each report's
permission codename while the admin loads it):

```python
from hyperadmin_reports import register_report

register_report(OrderRevenueReport)
admin = Admin(app, engine=engine)
admin.mount("/admin")
```

The admin then serves, inside its own sub-app, with a "Reports" sidebar group (the index,
then one `bar-chart-3` entry per report the user may view):

| Route | Name | Response |
|---|---|---|
| `GET {prefix}/reports/` | `hyperadmin:reports-index` | card grid of the reports the user may view (`description`, what each aggregates) |
| `GET {prefix}/reports/{slug}/` | `hyperadmin:report-detail` | the crosstab (`data-testid="report-grid"`) with year → bucket headers, row / column / grand totals, a null-vs-zero key and the bucket switch |
| `GET {prefix}/reports/{slug}/chart` | `hyperadmin:report-chart` | the report's chart frame (server-rendered SVG, no Chart.js): lazy-loaded above the grid, or embed it in a host template with `hx-get` / `hx-trigger="load"` |
| `GET {prefix}/reports/{slug}/export.csv` | `hyperadmin:report-export-csv` | UTF-8 CSV (no BOM), attachment, totals included |
| `GET {prefix}/reports/{slug}/export.xlsx` | `hyperadmin:report-export-xlsx` | XLSX (`openpyxl` write-only): a "Filters used" cover sheet, then the grid with its totals |

All four take `?period=auto|day|week|month|quarter|year`, which overrides the declared period
of the report's time buckets for that request (`ReportView.run(period=...)`); the page's export
links carry the current query string, so a download matches what is on screen. With `auto`, the
page says which bucket it picked and why ("Auto: quarter, for a 12-month range").

The chart draws the report's first aggregate that has totals: a **line** when a time bucket
runs along the x axis (one line per group), a **bar** for a single group, a **stacked bar** for
rows x columns of groups. It shows at most six series, the top 12 bars or the latest 36
points, and says so in its caption. The fragment takes the page's query string unchanged, so
chart and grid share the period; `?embed=1` (what the page sends) hides the frame's own period
switch. A chart that cannot be drawn, or a failing query, renders the frame's error state
with a 200 status, because HTMX does not swap error responses.

## Filters

A report declares `filters` the way a list view declares `list_filter`: field names (an
exact-match select) or `hyperadmin.filters` definitions. They are applied **before** the
aggregate, as `WHERE` clauses on the table the report reads (the `cache` fact table when one is
set, so that table must carry the filtered columns; `register_report` checks it).

```python
from hyperadmin.filters import DateRangeFilter, IsOwnerFilter


class OrderRevenueReport(ReportView):
    slug = "orders-revenue"
    model = Order
    rows = [Group("sku")]
    cols = [TimeBucket("created_at", period="auto")]
    values = [Sum("amount")]
    filters = [DateRangeFilter(field="created_at"), "status", IsOwnerFilter(owner_fields="owner_id")]


result = await OrderRevenueReport.run(session, filters={"created_at__gte": "2026-02-01"})
```

`run(filters=...)` takes a querystring (a mapping or Starlette `QueryParams`) with the same keys
as list views (`created_at__gte`, `created_at__lte`, `created_at__preset`, `filter_status`,
`sku__in`, `is_owner`); `run(binding=FilterBinding(tz=..., user_key=...))` supplies the display
timezone and the current user's key. Without `filters=` the pipeline is skipped, so existing
callers are unchanged. Input that does not parse is dropped, never sent to the database.

On the page the report gets the list view's filter sidebar (`data-testid="report-filters"`):
presets, inline errors, applied-filter chips (`report-applied-filters`), "Reset". Applying swaps
the page in place and pushes the URL. The grid, the chart fragment and both exports read the same
querystring, after the permission check, so they always agree; the XLSX "Filters used" sheet
lists what was applied. A closed date range on a `TimeBucket(period="auto")` column sizes the
bucket (a year reads by quarter). Select and checklist filters offer the values present in the
report's source (at most 50; a foreign key shows the related rows' names). `period` and `embed`
are the routes' own keys, so a filter may not use them.

Filters narrow what the report's permission already lets a user see; they are not an access
control. A report reads its source table directly, so `ModelAdmin.get_queryset` scoping of the
same model does not apply to it: scope a report with its own permission codename.

Totals exist for `Sum`, `Count`, `Min` and `Max` (`Aggregate.totals`); `StringAggComma` and
`Many2One` show none. A missing bucket renders as "—" ("no data" for screen readers), rows that
add up to zero print `0`.

Each report route requires the report's codename (`view_report_{slug}` with `-` → `_`, or
`ReportView.permission`), checked by the same permission checker the admin's model views use;
a user who lacks it gets a 403 card naming the permission to ask for (`data-testid="report-forbidden"`).
Without auth every report is open.

## Dashboard

Put report numbers, report charts and shortcut links on the admin home page. Register widgets
after their reports and before `Admin(...)` is built; registration order is the default order.

```python
from hyperadmin_reports import (
    ChartWidget,
    QuickAction,
    QuickActionsWidget,
    StatWidget,
    register_report,
    register_widget,
)

register_report(OrderRevenueReport)
register_report(OrdersByMonthReport)
register_widget(StatWidget(OrderRevenueReport))          # grand total of its first aggregate
register_widget(ChartWidget(OrdersByMonthReport))        # the report's chart fragment
register_widget(QuickActionsWidget([
    QuickAction("New order", "order-create-form", permission="add_order"),
    QuickAction("All reports", "reports-index"),
]))
admin = Admin(app, engine=engine)
```

| Widget | Shows | Options |
|---|---|---|
| `StatWidget(report)` | one total of a report aggregate, folded with `Aggregate.total()`; "—" and "No data" without rows | `value="sum_amount"` (the aggregate's `name`; default: the first aggregate with totals), `key`, `title`, `span` |
| `ChartWidget(report)` | the report's chart, loaded from `{prefix}/reports/{slug}/chart?embed=1` | `key`, `title`, `span` (default 2) |
| `QuickActionsWidget(actions)` | links to named admin routes; an action with a `permission` shows only to users who hold it | `key`, `title`, `span` |

A widget's `key` (default `stat-{slug}` / `chart-{slug}` / `quick-actions`) is its identity in
saved layouts; `span` is 1 to 4 grid columns (the grid has four columns on a desktop, two on a
tablet, one on a phone). A bad key, a duplicate key, a span outside 1..4, a report that is not
registered, an aggregate without totals or a report that cannot be charted raises `ValueError`
when the widget is built or registered, not on the first request.

For anything else, subclass `DashboardWidget`:

```python
from hyperadmin_reports import DashboardWidget, WidgetBody, register_widget


class OpenTicketsWidget(DashboardWidget):
    key = "open-tickets"
    title = "Open tickets"

    def permission(self) -> str | None:
        return "view_ticket"

    async def render(self, request, admin) -> WidgetBody:
        return WidgetBody("my_app/open_tickets.html", {"count": await count_open_tickets()})


register_widget(OpenTicketsWidget())
```

**Where it is served.** With at least one widget registered, the dashboard replaces the welcome
page at `{prefix}/` and is also at `{prefix}/dashboard/`. Without widgets nothing changes.

| Route | Name | Response |
|---|---|---|
| `GET {prefix}/dashboard/` | `hyperadmin:dashboard-index` | the dashboard page |
| `GET {prefix}/dashboard/widgets/{key}` | `hyperadmin:dashboard-widget` | one card body (each data widget loads in its own request) |
| `POST {prefix}/dashboard/layout` | `hyperadmin:dashboard-layout` | save the order: form field `widgets`, repeated |
| `POST {prefix}/dashboard/layout/move` | `hyperadmin:dashboard-layout-move` | move one card: `key`, `direction` (`up` / `down`) |
| `POST {prefix}/dashboard/reset` | `hyperadmin:dashboard-reset` | back to the default order |

**Settings.** `Admin(..., plugin_settings={"reports": {...}})` or `HYPERADMIN_REPORTS_*`
environment variables:

| Setting | Default | Meaning |
|---|---|---|
| `dashboard_home` | `True` | serve the dashboard at `{prefix}/`; `False` keeps the welcome page and adds a "Dashboard" link to the "Reports" sidebar group |
| `dashboard_layouts` | `True` | remember each user's order; `False` shows the default order without reorder controls and never touches the layout table |
| `dashboard_prefix` | `"/dashboard"` | prefix of the dashboard page; change it when a model's slug is `dashboard` |

**Permissions.** A `StatWidget` or `ChartWidget` needs its report's codename
(`view_report_{slug}`). A user who lacks it does not get the card, cannot load its fragment
(403) and cannot save an order naming it (400). Without auth every widget shows. A user who
may view none sees an empty state.

**Order.** Signed-in users reorder cards by dragging the handle or with the "Move up" /
"Move down" buttons, which also work from the keyboard and without JavaScript; "Reset layout"
returns to the default order. A widget registered after a user saved an order appears at the
end. Saving needs a signed-in user (`request.state.user_key`) and the layout table below.

**Failures.** A widget whose `render()` raises shows "Widget unavailable" with a Retry button
and is logged with its traceback; the other cards are not affected.

Design: [`docs/specs/dashboard-builder.md`](../../docs/specs/dashboard-builder.md).

## Dashboard layouts

The dashboard remembers each user's widget order in one table the plugin owns,
`hyperadmin_reports_dashboard_layout`. The table is declared on the plugin's own `MetaData`
(`hyperadmin_reports.dashboard_metadata()`), not on `SQLModel.metadata`, so upgrading the
plugin never adds a table to your migrations. Create it when you want saved orders; without
it the dashboard shows the default order, hides the reorder controls and logs one warning.

Without Alembic, create it once at start-up:

```python
from hyperadmin_reports import create_layout_table

await create_layout_table(engine)  # an AsyncEngine or an open AsyncConnection; idempotent
```

With Alembic, add a hand-written revision:

```python
import sqlalchemy as sa
from alembic import op


def upgrade() -> None:
    op.create_table(
        "hyperadmin_reports_dashboard_layout",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_key", sa.String(255), nullable=False),
        sa.Column("dashboard", sa.String(64), nullable=False),
        sa.Column("widgets", sa.JSON(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint(
            "user_key", "dashboard", name="uq_hyperadmin_reports_dashboard_layout"
        ),
    )
    op.create_index(
        "ix_hyperadmin_reports_dashboard_layout_user_key",
        "hyperadmin_reports_dashboard_layout",
        ["user_key"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_hyperadmin_reports_dashboard_layout_user_key",
        table_name="hyperadmin_reports_dashboard_layout",
    )
    op.drop_table("hyperadmin_reports_dashboard_layout")
```

A row holds `user_key` (`request.state.user_key` as text), `dashboard` (always `"home"` today)
and `widgets`, the ordered list of widget keys. To let autogenerate manage the table instead,
add `dashboard_metadata()` to your `target_metadata` list.

The package is discovered through the `hyperadmin.plugins` entry point (`reports`).
Design: [`docs/specs/olap-reporting.md`](../../docs/specs/olap-reporting.md).
