---
type: story
id: 3vo9kpKs3D0T
title: "feat(dashboard): create dashboard data models"
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
  issue_number: 456
  repo: yevheniidehtiar/hyper-admin
  last_sync_hash: sha256:c992552e567caa08240bc70dfdc8698b431da1f541b06f5f896cd85b7555371b
  synced_at: 2026-04-05T09:13:33.560Z
created_at: 2026-04-01T21:43:49Z
updated_at: 2026-04-01T21:43:49Z
---

## Context

The dashboard builder needs data models for storing user layouts and widget configurations. This creates the new `dashboard/` package with SQLModel tables.

## Scenarios

**Scenario: DashboardLayout stores per-user layout**
  Given user alice creates a dashboard named "My Dashboard"
  When  the layout is persisted
  Then  it has `user_id = alice.id` and `name = "My Dashboard"`

**Scenario: WidgetConfig stores widget position and configuration**
  Given a CountWidget at position 0 with config `{"model": "Order", "label": "Total Orders"}`
  When  the widget config is persisted
  Then  `widget_type = "count"`, `position = 0`, config contains model and label

**Scenario: default dashboard is loaded when user has no custom layout**
  Given user alice has no `DashboardLayout`
  When  the dashboard is loaded
  Then  the system default widgets are shown

## Acceptance Criteria

- [ ] `src/hyperadmin/dashboard/__init__.py` created
- [ ] `DashboardLayout` model: `id`, `user_id` (FK), `name`, `is_default` (bool), `created_at`
- [ ] `WidgetConfig` model: `id`, `dashboard_id` (FK), `widget_type` (str), `position` (int), `size` (str), `config` (JSON), `created_at`
- [ ] Table names: `hyperadmin_dashboard_layouts`, `hyperadmin_widget_configs`
- [ ] Relationships with `selectinload`
- [ ] Unit tests cover all 3 scenarios

## Files Likely Affected
- `src/hyperadmin/dashboard/__init__.py` (new)
- `src/hyperadmin/dashboard/models.py` (new)
- `tests/unit/test_dashboard_models.py` (new)

## Dependencies
Depends on: #455 (SDD approved)

## Notes for Implementer
- `config` field: use `sa_column=Column(JSON)` for SQLModel JSON storage
- `size` field: string enum-like values ("small", "medium", "large", "full")
- Follow existing model patterns in `auth/models.py`
- CONSTITUTION.md: new `dashboard/` package is correct (new feature = new module)
