---
type: story
id: st-v056-fl-00
title: "review(spec): approve SDD for filter library"
status: done
priority: high
assignee: null
labels:
  - size:S
  - done
  - needs-human
  - upstream-readiness
  - H12
estimate: null
epic_ref:
  id: ep-v056-fl-01
created_at: 2026-05-11T00:00:00Z
updated_at: 2026-10-20T00:00:00Z
closed_at: 2026-10-20T00:00:00Z
---

## Summary

**Human gate** — review and approve `docs/specs/filter-library.md` before
implementation sub-tasks may start.

## Approval

**Approved by Yevhenii Dehtiar on 2026-10-20.** SDD status moved to `Approved`
in `docs/specs/filter-library.md`. Implementation sub-tasks are now unblocked.

## Checklist

- [x] Six built-in filters cover the H12 acceptance check
- [x] `filters/` as a top-level module (not under `core/`) — boundary acceptable
- [x] Legacy `list[str]` retained — backward compatible
- [x] `hyperadmin_saved_view` schema acceptable; created via `hyperadmin init-db` / host migrations (no Alembic in-tree since v0.5.8)
- [x] Per-user scoping policy correct (no shared views in v0.5.6)
- [x] HTMX swap of `<tbody>` (not full list) — confirmed
- [x] Open Questions resolved (see below)

## Open Questions resolved

1. **`IsOwnerFilter(owner_fields: list[str] | str)`** — one or several owner
   fields; a single field stays the common case.
2. **`CurrentPeriodDefault` redirects with `HX-Push-Url`** so the URL is the
   source of truth.
3. **Saved-views sidebar is rendered with the page** (no HTMX load).

## Parent

- Epic: `epic-v056-filter-library`
