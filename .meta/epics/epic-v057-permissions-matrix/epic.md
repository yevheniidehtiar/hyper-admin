---
type: epic
id: ep-v057-pmx-01
title: "epic(permissions): tabular permission-matrix UI + examples/full-demo umbrella"
status: todo
priority: high
owner: null
labels:
  - size:L
  - planned
  - backend
  - frontend
  - upstream-readiness
  - H20
milestone_ref:
  id: v057-pmx-01
created_at: 2026-05-11T00:00:00Z
updated_at: 2026-05-11T00:00:00Z
---

## Overview

Implements upstream readiness capability **H20**: tabular model × action grid
editor for groups, integrated object-permission popover, optimistic-
concurrency bulk save, per-cell audit logging. Also bundles
`examples/full-demo/` — the umbrella app that runs every H# qualification
check end-to-end.

**SDD:** [`docs/specs/permission-matrix-ui.md`](../../../docs/specs/permission-matrix-ui.md)
(required — new view module, schema change, multi-module integration).

## Tracks

### Track A: Matrix data layer (permissions/)
- `permissions/matrix.py` — load grid, compute diff, save with version check.
- `permissions/audit.py` — reuse v0.5.1 audit writer.
- `Group.permissions_version` column + Alembic migration.

### Track B: View module + routes
- `views/permissions_matrix.py` — grid, save, object popover, conflict (409).
- Permission gate via `permissions_matrix_codename`.
- Disable switch via `permissions_matrix_enabled`.

### Track C: Templates + UX
- `templates/permissions/matrix.html`, `object_popover.html`, `_diff_row.html`.
- Select-all column toggle, group dropdown, save bar with conflict banner.
- `data-testid`: `pmatrix-cell-{model}-{codename}`, `pmatrix-save-btn`,
  `pmatrix-group-select`, `pmatrix-conflict-banner`, `pmatrix-object-cell-{model}`.

### Track D: `examples/full-demo/` umbrella + E2E qualification
- Generic schema: `Order`, `Invoice`, `Product`, `Supplier`.
- One bundled E2E suite that exercises **every H#** in sequence.
- Becomes the readiness gate from this milestone onward.

## Scenarios

See SDD `## BDD Scenarios` (seven scenarios: matrix load, diff save,
conflict, object popover, gate, audit log, detail-page reflection).

## Acceptance Criteria

- [ ] `Group.permissions_version` migration applies cleanly
- [ ] Matrix loads with current grid for the selected group
- [ ] Save sends diff-only payload (`{group_id, version, changes:[...]}`)
- [ ] Optimistic-concurrency 409 on version mismatch
- [ ] Object popover lists per-row perms and supports add/remove
- [ ] Permission codename gates access (default `change_groups_permissions`)
- [ ] Audit row written per (group, model, codename, before, after)
- [ ] `examples/full-demo/` runs the 10-step qualification check via `poe test:e2e -k qualification`
- [ ] Seven SDD scenarios pass
- [ ] `poe lint` and `poe test` pass

## Blocked by

- `reviewspec-approve-sdd-permission-matrix-ui`
- All prior upstream-readiness epics (the umbrella demo requires every H# in place)

## Parent

- Milestone: `v057-permissions-matrix`
- Tracking: `epic-upstream-readiness` (H20)
