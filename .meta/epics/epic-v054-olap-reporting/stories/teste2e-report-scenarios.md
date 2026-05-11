---
type: story
id: st-v054-olap-04
title: "test(e2e): report scenarios via Playwright"
status: todo
priority: high
assignee: null
labels:
  - size:M
  - planned
  - tests
  - upstream-readiness
  - H14
estimate: null
epic_ref:
  id: ep-v054-olap-01
created_at: 2026-05-11T00:00:00Z
updated_at: 2026-05-11T00:00:00Z
---

## Summary

Cover the eight SDD scenarios end-to-end. Use the `examples/full-demo/`
generic `Order/Product/Supplier` seed data so the qualification check is
reproducible without consumer-specific schema.

## Files to Change

- **New:** `tests/e2e/test_olap_reporting.py`
- **Modified:** `tests/e2e/conftest.py` — seed for `OrderRevenueReport` if missing

## Scenarios → Tests

| Scenario | Test function |
|---|---|
| report registers and lists in the admin nav | `test_report_registers_in_admin_nav` |
| sum aggregate over one row group renders a grid | `test_sum_aggregate_renders_grid` |
| time-bucketed crosstab renders rows × month columns | `test_time_bucketed_crosstab_renders` |
| auto bucketing picks quarter for a year-range request | `test_auto_bucketing_picks_quarter` |
| CSV export streams the same dataset | `test_csv_export_streams_dataset` |
| XLSX export streams the same dataset | `test_xlsx_export_streams_dataset` |
| permission codename gates report access | `test_permission_gates_report_access` |
| cached fact-table source replaces the live query | `test_cached_source_replaces_live_query` |

## Acceptance Criteria

- [ ] Eight Playwright tests, one per scenario, mandatory G/W/T comments
- [ ] Accessibility-first locators or `data-testid` only (`report-grid`,
  `report-export-csv`, `report-export-xlsx`)
- [ ] `poe test:e2e -k olap_reporting` passes locally and in CI

## Blocked by

- `featviews-report-routes-and-export`

## Parent

- Epic: `epic-v054-olap-reporting`
