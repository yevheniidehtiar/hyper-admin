---
type: story
id: st-v057-pmx-03
title: "feat(templates): matrix grid, object popover, conflict banner"
status: todo
priority: high
assignee: null
labels:
  - size:M
  - planned
  - frontend
  - upstream-readiness
  - H20
estimate: null
epic_ref:
  id: ep-v057-pmx-01
created_at: 2026-05-11T00:00:00Z
updated_at: 2026-05-11T00:00:00Z
---

## Summary

Render the matrix grid, the object-permission popover, and the conflict
banner. Include a per-column "select all" toggle. Keep tests accessibility-
first.

**Spec:** [`docs/specs/permission-matrix-ui.md`](../../../../docs/specs/permission-matrix-ui.md)

## Files to Change

- **New:** `src/hyperadmin/templates/permissions/matrix.html`
- **New:** `src/hyperadmin/templates/permissions/object_popover.html`
- **New:** `src/hyperadmin/templates/permissions/_diff_row.html`
- **Modified:** `src/hyperadmin/templates/_sidebar.html` — link to the matrix when enabled

## data-testid Reference

| Element | testid |
|---|---|
| Group dropdown | `pmatrix-group-select` |
| Cell checkbox | `pmatrix-cell-{model}-{codename}` |
| Column "select all" | `pmatrix-select-all-{codename}` |
| Save button | `pmatrix-save-btn` |
| Conflict banner | `pmatrix-conflict-banner` |
| Object column trigger | `pmatrix-object-cell-{model}` |
| Object popover entry | `pmatrix-object-entry-{id}` |
| Object popover Add | `pmatrix-object-add` |

## Acceptance Criteria

- [ ] Grid renders per the SDD shape (rows = models, cols = actions + object)
- [ ] Group dropdown swaps the grid via HTMX without page reload
- [ ] Save button posts the diff payload (changed cells only)
- [ ] Conflict banner appears on 409 with a "Reload" affordance
- [ ] Object popover loads via `hx-get` and supports Add / Remove
- [ ] Per-column "select all" toggles every cell in that column
- [ ] `data-testid` exports match the table above
- [ ] Visual snapshots committed
- [ ] `poe lint` passes

## Blocked by

- `featviews-matrix-routes-and-audit`

## Parent

- Epic: `epic-v057-permissions-matrix`
