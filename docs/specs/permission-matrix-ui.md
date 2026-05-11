# SDD: Tabular Permission-Matrix UI

| Field | Value |
|---|---|
| Author | Claude Code |
| Status | Draft |
| Issue | TBD |
| Milestone | v0.5.7 — Permissions Matrix |
| Created | 2026-05-11 |
| Last updated | 2026-05-11 |

---

## Problem

Object-level permissions and the auth model shipped in v0.5.1
(`docs/specs/object-permissions-mfa.md`). Editing them today requires
clicking into individual permission records one at a time. With even a small
catalogue (say, 30 models × 4 actions × 6 groups = 720 cells), this is
impractical. The H20 upstream check requires a tabular **model × action**
grid editor for groups / roles, with the **object-permission column**
integrated from H5, **bulk save**, and **audit logging** of every change.

## Goals

- A single-page grid editor at `/admin/permissions-matrix/` with rows = models,
  cols = actions (`view`, `add`, `change`, `delete`, plus any extras from
  `@action`), one matrix per group / role selectable via a dropdown.
- A separate object-permission column for each row that opens an inline
  popover listing per-row permission entries for the selected group; values
  editable in place.
- Bulk save that POSTs only the diff (cells the operator actually changed),
  not the entire grid.
- Optimistic concurrency: every save carries a per-group `version` stamp
  loaded with the grid; conflicting saves return 409 with a "reload to see
  changes" message.
- Audit log entry per (group, model, action, old → new) tuple written into
  the existing audit-trail table (v0.5.1 already audits CRUD; this just
  reuses the writer).
- Permission to access the matrix itself: superuser-only by default,
  configurable via `AdminOptions.permissions_matrix_codename` (defaults to
  `change_groups_permissions`).
- Bundled `examples/full-demo/` umbrella app exercising every H# end-to-end
  (`uv run examples/full-demo/main.py`).

## Non-Goals

- Inline create of new groups from the matrix. Group management remains in
  the existing model admin.
- Cross-group bulk edit ("apply this row to groups A and B"). The matrix
  edits one group at a time.
- Permission inheritance / hierarchical groups. Out of scope; flat groups
  only.
- Time-bound permissions ("Alice can edit Orders until 2026-12-31"). Future.
- Diff visualisation between two groups. Future "compare view".

## BDD Scenarios

```
Scenario: matrix loads with current grid for selected group
  Given groups [Editors, Viewers] and models [Order, Invoice, Product]
  When  the user opens /admin/permissions-matrix/ and selects "Editors"
  Then  the grid renders 3 rows × 4 cols (view/add/change/delete)
  And   each cell shows the current granted value as a checkbox

Scenario: bulk save posts only changed cells
  Given the Editors group has 12 currently checked cells
  When  the user toggles two cells off and clicks Save
  Then  POST /admin/permissions-matrix/save carries exactly two diff entries
  And   the response is 200 with HX-Trigger "permissions-saved"

Scenario: conflicting save returns 409
  Given the user has the grid loaded with version=5
  And   another user has saved a change, bumping version to 6
  When  the user clicks Save
  Then  response is 409 with body "Permissions changed elsewhere — reload"
  And   no permission rows are mutated

Scenario: object-permission column opens an inline popover
  Given the Editors group has 2 per-row object permissions on Order
  When  the user clicks the "Object" cell on the Order row
  Then  a popover loads /admin/permissions-matrix/object/Editors/Order with the two entries listed
  And   each entry has a remove button and the popover has an "Add" affordance

Scenario: permission codename gates access to the matrix
  Given the user lacks "change_groups_permissions"
  When  GET /admin/permissions-matrix/
  Then  response is 403

Scenario: audit log records every (group, model, action, old, new) tuple
  Given the user toggles 3 cells and saves
  When  the save commits
  Then  3 new rows exist in the audit trail with action="permission_change"
  And   each row carries the (group_id, model, codename, before, after) payload

Scenario: detail page reflects a freshly-flipped view-but-not-edit role
  Given the user logs in as a member of "Viewers"
  And   the matrix has Viewers with view=true, change=false for Order
  When  the user opens /admin/orders/1/
  Then  the page renders without an Edit button
  And   POST /admin/orders/1/update would return 403
```

## Design

### Architecture

```
permissions/                      — NEW package (auth-adjacent)
  matrix.py                       — Matrix data model: load, diff, save, conflict-detect
  audit.py                        — Reuses existing audit writer from v0.5.1
views/permissions_matrix.py       — NEW view module: grid, save, object popover, conflict
templates/permissions/            — NEW: matrix.html, object_popover.html, _diff_row.html
core/options.py                   — permissions_matrix_codename
examples/full-demo/               — NEW umbrella app exercising every H#
```

