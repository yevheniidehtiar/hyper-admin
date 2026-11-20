---
type: epic
id: _MkBhj2OoiGp
title: "epic(dashboard): Dashboard Builder with Widgets"
status: todo
priority: medium
owner: null
labels:
  - agent-task
  - area:core
  - area:views
  - roadmap
milestone_ref:
  id: 8DidH5NiN6cP
github:
  issue_number: 422
  repo: yevheniidehtiar/hyper-admin
  last_sync_hash: sha256:10e571bcd1e0b262db9289b059467c0fc5bdee48f1673f35ddaff402e1da3280
  synced_at: 2026-04-07T17:23:23.791Z
created_at: 2026-04-01T21:36:16Z
updated_at: 2026-11-20T00:00:00Z
---

## Overview

The widget/layout layer over `ReportView`: the admin home page becomes a dashboard of report
numbers, report charts and shortcut links, which each user can reorder by drag and drop or from
the keyboard, with the order remembered per user.

**Milestone**: v0.5.4 — Reporting & Charts  
**Spec**: [docs/specs/dashboard-builder.md](../../../docs/specs/dashboard-builder.md) (Approved (architect), revision 2, 2026-11-20)  
**Modules affected**: `plugins/hyperadmin-reports/` (new `dashboard/` subpackage), `core/plugins.py` + `routing.py` (one additive home page seam)

### What's included

- Core seam `PluginRegistry.set_home_page()` and the reports plugin's `ReportsSettings`
- Plugin-owned layout table on the plugin's own `MetaData` (opt-in, degrades without it) + `LayoutStore`
- `DashboardWidget` base class; `StatWidget`, `ChartWidget` (bound to registered reports), `QuickActionsWidget`; `register_widget()`
- `DashboardService`: permissions, per-user order, save validation, failure isolation
- Dashboard routes (page, widget fragments, save order, move, reset) and the home page claim
- Widget card templates (StatCard design), responsive grid, error / empty states
- Vendored SortableJS drag and drop + keyboard move buttons
- E2E test suite

Superseded: #459 (aggregation helpers on `BaseAdapter`) — `ReportView` aggregates cover it.

### Dependency DAG

```
#455 (spec, done) ──┬──► #456 (layout store) ──┐
                    ├──► #457 (widgets) ────────┴──► #460 (service) ──┐
                    └──► #468 (core seam + settings) ─────────────────┴──► #462 (routes) → #463 (cards) → #466 (drag-drop) → #469 (E2E)
#459 superseded
```

Implementation order on one branch: #468, #456, #457, #460, #462, #463, #466, #469.

## Tasks
- [x] #455 — review(spec): approve SDD for dashboard builder
- [ ] #456 — feat(dashboard): create dashboard data models
- [ ] #457 — feat(dashboard): create DashboardWidget protocol and built-in widgets
- [ ] #459 — feat(adapters): add aggregation helpers to BaseAdapter (superseded)
- [ ] #460 — feat(dashboard): create DashboardService
- [ ] #462 — feat(views): create dashboard view handler
- [ ] #463 — feat(ui): create dashboard template with widget cards
- [ ] #466 — feat(ui): add Sortable.js drag-drop widget reordering
- [ ] #468 — feat(core): add dashboard config to Admin class
- [ ] #469 — test(e2e): dashboard E2E test suite

## Status note (2026-09-28 roadmap re-cut)

Linked to v0.5.4 — Reporting & Charts, which re-scoped the dashboard milestone around ReportView + charts. The widget/drag-drop dashboard stories stay in scope as the follow-on layer on top of ReportView (nothing cut).

## Status note (2026-11-20 spec gate)

SDD revision 2 approved by the architect: the dashboard moved into `hyperadmin-reports`, story files moved from `.meta/stories/` into this epic and rewritten to match. The owner can veto on the epic PR.
