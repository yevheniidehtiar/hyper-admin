---
type: story
id: st-v057-pmx-02
title: "feat(views): matrix routes, conflict handling, audit log integration"
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

Add `views/permissions_matrix.py` with five routes (grid load, save, object
GET, object POST, conflict-banner fragment). Wire audit-log entries per
diff cell (reusing the v0.5.1 audit writer). Permission gate via
`permissions_matrix_codename`. Disable via `permissions_matrix_enabled=False`.

**Spec:** [`docs/specs/permission-matrix-ui.md`](../../../../docs/specs/permission-matrix-ui.md)

## Files to Change

- **New:** `src/hyperadmin/views/permissions_matrix.py`
- **Modified:** `src/hyperadmin/core/app.py` — register the matrix routes when enabled
- **Modified:** `src/hyperadmin/core/options.py` — `permissions_matrix_codename`, `permissions_matrix_enabled`
- **New:** `tests/unit/test_permissions_matrix_views.py`

## Scenarios

```
Scenario: save returns 200 with HX-Trigger when version matches
  Given the user has change_groups_permissions and version=5
  When  POST /admin/permissions-matrix/save with diff and version=5
  Then  response is 200 and HX-Trigger header is "permissions-saved"

Scenario: save returns 409 when version is stale
  When  POST with version=4 while current is 5
  Then  response is 409 and body contains "Permissions changed elsewhere"

Scenario: matrix gated by permissions_matrix_codename
  Given user lacks "change_groups_permissions"
  When  GET /admin/permissions-matrix/
  Then  response is 403

Scenario: audit log is written per diff cell on save
  Given a save diff of 3 cells
  When  the save commits
  Then  3 audit rows exist with action="permission_change" and matching payloads

Scenario: matrix disabled at config returns 404
  Given AdminOptions(permissions_matrix_enabled=False)
  When  GET /admin/permissions-matrix/
  Then  response is 404
```

## Acceptance Criteria

- [ ] Five routes registered behind the matrix-codename gate
- [ ] Save returns 200 / 409 / 403 per scenarios
- [ ] Audit log row per diff cell
- [ ] `permissions_matrix_enabled=False` disables the route
- [ ] Unit tests cover all five scenarios
- [ ] `poe lint` and `poe test:unit` pass

## Blocked by

- `featpermissions-matrix-data-layer`

## Parent

- Epic: `epic-v057-permissions-matrix`
