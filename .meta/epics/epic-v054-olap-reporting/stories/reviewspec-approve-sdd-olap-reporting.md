---
type: story
id: st-v054-olap-00
title: "review(spec): approve SDD for OLAP reporting"
status: done
priority: high
assignee: null
labels:
  - size:S
  - planned
  - needs-human
  - upstream-readiness
  - H14
estimate: null
epic_ref:
  id: ep-v054-olap-01
created_at: 2026-05-11T00:00:00Z
updated_at: 2026-10-17T00:00:00Z
---

## Summary

**Human gate** — review and approve `docs/specs/olap-reporting.md` before
implementation sub-tasks may start.

## Checklist

- [x] H14 scope satisfied (aggregates, crosstab, bucketing, CSV+XLSX, cache seam)
- [x] Non-goals defer drill-down, self-service builder, scheduled refresh
- [x] Route layout `/admin/reports/{slug}/...` confirmed
- [x] Permission codename scheme `view_report_{slug}` confirmed
- [x] CSV + XLSX both required (not CSV-only)
- [x] Auto-bucketing thresholds reasonable
- [x] Open Questions resolved (route nesting, Many2One render, XLSX cover sheet)

## Open Questions to resolve

1. Top-level `/admin/reports/` vs nested under model?
2. `Many2One` aggregate — render display or pk?
3. XLSX "Filters used" cover sheet — include?

## Parent

- Epic: `epic-v054-olap-reporting`
