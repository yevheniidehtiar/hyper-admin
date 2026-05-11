---
type: story
id: st-v054-olap-00
title: "review(spec): approve SDD for OLAP reporting"
status: todo
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
updated_at: 2026-05-11T00:00:00Z
---

## Summary

**Human gate** — review and approve `docs/specs/olap-reporting.md` before
implementation sub-tasks may start.

## Checklist

- [ ] H14 scope satisfied (aggregates, crosstab, bucketing, CSV+XLSX, cache seam)
- [ ] Non-goals defer drill-down, self-service builder, scheduled refresh
- [ ] Route layout `/admin/reports/{slug}/...` confirmed
- [ ] Permission codename scheme `view_report_{slug}` confirmed
- [ ] CSV + XLSX both required (not CSV-only)
- [ ] Auto-bucketing thresholds reasonable
- [ ] Open Questions resolved (route nesting, Many2One render, XLSX cover sheet)

## Open Questions to resolve

1. Top-level `/admin/reports/` vs nested under model?
2. `Many2One` aggregate — render display or pk?
3. XLSX "Filters used" cover sheet — include?

## Parent

- Epic: `epic-v054-olap-reporting`
