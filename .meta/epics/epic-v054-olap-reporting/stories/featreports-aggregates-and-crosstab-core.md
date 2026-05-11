---
type: story
id: st-v054-olap-01
title: "feat(reports): aggregates, crosstab, time-bucketing core"
status: todo
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
updated_at: 2026-05-11T00:00:00Z
---

## Summary

Stand up the `reports/` package with `ReportView`, the six aggregates, the
crosstab pivot builder, and `TimeBucket` (including the `auto` resolver).
Implementation is data-layer first — no routes / templates / exports yet.

**Spec:** [`docs/specs/olap-reporting.md`](../../../../docs/specs/olap-reporting.md)

## Files to Change

- **New:** `src/hyperadmin/reports/__init__.py`
- **New:** `src/hyperadmin/reports/aggregates.py`
- **New:** `src/hyperadmin/reports/view.py`
- **New:** `src/hyperadmin/reports/crosstab.py`
- **New:** `src/hyperadmin/reports/bucketing.py`
- **New:** `tests/unit/test_reports_core.py`

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

- [ ] Six aggregates implemented; each has a per-dialect SQL stub
- [ ] `ReportView.run()` executes the grouped query and returns a flat result set
- [ ] Pivot builder handles missing cells (None / zero per aggregate convention)
- [ ] `TimeBucket("...", period="auto")` resolver matches SDD thresholds
- [ ] Public exports from `hyperadmin.reports`
- [ ] Unit tests cover all three scenarios + per-aggregate SQL
- [ ] `poe lint` and `poe test:unit` pass

## Blocked by

- `reviewspec-approve-sdd-olap-reporting`

## Parent

- Epic: `epic-v054-olap-reporting`
