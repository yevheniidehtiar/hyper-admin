---
type: story
id: K3AnRMAHW2sv
title: "feat(adapters): add aggregation helpers to BaseAdapter"
status: cancelled
priority: medium
assignee: null
labels:
  - enhancement
  - agent-task
  - area:core
  - area:adapters
  - size:M
estimate: null
epic_ref:
  id: _MkBhj2OoiGp
github:
  issue_number: 459
  repo: yevheniidehtiar/hyper-admin
  last_sync_hash: sha256:20ca319c60589236fa4a23bc37007d75768723bbb09898b3270eaed690f00c4c
  synced_at: 2026-04-07T17:23:23.791Z
created_at: 2026-04-01T21:44:20Z
updated_at: 2026-11-20T00:00:00Z
---

## Superseded

Superseded by revision 2 of `docs/specs/dashboard-builder.md` (2026-11-20, architect). Do not
implement.

The dashboard's numbers come from registered `ReportView`s in the `hyperadmin-reports` plugin,
whose aggregates (`Sum`, `Count`, `Min`, `Max`, ...) already run on every SQLAlchemy model and
fold into totals with `Aggregate.total()`. `BaseAdapter.list()` already returns the row count.
`count()` / `aggregate()` on `BaseAdapter` would be core adapter API with no caller in this epic.
If a later core feature needs adapter-level aggregation, it gets its own story and SDD.

The story stays open on GitHub until the epic PR closes it together with the other stories.

## Original scope (for reference)

`count(filters) -> int` and `aggregate(field, func, filters)` on `BaseAdapter`, implemented by
`SQLModelAdapter` with `func.count()` / `func.sum()` / `func.avg()` / `func.min()` / `func.max()`.

## Dependencies

Depends on: `reviewspec-approve-sdd-for-dashboard-builder.md`
