---
type: story
id: Rvhb-sLANLaB
title: "feat(dashboard): create DashboardWidget protocol and built-in widgets"
status: todo
priority: medium
assignee: null
labels:
  - enhancement
  - agent-task
  - area:core
  - size:M
estimate: null
epic_ref: null
github:
  issue_number: 457
  repo: yevheniidehtiar/hyper-admin
  last_sync_hash: sha256:d6ec03962e5f47b50fbb39fe453ee6181db9cbefc830b67a58dfdac2a94b69fd
  synced_at: 2026-04-07T17:23:23.791Z
created_at: 2026-04-01T21:44:05Z
updated_at: 2026-04-01T21:44:05Z
---

## Context

Widgets are the content units of the dashboard. This defines the `DashboardWidget` protocol in `core/` and implements 3 built-in widgets in `dashboard/`.

## Scenarios

**Scenario: CountWidget returns total record count for a model**
  Given a CountWidget configured for the Order model
  When  `render_data()` is called
  Then  the result contains `{"count": 42, "label": "Total Orders"}`

**Scenario: RecentItemsWidget returns latest N records**
  Given a RecentItemsWidget configured for Order with `limit=5`
  When  `render_data()` is called
  Then  the result contains the 5 most recently created Orders

**Scenario: QuickActionsWidget returns configured action links**
  Given a QuickActionsWidget with actions `["Create Order", "View Reports"]`
  When  `render_data()` is called
  Then  the result contains the action labels and URLs

**Scenario: DashboardWidget protocol is runtime-checkable**
  Given a class implementing `widget_type`, `title`, `render_data()`
  When  `isinstance()` is called against `DashboardWidget`
  Then  it returns True

## Acceptance Criteria

- [ ] `DashboardWidget` protocol in `core/dashboard.py` (new)
- [ ] Protocol: `widget_type: str`, `title: str`, `async render_data(config, adapter) -> dict`
- [ ] `CountWidget` in `dashboard/widgets.py` — uses `adapter.count()`
- [ ] `RecentItemsWidget` — uses `adapter.list(page=1, page_size=N, order_by="-created_at")`
- [ ] `QuickActionsWidget` — returns static config (no DB call)
- [ ] Unit tests cover all 4 scenarios

## Files Likely Affected
- `src/hyperadmin/core/dashboard.py` (new)
- `src/hyperadmin/dashboard/widgets.py` (new)
- `tests/unit/test_dashboard_widgets.py` (new)

## Dependencies
Depends on: #456 (dashboard data models)

## Notes for Implementer
- Protocol goes in `core/` (contracts), implementations go in `dashboard/` (CONSTITUTION.md)
- `render_data()` is async — widgets may make DB calls via the adapter
- Widget config is a `dict[str, Any]` parsed from `WidgetConfig.config` JSON