The matrix is **not** mounted as a `ModelAdmin` — it is its own view module
because rows / columns are derived from the admin's *registry*, not from a
single model. This sidesteps awkward conflation of meta-admin with model-admin.

### Data Model Changes

No new tables. Reuses:

- `Group` / `Role` (from v0.5.1).
- Permission rows (from v0.5.1).
- Audit table (from v0.5.1).

Adds an optimistic-concurrency column to the existing `Group` table:

```python
class Group(SQLModel, table=True):
    ...
    permissions_version: int = Field(default=0)
```

Bumped atomically on every successful matrix save. Forward-only Alembic
migration adds the column with `server_default='0'`.

### API / Protocol Changes

```
GET    /admin/permissions-matrix/                              → grid (full page)
GET    /admin/permissions-matrix/?group_id=<id>                → grid for that group
POST   /admin/permissions-matrix/save                          → diff save; body {group_id, version, changes: [...]}
GET    /admin/permissions-matrix/object/{group}/{model}        → popover fragment
POST   /admin/permissions-matrix/object/{group}/{model}        → add / remove object permission entries
```

The save payload uses a tiny diff envelope:

```json
{
  "group_id": 7,
  "version": 5,
  "changes": [
    {"model": "order",   "codename": "change_order",  "granted": false},
    {"model": "invoice", "codename": "add_invoice",   "granted": true}
  ]
}
```

### Configuration Changes

`AdminOptions` gains:

```python
permissions_matrix_codename: str = "change_groups_permissions"
permissions_matrix_enabled: bool = True
```

Disable via `permissions_matrix_enabled=False` for projects without groups.

## Edge Cases & Error Handling

| Case | Handling |
|---|---|
| Empty admin registry | matrix renders an empty grid with a "No registered models" notice |
| Version mismatch | 409 + reload prompt; no rows mutated; not retried |
| Cell change touches a permission the user can't grant (privilege escalation) | reject the whole save with 403 and a per-cell error listing rejected entries |
| Group deleted mid-edit | save returns 404 "Group not found"; client resets selection |
| `permissions_matrix_enabled=False` | route returns 404 |
| Audit writer raises | save rolls back the permission diff (atomic transaction); user sees a 500 with a generic "save failed" message; the error is logged |
| Concurrent object-popover edits | versionless — the popover writes are idempotent (add / remove keyed on (group, model, action, obj_pk)) |
| Browser sends a tampered version (e.g. -1) | treated as version mismatch — returns 409 |

## Migration & Backward Compatibility

- Adds `Group.permissions_version` via Alembic; defaults to 0 for existing rows.
- Adds routes; no existing route changes.
- Adds `AdminOptions` fields with safe defaults; no breaking change.

## Open Questions

- [ ] Should the matrix support **roles** (named bundles assigned to groups) in v0.5.7, or only groups? Proposal: groups only — roles are a separate v0.5.8 epic. The plan lists "groups/roles" but H20 acceptance only needs groups.
- [ ] Should the saved-diff payload carry a CSRF token or rely on the existing global CSRF middleware? Proposal: rely on the existing middleware.
- [ ] Should we add a "select-all" toggle per column? Proposal: yes — saves operator time; trivial UI.

## Decision Log

| Decision | Rationale | Alternatives considered |
|---|---|---|
| Matrix as a standalone view module, not a `ModelAdmin` | Rows / cols span the entire admin registry; a single-model abstraction is the wrong shape | Stretch `ModelAdmin` to a "meta-admin" type (awkward, leaks abstraction) |
| Optimistic concurrency via per-group `permissions_version` | Cheap, no row-level locks; common case is single editor | Row-level `updated_at` per permission (more rows, more writes); pessimistic locks (blocks concurrent edits) |
| Diff-only POST (not full-grid POST) | Smaller payload, clearer audit log entries, harder to accidentally overwrite unrelated cells | Full-grid POST (loses intent; audit becomes "everything changed") |
| Bundle `examples/full-demo/` here, not earlier | This is the milestone where the readiness suite must run end-to-end | Ship the demo with v0.5.5 (premature — would change shape each milestone) |
| Object permissions edited via popover, not inline | Popover keeps the grid scannable; inline would make rows variable-height | Modal (heavier, breaks flow); side-drawer (eats grid width) |
