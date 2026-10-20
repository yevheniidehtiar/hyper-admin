# SDD: Tabular Permission-Matrix UI

| Field | Value |
|---|---|
| Author | Claude Code |
| Status | Approved |
| Issue | TBD |
| Milestone | v0.5.7 — Permissions Matrix |
| Created | 2026-05-11 |
| Last updated | 2026-10-20 |
| Approved by | Yevhenii Dehtiar |
| Approved on | 2026-10-20 |

---

## Problem

Object-level permissions and the auth model shipped in v0.5.1
(`docs/specs/object-permissions-mfa.md`). Editing them today requires
clicking into individual permission records one at a time. With even a small
catalogue (say, 30 models × 4 actions × 6 groups = 720 cells), this is
impractical. The H20 upstream check requires a tabular **model × action**
grid editor for groups (roles are a future epic), with the
**object-permission column** integrated from H5, **bulk save**, and
**audit logging** of every change.

## Goals

- A single-page grid editor at `/admin/permissions-matrix/` with rows = models,
  cols = actions (`view`, `add`, `change`, `delete`, plus any extras from
  `@action`), one matrix per group selectable via a dropdown.
- A separate object-permission column for each row that opens an inline
  popover listing per-row permission entries for the selected group; values
  editable in place.
- Bulk save that POSTs only the diff (cells the operator actually changed),
  not the entire grid.
- Optimistic concurrency: every save carries a per-group `version` stamp
  loaded with the grid; conflicting saves return 409 with a "reload to see
  changes" message.
- Audit log entry per (group, model, action, old → new) tuple written by
  `permissions/audit.py` into a new `hyperadmin_permission_audit` table.
  v0.5.1 deferred CRUD audit-log persistence to its own SDD
  (`docs/specs/object-permissions-mfa.md`, Non-Goals), so there is no shared
  writer yet; when one lands, `permissions/audit.py` becomes an adapter over it.
- Permission to access the matrix itself: superuser-only by default,
  configurable via `AdminOptions.permissions_matrix_codename` (defaults to
  `change_groups_permissions`).
- Bundled `examples/full-demo/` umbrella app exercising every H# end-to-end
  (`uv run examples/full-demo/main.py`).

## Non-Goals

- Inline create of new groups from the matrix. Group management remains in
  the existing model admin.
- Roles (named permission bundles assigned to groups). Groups only; roles
  are a future epic.
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
  And   PUT /admin/orders/1 returns 403
```

## Design

### Architecture

```
permissions/                      — NEW package (auth-adjacent)
  matrix.py                       — Matrix data model: load, diff, save, conflict-detect
  audit.py                        — PermissionAudit model + writer (hyperadmin_permission_audit)
views/permissions_matrix.py       — NEW view module: grid, save, object popover, conflict
templates/permissions/            — NEW: matrix.html, object_popover.html, _diff_row.html
core/options.py                   — permissions_matrix_codename
core/app.py                       — registers the matrix page through the plugin registry
examples/full-demo/               — NEW umbrella app exercising every H#
```

The matrix is **not** mounted as a `ModelAdmin` — it is its own view module
because rows / columns are derived from the admin's *registry*, not from a
single model. This sidesteps awkward conflation of meta-admin with model-admin.

It is registered as a built-in page through the plugin registry that v0.5.8
shipped (`core/plugins.py`): a `PluginPage` whose router mounts under
`/permissions-matrix` inside the isolated admin sub-app, a `NavEntry` with
`url_name="permissions-matrix"` (resolved through the `hyperadmin:`
namespace), and a `PluginPermission` for `permissions_matrix_codename` so
`PermissionSyncService` creates the codename. The page's router therefore
runs under `HyperAdminRoute` (auth bridge, CSRF guard, error pages), and
every URL in its templates comes from `url_for` / `admin_url_for`, never a
hard-coded `/admin/...` prefix.

### Data Model Changes

Reuses the built-in auth models (`hyperadmin.auth.models`, opt-in since
v0.5.8): `Group`, `Permission` and `GroupPermission` from v0.5.1. There is no
`Role` model and no shared audit table yet.

Adds an optimistic-concurrency column to the existing `Group` table:

```python
class Group(SQLModel, table=True):
    ...
    permissions_version: int = Field(default=0, sa_column_kwargs={"server_default": "0"})
```

Bumped atomically on every successful matrix save.

Adds one table for the audit trail:

```python
class PermissionAudit(SQLModel, table=True):
    __tablename__ = "hyperadmin_permission_audit"
    id: int | None = Field(default=None, primary_key=True)
    actor_key: str = Field(index=True, max_length=255)   # request.state.user_key
    group_id: int = Field(index=True)
    model: str = Field(max_length=255)
    codename: str = Field(max_length=255)
    before: bool
    after: bool
    created_at: datetime = Field(default_factory=utc_now, sa_type=UTCNaiveDateTime)
