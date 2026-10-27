---
type: story
id: st-v054-olap-01
title: "feat(reports): aggregates, crosstab, time-bucketing core"
status: done
priority: high
assignee: null
labels:
  - size:L
  - planned
  - backend
  - upstream-readiness
  - H14
estimate: null
epic_ref:
  id: ep-v054-olap-01
created_at: 2026-05-11T00:00:00Z
updated_at: 2026-10-18T00:00:00Z
---

## Summary

Stand up the first-party plugin `hyperadmin-reports` (uv workspace member at
`plugins/hyperadmin-reports/`, import package `hyperadmin_reports`) with `ReportView`, the six aggregates, the
crosstab pivot builder, and `TimeBucket` (including the `auto` resolver).
Implementation is data-layer first — no routes / templates / exports yet.

**Spec:** [`docs/specs/olap-reporting.md`](../../../../docs/specs/olap-reporting.md)

## Files to Change

- **New:** `plugins/hyperadmin-reports/pyproject.toml` — dist `hyperadmin-reports`, entry point `hyperadmin.plugins: reports`
- **New:** `plugins/hyperadmin-reports/src/hyperadmin_reports/plugin.py` — stub `ReportsPlugin`
- **Modified:** root `pyproject.toml` / `uv.lock` — `[tool.uv.workspace]`, plugin in the dev group; lint/type/test/coverage cover `plugins/`
- **New:** `plugins/hyperadmin-reports/src/hyperadmin_reports/__init__.py`
- **New:** `plugins/hyperadmin-reports/src/hyperadmin_reports/aggregates.py`
- **New:** `plugins/hyperadmin-reports/src/hyperadmin_reports/view.py`
- **New:** `plugins/hyperadmin-reports/src/hyperadmin_reports/crosstab.py`
- **New:** `plugins/hyperadmin-reports/src/hyperadmin_reports/bucketing.py`
- **New:** `plugins/hyperadmin-reports/tests/test_reports_core.py`

## Scenarios

```
Scenario: Sum aggregate compiles to SUM(field)
  Given Sum(field="amount")
  When  .sql(dialect="postgresql") is called
  Then  the result is "SUM(\"amount\")"

Scenario: pivot builder pivots (sku, month) → row × col grid
  Given a flat result [(sku=A, month=2026-01, total=10), (sku=A, month=2026-02, total=20), (sku=B, month=2026-01, total=5)]
  When  pivot(rows=["sku"], cols=["month"], value="total") runs
  Then  the grid maps {("A","2026-01"): 10, ("A","2026-02"): 20, ("B","2026-01"): 5}

Scenario: auto bucketing picks quarter for 365-day range
  Given TimeBucket("created_at", period="auto") and range 2025-01-01 .. 2025-12-31
  When  resolve_period(range) is called
  Then  the result is "quarter"
```

## Acceptance Criteria

- [x] Six aggregates implemented; each has a per-dialect SQL stub
- [x] `ReportView.run()` executes the grouped query and returns a flat result set
- [x] Pivot builder handles missing cells (None / zero per aggregate convention)
- [x] `TimeBucket("...", period="auto")` resolver matches SDD thresholds
- [x] Public exports from `hyperadmin_reports`
- [x] Unit tests cover all three scenarios + per-aggregate SQL
- [x] `poe lint` and `poe test:unit` pass

## Blocked by

- `reviewspec-approve-sdd-olap-reporting`

## Parent

- Epic: `epic-v054-olap-reporting`
