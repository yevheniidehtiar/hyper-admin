---
type: story
id: st-v054-olap-03
title: "feat(views): report routes + CSV/XLSX streaming exports"
status: todo
priority: high
assignee: null
labels:
  - size:M
  - planned
  - backend
  - upstream-readiness
  - H14
estimate: null
epic_ref:
  id: ep-v054-olap-01
created_at: 2026-05-11T00:00:00Z
updated_at: 2026-05-11T00:00:00Z
---

## Summary

Wire `ReportView` into the admin router. Each registered report gets three
routes: HTML grid, CSV export, XLSX export. XLSX uses `openpyxl.write_only`
so a million-cell export does not blow memory. Permission codename
`view_report_{slug}` enforced on each.

**Spec:** [`docs/specs/olap-reporting.md`](../../../../docs/specs/olap-reporting.md)

## Files to Change

- **New:** `src/hyperadmin/reports/export.py` — `stream_csv`, `stream_xlsx`
- **Modified:** `src/hyperadmin/views/dynamic.py` (or new `views/reports.py` if cleaner) — route registration
- **Modified:** `src/hyperadmin/core/app.py` — `Admin.register_report(...)` and discovery
- **Modified:** `tests/unit/test_reports_core.py` — route + export tests

## Scenarios

```
Scenario: HTML grid renders pivot
  When  GET /admin/reports/orders-revenue/
  Then  response is 200 and body has a <table data-testid="report-grid">

Scenario: CSV stream sets attachment disposition
  When  GET /admin/reports/orders-revenue/export.csv
  Then  Content-Type is "text/csv"
  And   Content-Disposition is "attachment; filename=orders-revenue.csv"

Scenario: XLSX stream is openable by openpyxl
  When  GET /admin/reports/orders-revenue/export.xlsx
  Then  Content-Type is the XLSX media type
  And   loading the body with openpyxl.load_workbook yields a single sheet matching the grid

Scenario: permission codename gates report access
  Given the user lacks "view_report_orders_revenue"
  When  GET /admin/reports/orders-revenue/
  Then  response is 403
```

## Acceptance Criteria

- [ ] `Admin.register_report(...)` registers three routes per report
- [ ] CSV streamer with correct headers and BOM-free UTF-8
- [ ] XLSX streamer uses `write_only` workbook
- [ ] Permission check on all three routes
- [ ] Unit tests for all four scenarios
- [ ] `poe lint` and `poe test:unit` pass

## Blocked by

- `featreports-source-dispatch-and-filters`

## Parent

- Epic: `epic-v054-olap-reporting`