```

HyperAdmin ships no migration tool (BYOA SDD C): both changes join the
`hyperadmin_*` metadata, so `hyperadmin init-db` creates them on fresh
databases and hosts running Alembic pick them up through
`hyperadmin.auth.metadata()`. Existing deployments add the column and table
with their own migration tool (documented in the upgrade guide).

### API / Protocol Changes

```
GET    {prefix}/permissions-matrix/                              → grid (full page)                 name: permissions-matrix
GET    {prefix}/permissions-matrix/?group_id=<id>                → grid for that group
POST   {prefix}/permissions-matrix/save                          → diff save; body {group_id, version, changes: [...]}   name: permissions-matrix-save
GET    {prefix}/permissions-matrix/object/{group}/{model}        → popover fragment                name: permissions-matrix-object
POST   {prefix}/permissions-matrix/object/{group}/{model}        → add / remove object permission entries
```

`{prefix}` is the admin mount path (`/admin` by default). All POSTs pass the
CSRF guard in `HyperAdminRoute` (BYOA SDD D.1): the JSON save sends the
`X-CSRF-Token` header via the `hx-headers` global the base layout already
sets, so no per-save token is embedded in the payload.

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
| `permissions_matrix_enabled=False` | page and nav entry are not registered; the URL returns 404 |
| Built-in auth models not registered (e.g. `Admin(auth=ExternalAuth(...))` without `ModelPermissionChecker`) | there are no groups to edit: page and nav entry are not registered, logged at INFO |
| Audit writer raises | save rolls back the permission diff (atomic transaction); user sees a 500 with a generic "save failed" message; the error is logged |
| Concurrent object-popover edits | versionless — the popover writes are idempotent (add / remove keyed on (group, model, action, obj_pk)) |
| Browser sends a tampered version (e.g. -1) | treated as version mismatch — returns 409 |

## Migration & Backward Compatibility

- Adds `Group.permissions_version` (server default 0) and the
  `hyperadmin_permission_audit` table; created by `hyperadmin init-db` on
  fresh databases, added by the host's migration tool on existing ones.
- Adds routes; no existing route changes.
- Adds `AdminOptions` fields with safe defaults; no breaking change.

## Open Questions

All open questions resolved at approval (2026-10-20):

- [x] Groups only. Roles (named bundles assigned to groups) are a future
  epic; the plan listed "groups/roles" but H20 acceptance only needs groups.
- [x] The save payload carries no per-save token: it relies on the CSRF guard
  that v0.5.8 shipped in `HyperAdminRoute` (signed double-submit cookie plus
  the `X-CSRF-Token` header HTMX already sends).
- [x] A per-column "select all" toggle is added — saves operator time;
  trivial UI.

## Decision Log

| Decision | Rationale | Alternatives considered |
|---|---|---|
| Matrix as a standalone view module, not a `ModelAdmin` | Rows / cols span the entire admin registry; a single-model abstraction is the wrong shape | Stretch `ModelAdmin` to a "meta-admin" type (awkward, leaks abstraction) |
| Optimistic concurrency via per-group `permissions_version` | Cheap, no row-level locks; common case is single editor | Row-level `updated_at` per permission (more rows, more writes); pessimistic locks (blocks concurrent edits) |
| Diff-only POST (not full-grid POST) | Smaller payload, clearer audit log entries, harder to accidentally overwrite unrelated cells | Full-grid POST (loses intent; audit becomes "everything changed") |
| Bundle `examples/full-demo/` here, not earlier | This is the milestone where the readiness suite must run end-to-end | Ship the demo with v0.5.5 (premature — would change shape each milestone) |
| Object permissions edited via popover, not inline | Popover keeps the grid scannable; inline would make rows variable-height | Modal (heavier, breaks flow); side-drawer (eats grid width) |
| Groups only, roles deferred (approved) | H20 acceptance needs groups; roles need their own model and SDD | Ship roles here (grows v0.5.7 past the qualification check) |
| Rely on the `HyperAdminRoute` CSRF guard (approved) | One CSRF mechanism for every admin request; HTMX already sends the header | Per-save token in the JSON envelope (a second, parallel CSRF path) |
| Per-column select-all toggle (approved) | Granting `view` on 30 models is one click instead of 30 | None (operators click every cell) |
| Registered through the plugin registry (alignment with v0.5.8) | Gets `HyperAdminRoute`, the nav entry and codename sync from the same registry plugin pages use | Hand-wire a router in `core/app.py` (duplicates what `plugin_wiring.py` does) |
| Own `hyperadmin_permission_audit` table (alignment with v0.5.8) | v0.5.1 deferred audit persistence; H20 still requires an audit row per change | Wait for the shared audit SDD (blocks H20); log lines only (not queryable) |
