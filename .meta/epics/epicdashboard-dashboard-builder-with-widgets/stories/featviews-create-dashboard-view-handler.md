---
type: story
id: nZS3hHHHPs5t
title: "feat(views): create dashboard view handler"
status: done
priority: medium
assignee: null
labels:
  - enhancement
  - agent-task
  - area:views
  - size:M
estimate: null
epic_ref:
  id: _MkBhj2OoiGp
github:
  issue_number: 462
  repo: yevheniidehtiar/hyper-admin
  last_sync_hash: sha256:d459515028a9ba219f66f9ce120d8c3375bcd8173f1caf0a22a2e268542b7a02
  synced_at: 2026-04-07T17:23:23.791Z
created_at: 2026-04-01T21:44:50Z
updated_at: 2026-11-20T00:00:00Z
---

## Context

Spec: `docs/specs/dashboard-builder.md` (Endpoints, Configuration Changes).

The reports plugin serves the dashboard as a plugin page under `settings.dashboard_prefix`
(default `/dashboard`) and, when widgets are registered and `dashboard_home` is on, claims the
admin index through the home page seam (`featcore-add-dashboard-config-to-admin-class.md`). The
routes parse input, call `DashboardService` and pick a template; all rules live in the service.
This story creates the page shell (`index.html`, `_grid.html`, `_card.html` with plain-form move
buttons); the card bodies and states come in
`featui-create-dashboard-template-with-widget-cards.md`.

## Scenarios

**Scenario: dashboard replaces the welcome page when widgets are registered**
  Given a StatWidget over the registered report "orders-revenue" is registered before `Admin(...)`
  When  a signed-in user requests `GET {prefix}/`
  Then  the page contains `data-testid="dashboard-grid"`
  And   the page does not contain "Welcome to HyperAdmin Dashboard"

**Scenario: welcome page stays when no widget is registered**
  Given the reports plugin is installed and no widget is registered
  When  a signed-in user requests `GET {prefix}/`
  Then  the welcome page is shown
  And   `GET {prefix}/dashboard/` is 404

**Scenario: dashboard_home=False keeps the welcome page and adds a sidebar link**
  Given widgets are registered and `plugin_settings={"reports": {"dashboard_home": False}}`
  When  a signed-in user requests `GET {prefix}/`
  Then  the welcome page is shown
  And   the sidebar has a link `data-testid="nav-dashboard"` to `{prefix}/dashboard/`

**Scenario: loading a widget the user may not view is refused**
  Given user "viewer" lacks `view_report_payroll_total`
  When  viewer requests `GET {prefix}/dashboard/widgets/stat-payroll-total`
  Then  the response is 403

**Scenario: loading an unknown widget is not found**
  When  a signed-in user requests `GET {prefix}/dashboard/widgets/nope`
  Then  the response is 404

**Scenario: saving an order over HTMX answers 204**
  Given alice sees `[A, B, C]`
  When  alice POSTs `{prefix}/dashboard/layout` with `widgets=C&widgets=A&widgets=B` and `HX-Request: true`
  Then  the response is 204
  And   `GET {prefix}/` shows `[C, A, B]` for alice

**Scenario: saving an invalid order is rejected**
  Given alice sees `[A, B, C]`
  When  alice POSTs `{prefix}/dashboard/layout` with `widgets=A&widgets=B&widgets=P`
  Then  the response is 400

**Scenario: saving a layout without a signed-in user is refused**
  Given the admin has no authentication configured
  When  `POST {prefix}/dashboard/layout` with `widgets=A&widgets=B&widgets=C`
  Then  the response is 403

**Scenario: saving with a missing layout table answers 503**
  Given the layout table does not exist
  When  alice POSTs `{prefix}/dashboard/layout` with her visible keys
  Then  the response is 503

**Scenario: a plain form move redirects back to the dashboard**
  Given alice sees `[A, B, C]`
  When  alice POSTs `{prefix}/dashboard/layout/move` with `key=B&direction=up` without `HX-Request`
  Then  the response is a 303 redirect to `{prefix}/dashboard/`
  And   alice's order is `[B, A, C]`

**Scenario: reset over HTMX returns the default grid**
  Given alice saved `[C, A, B]`
  When  alice POSTs `{prefix}/dashboard/reset` with `HX-Request: true`
  Then  the response is the grid in the order `[A, B, C]`

## Acceptance Criteria

- [ ] `build_dashboard_router(admin, settings)` with the five routes and names of the SDD table
- [ ] `ReportsPlugin.on_register`: dashboard page at `settings.dashboard_prefix` only when
      `registered_widgets()` is non-empty; home page claim when `dashboard_home`, else a
      "Dashboard" nav entry in the "Reports" section with `testid="nav-dashboard"`
- [ ] `LayoutStore` created only when `dashboard_layouts` is on
- [ ] HTMX vs plain responses as in the SDD (204 / grid fragment / 303); 400, 403, 404, 503 as listed
- [ ] `templates/dashboard/index.html`, `_grid.html`, `_card.html`; move buttons are POST forms
      with `csrf_input()`, shown only when the service can persist for the request
- [ ] Plugin README "Dashboard" section (register widgets, settings, permissions); `CHANGELOG.md`
      `Unreleased` bullet in its own hunk
- [ ] Integration tests (TestClient against a mounted admin) cover all 11 scenarios

## Files to Change

- `plugins/hyperadmin-reports/src/hyperadmin_reports/dashboard/routes.py` (new)
- `plugins/hyperadmin-reports/src/hyperadmin_reports/plugin.py`
- `plugins/hyperadmin-reports/src/hyperadmin_reports/templates/dashboard/index.html` (new)
- `plugins/hyperadmin-reports/src/hyperadmin_reports/templates/dashboard/_grid.html` (new)
- `plugins/hyperadmin-reports/src/hyperadmin_reports/templates/dashboard/_card.html` (new)
- `plugins/hyperadmin-reports/tests/test_dashboard_routes.py` (new)
- `plugins/hyperadmin-reports/README.md`
- `CHANGELOG.md`

## Dependencies

Depends on: `featdashboard-create-dashboardservice.md`, `featcore-add-dashboard-config-to-admin-class.md`

## Notes for Implementer

- The home page endpoint is the `dashboard-index` handler itself (`async (request) -> Response`).
- `GET {prefix}/dashboard/` returns `_grid.html` for HTMX requests that target the grid, the full
  page otherwise.
- Widgets must be registered before `Admin(...)`; tests register and unregister around each admin.
