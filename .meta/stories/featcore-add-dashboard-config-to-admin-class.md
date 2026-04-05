---
type: story
id: YguCsQ5l7b38
title: "feat(core): add dashboard config to Admin class"
status: todo
priority: medium
assignee: null
labels:
  - enhancement
  - agent-task
  - area:core
  - size:S
  - area:settings
estimate: null
epic_ref: null
github:
  issue_number: 468
  repo: yevheniidehtiar/hyper-admin
  last_sync_hash: sha256:a43271421d17bc59f81a8f74bbd60e343b7f6e10786f6bc7eeb84fc6bf680ea0
  synced_at: 2026-04-05T09:13:33.560Z
created_at: 2026-04-01T21:45:33Z
updated_at: 2026-04-01T21:45:33Z
---

## Context

Users need to configure whether the dashboard is enabled and what default widgets are shown for new users.

## Scenarios

**Scenario: dashboard_enabled=False shows static welcome page**
  Given `HyperAdminSettings(dashboard_enabled=False)`
  When  GET `/admin/`
  Then  the static "Welcome to HyperAdmin" page is shown

**Scenario: default_widgets configures system default layout**
  Given `HyperAdminSettings(default_widgets=[{"type": "count", "model": "Order"}])`
  When  a new user visits the dashboard
  Then  a CountWidget for Order is shown

## Acceptance Criteria

- [ ] `dashboard_enabled: bool = True` added to `HyperAdminSettings`
- [ ] `default_widgets: list[dict] = []` added to `HyperAdminSettings`
- [ ] `Admin.mount()` conditionally wires `DashboardService` based on `dashboard_enabled`
- [ ] Default widgets config parsed into `WidgetConfig` objects by `DashboardService`
- [ ] Unit tests cover both scenarios

## Files Likely Affected
- `src/hyperadmin/core/settings.py`
- `src/hyperadmin/core/app.py`
- `tests/unit/test_settings.py`

## Dependencies
Depends on: #462 (dashboard view handler)

## Notes for Implementer
- When `dashboard_enabled=False`, the existing static `admin_dashboard()` is used
- `default_widgets` format: `[{"type": "count", "model": "Order", "label": "Total Orders"}]`
