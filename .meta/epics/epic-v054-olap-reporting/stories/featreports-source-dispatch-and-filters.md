---
type: story
id: st-v054-olap-02
title: "feat(reports): source dispatcher and fact-table cache seam"
status: done
priority: high
assignee: null
labels:
  - size:S
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

Add `FactTableSource` and the source dispatcher: when a `ReportView` declares
a cache, the dispatcher reads from the fact table instead of the live query
with no calling-code change. `ReportView.run(where=[...])` accepts SQLAlchemy
clauses (applied before grouping) as the seam the v0.5.6 filter pipeline plugs
into.

Filter integration (the former third scenario) was cut on 2026-10-18 because it
depends on the v0.5.6 filter library (`FilterDef`); it moved to
`featreports-filter-integration`.

**Spec:** [`docs/specs/olap-reporting.md`](../../../../docs/specs/olap-reporting.md)

## Files to Change

- **New:** `plugins/hyperadmin-reports/src/hyperadmin_reports/cache.py`
- **Modified:** `plugins/hyperadmin-reports/src/hyperadmin_reports/view.py` — source dispatcher in `.run()`, `where` seam, `register_report` validator
- **New:** `plugins/hyperadmin-reports/tests/test_reports_cache.py` — cache + dispatcher coverage

## Scenarios

```
Scenario: cache source replaces live query
  Given ReportView.cache = FactTableSource(model=OrderRevenueFact)
  When  .run() executes
  Then  the executed query targets OrderRevenueFact
  And   the result equals the live-query reference

Scenario: cache validation rejects missing columns
  Given a fact table missing the "sku" column referenced in rows
  When  register_report() runs
  Then  ValueError is raised: "FactTableSource missing column 'sku'"
```

## Acceptance Criteria

- [x] `FactTableSource` implemented; live-query default preserved
- [x] Column-shape validation at `register_report` time
- [x] `where` clause seam in `ReportView.run()` for the filter pipeline
- [x] Unit tests for both scenarios
- [x] `poe lint` passes

## Blocked by

- `featreports-aggregates-and-crosstab-core`

## Parent

- Epic: `epic-v054-olap-reporting`
