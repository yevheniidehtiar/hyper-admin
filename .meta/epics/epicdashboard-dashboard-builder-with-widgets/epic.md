---
type: epic
id: 6rJu0Bhscpsu
title: "epic(dashboard): Dashboard Builder with Widgets"
status: todo
priority: medium
owner: null
labels:
  - agent-task
  - area:core
  - area:views
  - roadmap
milestone_ref: null
github:
  issue_number: 422
  repo: yevheniidehtiar/hyper-admin
  last_sync_hash: sha256:10e571bcd1e0b262db9289b059467c0fc5bdee48f1673f35ddaff402e1da3280
  synced_at: 2026-04-05T09:13:33.560Z
created_at: 2026-04-01T21:36:16Z
updated_at: 2026-04-01T21:46:50Z
---

## Overview

Implement a customizable dashboard builder with widget cards, aggregation helpers, and drag-drop reordering.

**Milestone**: v0.5.4 — Dashboard Builder  
**SDD Required**: Yes — `docs/specs/dashboard-builder.md`  
**Modules affected**: dashboard/ (new), core/, adapters/, views/

### What's included

- `DashboardLayout` + `WidgetConfig` data models
- `DashboardWidget` protocol in core/
- Built-in widgets: `CountWidget`, `RecentItemsWidget`, `QuickActionsWidget`
- Aggregation helpers (`count()`, `aggregate()`) in BaseAdapter + SQLModelAdapter
- `DashboardService` — load layout, render widgets, save order
- Dashboard view handler replacing static welcome page
- Dashboard template with widget card grid
- Sortable.js drag-drop widget reordering (HTMX save)
- Dashboard configuration in HyperAdminSettings
- E2E test suite

### Dependency DAG

```
#455 (spec) ──┬──► #456 → #457 ──┐
              └──► #459 ──────────┼──► #460 → #462 ──┬──► #463 → #466
                                  │                   └──► #468
                                  └──────────────────────► #469
```

## Tasks
- [ ] #455 — review(spec): approve SDD for dashboard builder
- [ ] #456 — feat(dashboard): create dashboard data models
- [ ] #457 — feat(dashboard): create DashboardWidget protocol and built-in widgets
- [ ] #459 — feat(adapters): add aggregation helpers to BaseAdapter
- [ ] #460 — feat(dashboard): create DashboardService
- [ ] #462 — feat(views): create dashboard view handler
- [ ] #463 — feat(ui): create dashboard template with widget cards
- [ ] #466 — feat(ui): add Sortable.js drag-drop widget reordering
- [ ] #468 — feat(core): add dashboard config to Admin class
- [ ] #469 — test(e2e): dashboard E2E test suite
