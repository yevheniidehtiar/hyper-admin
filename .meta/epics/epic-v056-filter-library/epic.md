---
type: epic
id: ep-v056-fl-01
title: "epic(filters): filter library with saved views"
status: todo
priority: high
owner: null
labels:
  - size:L
  - planned
  - backend
  - frontend
  - upstream-readiness
  - H12
milestone_ref:
  id: v056-dpfl-01
created_at: 2026-05-11T00:00:00Z
updated_at: 2026-05-11T00:00:00Z
---

## Overview

Implements upstream readiness capability **H12**: new
`src/hyperadmin/filters/` package with six built-in filters
(`DateRangeFilter`, `MultiFKFilter`, `MultiChoiceFilter`, `BooleanFilter`,
`IsOwnerFilter`, `CurrentPeriodDefault`); querystring-state HTMX list view
with `<tbody>` swap and `HX-Push-Url`; per-user saved views persisted in a
new `hyperadmin_saved_view` table. Backward compatible with the legacy
`list_filter: list[str]` syntax.

**SDD:** [`docs/specs/filter-library.md`](../../../docs/specs/filter-library.md)
(required — new top-level module + new DB table).

## Tracks

### Track A: Filter package (core)
- `filters/base.py` — `FilterDef` protocol, render/parse/apply hooks.
- `filters/date.py`, `filters/relation.py`, `filters/choice.py`, `filters/boolean.py` — six concrete filters.
- `core/filters_compat.py` — adapter that wraps legacy string entries.
- `AdminOptions.list_filter` widened to `list[FilterDef | str]`.

### Track B: List view + saved views (views + storage)
- `views/dynamic.py:list_view` passes filter sidebar context; applies filters in order.
- HTMX-aware `<tbody>` swap with `HX-Push-Url`.
- `SavedView` SQLModel + Alembic migration (`hyperadmin_saved_view`).
- Saved-view endpoints (GET/POST/DELETE), scoped to `request.user.id`.

### Track C: Templates + E2E (frontend)
- `templates/components/filter_sidebar.html` and `saved_views.html`.
- `templates/list.html` — sidebar slot.
- `data-testid`: `filter-{slug}`, `filter-{slug}-gte`, `filter-{slug}-lte`, `saved-view-{id}`, `save-view-btn`.
- E2E covering all eight scenarios in the SDD.

## Scenarios

See SDD `## BDD Scenarios` (eight scenarios: legacy compat, DateRange render,
HTMX swap, IsOwner, CurrentPeriodDefault, saved-view create/load, cross-user
isolation).

## Acceptance Criteria

- [ ] `filters/` package with six built-in filters
- [ ] `FilterDef` protocol with render/parse/apply hooks
- [ ] Legacy `list[str]` config still works (no breaking change)
- [ ] HTMX `<tbody>` swap with `HX-Push-Url`
- [ ] `hyperadmin_saved_view` table created via Alembic
- [ ] Saved-view endpoints scoped to current user (no cross-user leakage)
- [ ] `IsOwnerFilter` reuses `ObjectPermissionChecker`
- [ ] `CurrentPeriodDefault` redirects to canonical URL on first load
- [ ] Eight E2E scenarios pass
- [ ] `poe lint` and `poe test` pass

## Blocked by

- `reviewspec-approve-sdd-filter-library`

## Parent

- Milestone: `v056-detail-panels-filter-library`
- Tracking: `epic-upstream-readiness` (H12)
