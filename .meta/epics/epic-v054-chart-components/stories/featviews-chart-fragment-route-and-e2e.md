---
type: story
id: st-v054-charts-03
title: "feat(views+e2e): chart fragment route + Playwright suite"
status: todo
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
updated_at: 2026-05-11T00:00:00Z
---

## Summary

Register a chart fragment route per `ReportView`
(`GET /admin/reports/{slug}/chart`). Forward filter querystring to the
underlying report so chart and grid stay in sync. Cover the six SDD
scenarios in Playwright (SVG, Chart.js, stacked bar, lazy-load, a11y
fallback, filter context).

**Spec:** [`docs/specs/chart-components.md`](../../../../docs/specs/chart-components.md)

## Files to Change

- **Modified:** `src/hyperadmin/reports/view.py` — `chart_view` handler
- **Modified:** `src/hyperadmin/core/app.py` — register the chart route alongside the report grid
- **New:** `tests/e2e/test_chart_components.py`

## Scenarios → Tests

| Scenario | Test function |
|---|---|
| SVG bar chart renders from a ReportView dataset | `test_svg_bar_chart_renders_from_report` |
| Chart.js mode renders a canvas with a data payload | `test_chartjs_mode_renders_canvas_with_payload` |
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
