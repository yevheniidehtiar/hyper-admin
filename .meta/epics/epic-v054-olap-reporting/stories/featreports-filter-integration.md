---
type: story
id: st-v054-olap-05
title: "feat(reports): apply the report's filters before the aggregate"
status: todo
priority: medium
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
created_at: 2026-10-18T00:00:00Z
updated_at: 2026-10-18T00:00:00Z
---

## Summary

Wire `ReportView.filters` through the v0.5.6 filter pipeline (parse → apply →
run) so a report mounts the same sidebar as a list view. Split out of
`featreports-source-dispatch-and-filters` on 2026-10-18: it needs the
`FilterDef` API from `epic-v056-filter-library`. The seam already exists —
`ReportView.run(where=[...])` applies SQLAlchemy clauses against
`ReportView.source_model()` before grouping — so this story only translates
parsed filter values into those clauses.

**Spec:** [`docs/specs/olap-reporting.md`](../../../../docs/specs/olap-reporting.md)

## Files to Change

- **Modified:** `plugins/hyperadmin-reports/src/hyperadmin_reports/view.py` — filter parse → `where` clauses in `.run()`
- **Modified:** `plugins/hyperadmin-reports/tests/test_reports_cache.py` (or a new filter test module) — filter coverage

## Scenarios

```
Scenario: filters are applied before the aggregate
  Given a DateRangeFilter and a Sum aggregate
  When  .run() executes with {"created_at__gte": "2026-02-01"}
  Then  the SQL WHERE clause includes "created_at >= '2026-02-01'"
  And   the result excludes pre-February rows
```

## Acceptance Criteria

- [ ] `ReportView.filters` parsed with the v0.5.6 filter library and applied via the `where` seam
- [ ] Filters target the cache's fact table when `cache` is set
- [ ] Unit test for the scenario
- [ ] `poe lint` passes

## Blocked by

- `featreports-source-dispatch-and-filters`
- `epic-v056-filter-library`

## Parent

- Epic: `epic-v054-olap-reporting`
