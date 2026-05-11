---
type: story
id: st-v056-fl-00
title: "review(spec): approve SDD for filter library"
status: todo
priority: high
assignee: null
labels:
  - size:S
  - planned
  - needs-human
  - upstream-readiness
  - H12
estimate: null
epic_ref:
  id: ep-v056-fl-01
created_at: 2026-05-11T00:00:00Z
updated_at: 2026-05-11T00:00:00Z
---

## Summary

**Human gate** — review and approve `docs/specs/filter-library.md` before
implementation sub-tasks may start.

## Checklist

- [ ] Six built-in filters cover the H12 acceptance check
- [ ] `filters/` as a top-level module (not under `core/`) — boundary acceptable
- [ ] Legacy `list[str]` retained — backward compatible
- [ ] `hyperadmin_saved_view` schema acceptable; Alembic forward-only migration acceptable
- [ ] Per-user scoping policy correct (no shared views in v0.5.6)
- [ ] HTMX swap of `<tbody>` (not full list) — confirmed
- [ ] Open Questions resolved (multi-owner-field, redirect strategy, sidebar load)

## Open Questions to resolve

1. `IsOwnerFilter` — single or multi owner fields?
2. `CurrentPeriodDefault` — redirect with `HX-Push-Url` or hidden inputs only?
3. Saved-views sidebar — render server-side or HTMX-load?

## Parent

- Epic: `epic-v056-filter-library`
