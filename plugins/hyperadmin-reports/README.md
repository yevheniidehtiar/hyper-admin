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

The admin then serves, inside its own sub-app, with a "Reports" sidebar entry:

| Route | Name | Response |
|---|---|---|
| `GET {prefix}/reports/` | `hyperadmin:reports-index` | reports the user may view |
| `GET {prefix}/reports/{slug}/` | `hyperadmin:report-detail` | HTML grid (`data-testid="report-grid"`) |
| `GET {prefix}/reports/{slug}/export.csv` | `hyperadmin:report-export-csv` | UTF-8 CSV (no BOM), attachment |
| `GET {prefix}/reports/{slug}/export.xlsx` | `hyperadmin:report-export-xlsx` | XLSX (`openpyxl` write-only): a "Filters used" cover sheet, then the grid |

Each report route requires the report's codename (`view_report_{slug}` with `-` → `_`, or
`ReportView.permission`), checked by the same permission checker the admin's model views use.
Without auth every report is open.

The package is discovered through the `hyperadmin.plugins` entry point (`reports`).
Design: [`docs/specs/olap-reporting.md`](../../docs/specs/olap-reporting.md).
