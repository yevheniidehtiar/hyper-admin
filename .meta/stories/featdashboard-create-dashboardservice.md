---
type: story
id: 6phAJV-4E3hp
title: "feat(dashboard): create DashboardService"
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
  issue_number: 460
  repo: yevheniidehtiar/hyper-admin
  last_sync_hash: sha256:fcbb3a870d4dacce0b7d37938dc112edc7e153fd52c405f1180db4d591c6c657
  synced_at: 2026-04-05T09:13:33.560Z
created_at: 2026-04-01T21:44:36Z
updated_at: 2026-04-01T21:44:36Z
---

## Context

The dashboard service orchestrates loading user layouts, rendering widget data, and saving widget positions. It's the business logic layer between models and views.

## Scenarios

**Scenario: load_dashboard returns user's custom layout**
  Given user alice has a saved `DashboardLayout`
  When  `load_dashboard(alice)` is called
  Then  her layout with widget configs is returned

**Scenario: load_dashboard returns default layout for new user**
  Given user bob has no saved layout
  When  `load_dashboard(bob)` is called
  Then  the system default layout is returned

**Scenario: render_widgets fetches data for each widget in parallel**
  Given a layout with 3 widgets
  When  `render_widgets(layout)` is called
  Then  all 3 widgets' `render_data()` are called
  And   results are returned in position order

**Scenario: render_widgets handles widget errors gracefully**
  Given a widget whose `render_data()` raises an exception
  When  `render_widgets(layout)` is called
  Then  the failed widget returns an error card
  And   other widgets render normally

## Acceptance Criteria

- [ ] `DashboardService` class in `dashboard/service.py`
- [ ] `load_dashboard(user) -> DashboardLayout` — user layout or system default
- [ ] `render_widgets(layout, adapters) -> list[WidgetRenderResult]` — parallel rendering
- [ ] `save_widget_order(layout_id, positions: list[int]) -> None`
- [ ] Error isolation: one widget failure doesn't crash the dashboard
- [ ] Widget registry: maps `widget_type` string to widget class
- [ ] Unit tests cover all 4 scenarios

## Files Likely Affected
- `src/hyperadmin/dashboard/service.py` (new)
- `tests/unit/test_dashboard_service.py` (new)

## Dependencies
Depends on: #457 (DashboardWidget protocol + widgets), #459 (aggregation helpers)

## Notes for Implementer
- Use `asyncio.gather(*tasks, return_exceptions=True)` for parallel widget rendering
- Widget registry: `{"count": CountWidget, "recent_items": RecentItemsWidget, ...}`
- Default layout: built from `HyperAdminSettings.default_widgets` config
- Each `WidgetRenderResult` has: `widget_type`, `title`, `data` (or `error`)
