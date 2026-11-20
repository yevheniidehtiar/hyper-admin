---
type: story
id: RDeJu06smSCK
title: "review(spec): approve SDD for dashboard builder"
status: done
priority: medium
assignee: null
labels:
  - agent-task
  - area:core
  - area:views
  - size:S
estimate: null
epic_ref:
  id: _MkBhj2OoiGp
github:
  issue_number: 455
  repo: yevheniidehtiar/hyper-admin
  last_sync_hash: sha256:0230b3863c952ef9afa180f175d1052911ebd0234cf2e903cf0df244c81ddd88
  synced_at: 2026-04-07T17:23:23.791Z
created_at: 2026-04-01T21:43:34Z
updated_at: 2026-11-20T00:00:00Z
---

## Context

Spec gate for Epic #422. The SDD at `docs/specs/dashboard-builder.md` must be approved before the
dashboard implementation starts. The gate is passed by the architect agent; the owner can veto on
the epic PR.

## Outcome (2026-11-20)

Approved (architect) as revision 2 of the SDD. The draft of 2026-05-10 predated the move of
reports and charts into the `hyperadmin-reports` plugin, so the revision:

- puts the dashboard into the reports plugin (`hyperadmin_reports/dashboard/`), with one additive
  core seam, `PluginRegistry.set_home_page()`, so the plugin can serve `{prefix}/`;
- binds the data widgets to registered reports (`StatWidget`, `ChartWidget`) and adds
  `QuickActionsWidget`; widget permissions are the reports' codenames;
- stores the per-user order in a plugin-owned table on the plugin's own `MetaData` (opt-in, the
  dashboard degrades to the default order without it), so no host is pushed into a migration;
- reorders with vendored SortableJS plus keyboard / no-JS move buttons;
- supersedes `featadapters-add-aggregation-helpers-to-baseadapter.md` (#459).

No escalation item: no breaking public API, no new runtime dependency, no forced migration.

## Acceptance Criteria

- [x] SDD file exists at `docs/specs/dashboard-builder.md`
- [x] Problem statement is clear and scoped
- [x] Goals are measurable, non-goals prevent over-engineering
- [x] BDD scenarios cover widget rendering, layout persistence, drag-drop, error handling
- [x] Layout data model documented (`hyperadmin_reports_dashboard_layout`)
- [x] `DashboardWidget` API and the built-in widgets documented
- [x] Aggregation: reuses `ReportView` aggregates; the adapter helper story is superseded
- [x] Edge cases: empty dashboard, failed widgets, no user layout, missing table, no auth
- [x] Open questions resolved
- [x] Status changed from Draft to Approved (architect)

## Files to Change

- `docs/specs/dashboard-builder.md`

## Dependencies

None.
