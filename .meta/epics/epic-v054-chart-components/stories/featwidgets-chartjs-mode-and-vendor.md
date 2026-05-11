---
type: story
id: st-v054-charts-02
title: "feat(widgets): Chart.js mode + vendored UMD bundle"
status: todo
priority: medium
assignee: null
labels:
  - size:M
  - planned
  - frontend
  - upstream-readiness
  - H15
estimate: null
epic_ref:
  id: ep-v054-charts-01
created_at: 2026-05-11T00:00:00Z
updated_at: 2026-05-11T00:00:00Z
---

## Summary

Add the `mode="chartjs"` rendering path: `<canvas>` + a JSON payload that the
client-side glue reads to construct the Chart.js instance. Vendor the
Chart.js UMD bundle under `static/vendor/chart-js/`. Falls back to SVG when
the vendor file is missing (logs at WARNING).

**Spec:** [`docs/specs/chart-components.md`](../../../../docs/specs/chart-components.md)

## Files to Change

- **New:** `src/hyperadmin/static/vendor/chart-js/chart.umd.js` (vendored)
- **New:** `src/hyperadmin/static/vendor/chart-js/LICENSE`
- **New:** `src/hyperadmin/templates/widgets/charts/chartjs.html`
- **Modified:** `src/hyperadmin/widgets/charts.py` — mode dispatch
- **Modified:** `src/hyperadmin/core/options.py` — `Admin(chart_mode=...)` default
- **New:** `tests/unit/test_charts_chartjs.py`

## Scenarios

```
Scenario: chartjs mode renders canvas with data payload
  Given a BarChart with mode="chartjs" and dataset [(A,10),(B,20)]
  When  the fragment renders
  Then  the body contains "<canvas data-testid=\"chart-{slug}\">"
  And   a <script type="application/json" data-chart-data="{slug}"> with the dataset

Scenario: missing vendor file falls back to SVG
  Given the vendored chart.umd.js file is absent
  When  the chartjs fragment renders
  Then  the output is the SVG variant
  And   a WARNING is logged with message "Chart.js bundle missing — falling back to SVG"
```

## Acceptance Criteria

- [ ] Chart.js UMD bundle vendored with its LICENSE
- [ ] `mode="chartjs"` renders canvas + JSON payload + script include
- [ ] `Admin(chart_mode=...)` default propagates when widget doesn't specify
- [ ] Fallback path when vendor file missing
- [ ] Two scenarios above covered by unit tests
- [ ] `poe lint` and `poe test:unit` pass

## Blocked by

- `featwidgets-svg-chart-primitives`

## Parent

- Epic: `epic-v054-chart-components`
