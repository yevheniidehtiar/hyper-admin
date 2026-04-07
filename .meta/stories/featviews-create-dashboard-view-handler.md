---
type: story
id: nZS3hHHHPs5t
title: "feat(views): create dashboard view handler"
status: todo
priority: medium
assignee: null
labels:
  - enhancement
  - agent-task
  - area:views
  - size:M
estimate: null
epic_ref: null
github:
  issue_number: 462
  repo: yevheniidehtiar/hyper-admin
  last_sync_hash: sha256:d459515028a9ba219f66f9ce120d8c3375bcd8173f1caf0a22a2e268542b7a02
  synced_at: 2026-04-07T17:23:23.791Z
created_at: 2026-04-01T21:44:50Z
updated_at: 2026-04-01T21:44:50Z
---

## Context

The current dashboard is a static "Welcome to HyperAdmin" page. This replaces it with a dynamic view that uses `DashboardService` to load and render widgets.

## Scenarios

**Scenario: GET /admin/ renders dashboard with widget data**
  Given user alice has a dashboard with 2 widgets
  When  GET `/admin/`
  Then  the dashboard template renders with widget data

**Scenario: POST /admin/dashboard/save-order persists widget positions**
  Given user alice drags widget from position 0 to position 2
  When  POST `/admin/dashboard/save-order` with new positions
  Then  widget positions are updated in the database

**Scenario: dashboard view falls back to static page when no widgets configured**
  Given no dashboard widgets are configured
  When  GET `/admin/`
  Then  the default "Welcome to HyperAdmin" page is shown

## Acceptance Criteria

- [ ] `admin_dashboard()` in `views/dynamic.py` replaced with `DashboardService`-backed handler
- [ ] Dashboard loads user layout and renders widget data
- [ ] `POST /admin/dashboard/save-order` endpoint for position persistence
- [ ] Fallback to static page when `dashboard_enabled=False` or no widgets
- [ ] Route wired in `routing.py`
- [ ] Unit tests cover all 3 scenarios

## Files Likely Affected
- `src/hyperadmin/views/dynamic.py` — replace `admin_dashboard()` function
- `src/hyperadmin/routing.py` — wire dashboard service and save-order route

## Dependencies
Depends on: #460 (DashboardService)

## Notes for Implementer
- The existing `admin_dashboard()` at line 986 of `dynamic.py` is minimal — safe to replace
- Pass widget render results to template context as a list of dicts
- `save-order` endpoint: receive JSON array of `{widget_id, position}` pairs
