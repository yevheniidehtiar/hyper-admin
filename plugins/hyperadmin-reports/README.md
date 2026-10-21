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
| `GET {prefix}/reports/{slug}/export.csv` | `hyperadmin:report-export-csv` | UTF-8 CSV (no BOM), attachment, totals included |
| `GET {prefix}/reports/{slug}/export.xlsx` | `hyperadmin:report-export-xlsx` | XLSX (`openpyxl` write-only): a "Filters used" cover sheet, then the grid with its totals |

All three take `?period=auto|day|week|month|quarter|year`, which overrides the declared period
of the report's time buckets for that request (`ReportView.run(period=...)`); the page's export
links carry the current query string, so a download matches what is on screen. With `auto`, the
page says which bucket it picked and why ("Auto: quarter, for a 12-month range").

Totals exist for `Sum`, `Count`, `Min` and `Max` (`Aggregate.totals`); `StringAggComma` and
`Many2One` show none. A missing bucket renders as "—" ("no data" for screen readers), rows that
add up to zero print `0`.

Each report route requires the report's codename (`view_report_{slug}` with `-` → `_`, or
`ReportView.permission`), checked by the same permission checker the admin's model views use;
a user who lacks it gets a 403 card naming the permission to ask for (`data-testid="report-forbidden"`).
Without auth every report is open.

The package is discovered through the `hyperadmin.plugins` entry point (`reports`).
Design: [`docs/specs/olap-reporting.md`](../../docs/specs/olap-reporting.md).
