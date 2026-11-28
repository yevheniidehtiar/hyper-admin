---
type: story
id: KolTP1g27vm9
title: "feat(dashboard): create dashboard data models"
status: done
priority: medium
assignee: null
labels:
  - enhancement
  - agent-task
  - area:core
  - size:M
estimate: null
epic_ref:
  id: _MkBhj2OoiGp
github:
  issue_number: 456
  repo: yevheniidehtiar/hyper-admin
  last_sync_hash: sha256:c992552e567caa08240bc70dfdc8698b431da1f541b06f5f896cd85b7555371b
  synced_at: 2026-04-07T17:23:23.791Z
created_at: 2026-04-01T21:43:49Z
updated_at: 2026-11-20T00:00:00Z
---

## Context

Spec: `docs/specs/dashboard-builder.md` (Data Model Changes, Layout store).

The dashboard remembers each user's widget order in one row per user. The table belongs to the
`hyperadmin-reports` plugin and is declared with SQLAlchemy Core on the plugin's own `MetaData`, so
it never appears in a host's `SQLModel.metadata` or Alembic autogenerate unless the host opts in.
Widget configuration stays in code; the row stores only the ordered widget keys.

## Scenarios

**Scenario: saved order is loaded back for the same user**
  Given an empty `hyperadmin_reports_dashboard_layout` table
  And   `LayoutStore.save("alice", ["chart-a", "stat-b"])` was called
  When  `LayoutStore.load("alice")` is called
  Then  the result is `["chart-a", "stat-b"]`

**Scenario: a user without a saved order gets None**
  Given alice saved `["chart-a", "stat-b"]`
  When  `LayoutStore.load("bob")` is called
  Then  the result is `None`

**Scenario: saving again replaces the order**
  Given alice saved `["chart-a", "stat-b"]`
  When  `LayoutStore.save("alice", ["stat-b", "chart-a"])` is called
  Then  `load("alice")` returns `["stat-b", "chart-a"]`
  And   the table holds one row for alice

**Scenario: reset deletes the user's row**
  Given alice saved `["chart-a", "stat-b"]`
  When  `LayoutStore.reset("alice")` is called
  Then  the result is `True`
  And   `load("alice")` returns `None`

**Scenario: reset without a saved row is a no-op**
  Given bob has no saved order
  When  `LayoutStore.reset("bob")` is called
  Then  the result is `False`

**Scenario: a concurrent first save becomes an update**
  Given alice has no row and another session inserts alice's row between the store's check and its insert
  When  `LayoutStore.save("alice", ["stat-b"])` commits
  Then  no exception is raised
  And   `load("alice")` returns `["stat-b"]`

**Scenario: a missing table raises LayoutUnavailableError**
  Given a database without the layout table
  When  `LayoutStore.load("alice")` is called
  Then  `LayoutUnavailableError` is raised

**Scenario: the layout table is not part of SQLModel.metadata**
  Given `hyperadmin_reports.dashboard` is imported
  When  `SQLModel.metadata.tables` is inspected
  Then  it has no `hyperadmin_reports_dashboard_layout` table
  And   `dashboard_metadata().tables` has it

## Acceptance Criteria

- [ ] `layout_table` on a module-private `MetaData`: `id` (int PK), `user_key` (str 255, indexed),
      `dashboard` (str 64, default `"home"`), `widgets` (JSON list of keys), `updated_at` (naive
      UTC via `hyperadmin.core.timezones.utc_now`), unique `(user_key, dashboard)` named
      `uq_hyperadmin_reports_dashboard_layout`
- [ ] `dashboard_metadata()` returns that `MetaData`; `create_layout_table(bind)` creates only this table
- [ ] `LayoutStore(engine=None, *, session_factory=None)` uses `hyperadmin.core.adapters.open_session`
      and `require_engine_or_session_factory`, like `NavPinService`
- [ ] `load`, `save`, `reset` take `user_key` explicitly and store it as `str(user_key)`
- [ ] `SQLAlchemyError` from a missing table is raised as `LayoutUnavailableError`
- [ ] Plugin README: "Dashboard layouts" section with `create_layout_table()` and the hand-written
      Alembic `op.create_table(...)` / downgrade
- [ ] Unit tests cover all 8 scenarios

## Files to Change

- `plugins/hyperadmin-reports/src/hyperadmin_reports/dashboard/__init__.py` (new)
- `plugins/hyperadmin-reports/src/hyperadmin_reports/dashboard/layout.py` (new)
- `plugins/hyperadmin-reports/tests/test_dashboard_layout.py` (new)
- `plugins/hyperadmin-reports/README.md`

## Dependencies

Depends on: `reviewspec-approve-sdd-for-dashboard-builder.md`

## Notes for Implementer

- Use SQLAlchemy Core (`Table`, `insert`, `update`, `select`, `delete`), not a `SQLModel` table
  class: a `table=True` model would register on `SQLModel.metadata` on import.
- Upsert = update by `(user_key, dashboard)`; if no row was updated, insert; on `IntegrityError`,
  roll back and update (last writer wins).
