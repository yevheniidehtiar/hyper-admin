---
type: story
id: st-v054-olap-02
title: "feat(reports): source dispatcher, fact-table cache seam, filter integration"
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

Add `FactTableSource` and the source dispatcher: when a `ReportView` declares
a cache, the dispatcher reads from the fact table instead of the live query
with no calling-code change. Wire the report's `filters` list through the
v0.5.6 filter pipeline so a `ReportView` can mount the same sidebar as a
list view.

**Spec:** [`docs/specs/olap-reporting.md`](../../../../docs/specs/olap-reporting.md)

## Files to Change

- **New:** `src/hyperadmin/reports/cache.py`
- **Modified:** `src/hyperadmin/reports/view.py` — source dispatcher in `.run()`
- **Modified:** `tests/unit/test_reports_core.py` — cache + filter coverage

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

Scenario: filters are applied before the aggregate
  Given a DateRangeFilter and a Sum aggregate
  When  .run() executes with {"created_at__gte": "2026-02-01"}
  Then  the SQL WHERE clause includes "created_at >= '2026-02-01'"
  And   the result excludes pre-February rows
```

## Acceptance Criteria

- [ ] `FactTableSource` implemented; live-query default preserved
- [ ] Column-shape validation at `register_report` time
- [ ] Filter parse → apply → run pipeline in `ReportView.run()`
- [ ] Unit tests for all three scenarios
- [ ] `poe lint` passes

## Blocked by

- `featreports-aggregates-and-crosstab-core`

## Parent

- Epic: `epic-v054-olap-reporting`
