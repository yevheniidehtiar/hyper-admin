---
type: story
id: st-v057-pmx-01
title: "feat(permissions): matrix data layer + Group.permissions_version migration"
status: todo
priority: high
assignee: null
labels:
  - size:M
  - planned
  - backend
  - upstream-readiness
  - H20
estimate: null
epic_ref:
  id: ep-v057-pmx-01
created_at: 2026-05-11T00:00:00Z
updated_at: 2026-05-11T00:00:00Z
---

## Summary

Add `permissions/matrix.py` with three functions — `load_grid(group_id)`,
`compute_diff(current, submitted)`, `save_diff(group_id, version, changes)` —
plus the `Group.permissions_version` column and forward-only Alembic
migration. `save_diff` is atomic and bumps the version.

**Spec:** [`docs/specs/permission-matrix-ui.md`](../../../../docs/specs/permission-matrix-ui.md)

## Files to Change

- **New:** `src/hyperadmin/permissions/__init__.py`
- **New:** `src/hyperadmin/permissions/matrix.py`
- **Modified:** `src/hyperadmin/core/auth.py` — `Group.permissions_version` field
- **New:** `migrations/versions/{rev}_add_group_permissions_version.py`
- **New:** `tests/unit/test_permissions_matrix.py`

## Scenarios

```
Scenario: load_grid returns one entry per registered model × action
  Given Editors group and registered models [Order, Invoice]
  When  load_grid("Editors") is called
  Then  the result has 2 × 4 cells (view/add/change/delete) per model
  And   each cell carries (granted: bool, codename: str)

Scenario: save_diff with matching version commits and bumps
  Given Editors.permissions_version == 5
  When  save_diff("Editors", version=5, changes=[{model:"order", codename:"change_order", granted:false}])
  Then  the change_order permission for Editors is removed
  And   Editors.permissions_version == 6

Scenario: save_diff with stale version raises ConflictError
  Given Editors.permissions_version == 6
  When  save_diff("Editors", version=5, changes=[...])
  Then  ConflictError is raised
  And   no permission rows are mutated
```

## Acceptance Criteria

- [ ] `Group.permissions_version` added with default 0
- [ ] Alembic migration applies cleanly (up + down)
- [ ] `load_grid`, `compute_diff`, `save_diff` implemented
- [ ] `save_diff` is transactional and bumps the version atomically
- [ ] `ConflictError` raised on version mismatch
- [ ] Unit tests cover all three scenarios
- [ ] `poe lint` and `poe test:unit` pass

## Blocked by

- `reviewspec-approve-sdd-permission-matrix-ui`

## Parent

- Epic: `epic-v057-permissions-matrix`
