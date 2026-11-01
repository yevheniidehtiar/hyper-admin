---
type: story
id: st-v054-charts-03
title: "feat(views+e2e): chart fragment route + Playwright suite"
status: done
priority: high
assignee: null
labels:
  - size:M
  - planned
  - backend
  - tests
  - upstream-readiness
  - H15
estimate: null
epic_ref:
  id: ep-v054-charts-01
created_at: 2026-05-11T00:00:00Z
updated_at: 2026-11-01T00:00:00Z
---

## Summary

Register a chart fragment route per `ReportView`
(`GET /admin/reports/{slug}/chart`). Forward filter querystring to the
underlying report so chart and grid stay in sync. Cover the SDD
scenarios (no Chart.js: dropped) in Playwright (SVG, Chart.js, stacked bar, lazy-load, a11y
fallback, filter context).

**Spec:** [`docs/specs/chart-components.md`](../../../../docs/specs/chart-components.md)

## Files to Change

- **New:** `plugins/hyperadmin-reports/src/hyperadmin_reports/chart_data.py` — report → chart mapping
- **Modified:** `plugins/hyperadmin-reports/src/hyperadmin_reports/routes.py` — `GET {slug}/chart` fragment, lazy slot on the report page
- **New:** `plugins/hyperadmin-reports/src/hyperadmin_reports/templates/reports/chart.html`
- **New:** `tests/e2e/test_chart_components.py`, `tests/e2e/apps/report_charts.py`

## Scenarios → Tests

| Scenario | Test function |
|---|---|
| SVG bar chart renders from a ReportView dataset | `test_svg_bar_chart_renders_from_report` (+ `test_svg_line_chart_renders_from_report`) |
| chart shows no-data and error states | `test_chart_shows_the_no_data_state`, `test_chart_shows_an_error_state_*` |
| stacked bar chart renders one stack per column dimension | `test_stacked_bar_renders_one_stack_per_column` |
| chart fragment lazy-loads via HTMX in a host template | `test_chart_fragment_lazy_loads_via_htmx` |
| SVG chart includes accessible data table fallback | `test_svg_chart_includes_accessible_data_table` |
| chart respects the report's filter context | `test_chart_respects_report_filter_context` |

## Acceptance Criteria

- [ ] Chart route registered alongside each report's grid route
- [ ] Filter querystring forwarded unchanged
- [ ] Six scenarios pass at unit / E2E level
- [ ] Visual snapshots committed
- [ ] `poe lint` and `poe test` pass

## Blocked by

- `featwidgets-chartjs-mode-and-vendor`

## Parent

- Epic: `epic-v054-chart-components`
