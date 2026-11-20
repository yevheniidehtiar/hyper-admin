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
epic_ref:
  id: _MkBhj2OoiGp
github:
  issue_number: 457
  repo: yevheniidehtiar/hyper-admin
  last_sync_hash: sha256:d6ec03962e5f47b50fbb39fe453ee6181db9cbefc830b67a58dfdac2a94b69fd
  synced_at: 2026-04-07T17:23:23.791Z
created_at: 2026-04-01T21:44:05Z
updated_at: 2026-11-20T00:00:00Z
---

## Context

Spec: `docs/specs/dashboard-builder.md` (API / Protocol Changes, Plugin public API).

Widgets are the cards of the dashboard. They live in the `hyperadmin-reports` plugin, not in the
core: the data widgets bind to registered `ReportView`s. `DashboardWidget` is an abstract base
class with defaults; `StatWidget` shows one total of a report aggregate, `ChartWidget` embeds the
report's chart fragment, `QuickActionsWidget` shows shortcut links. Widgets are registered in code
with `register_widget()`, before `Admin(...)` is built, like reports.

This story also moves the plugin's reads of the `Admin` object (session source, permission
checker) out of `routes.py` into `admin_context.py`, so widgets and routes share them without
importing private helpers.

## Scenarios

**Scenario: stat widget totals its report aggregate**
  Given the registered report "orders-revenue" sums `Order.amount` grouped by `status`
  And   Orders have amounts 100, 200 and 300
  When  `StatWidget(OrderRevenueReport).render(request, admin)` is awaited
  Then  the body context has `value == 600`
  And   the body links to the "orders-revenue" report page

**Scenario: stat widget without rows has no value**
  Given the registered report "orders-revenue" and no Order rows
  When  the stat widget renders
  Then  the body context has `value is None`

**Scenario: chart widget points at the report chart fragment**
  Given the registered chartable report "orders-by-month"
  When  `ChartWidget(OrdersByMonthReport).fragment_url(request)` is called
  Then  the result is `{prefix}/reports/orders-by-month/chart?embed=1`
  And   `permission()` is `"view_report_orders_by_month"`

**Scenario: quick actions keep only the actions the user may use**
  Given a QuickActionsWidget with "New order" (permission `add_order`) and "All reports" (no permission)
  And   a user without `add_order`
  When  the widget renders for that user
  Then  the body lists "All reports"
  And   the body does not list "New order"

**Scenario: a widget over an unregistered report is refused**
  Given `OrderRevenueReport` was not passed to `register_report()`
  When  `register_widget(StatWidget(OrderRevenueReport))` is called
  Then  `ValueError` is raised naming the report

**Scenario: a duplicate widget key is refused**
  Given a widget with key "stat-orders-revenue" is registered
  When  another widget with the key "stat-orders-revenue" is registered
  Then  `ValueError` is raised

**Scenario: a stat over an aggregate without totals is refused**
  Given a registered report whose only aggregate is `StringAggComma("sku")`
  When  `StatWidget(report)` is constructed
  Then  `ValueError` is raised

**Scenario: a chart over a report without a dimension is refused**
  Given a registered report with no `rows` and no `cols`
  When  `ChartWidget(report)` is constructed
  Then  `ValueError` is raised

## Acceptance Criteria

- [ ] `DashboardWidget(ABC)`: `key`, `title`, `span` (1..4, default 1), `lazy` (default `True`),
      `permission()`, `fragment_url(request)`, `detail_url(request)`, abstract async
      `render(request, admin) -> WidgetBody`
- [ ] `WidgetBody(template, context)` named tuple
- [ ] `StatWidget(report, *, value=None, key=None, title=None, span=1)`: key `stat-{slug}`,
      permission `report.get_permission()`, value folded with `Aggregate.total()`
- [ ] `ChartWidget(report, *, key=None, title=None, span=2)`: key `chart-{slug}`, fragment URL is
      the `report-chart` route with `?embed=1`
- [ ] `QuickAction(label, url_name, url_params={}, permission=None, icon=None)` and
      `QuickActionsWidget(actions, *, key="quick-actions", title="Quick actions", span=1)`, `lazy = False`
- [ ] `register_widget`, `unregister_widget`, `registered_widgets` (registration order); all
      validation from the SDD raises `ValueError` at construction or registration
- [ ] `admin_context.py`: `session_source(admin)`, `permission_checker(admin)`,
      `has_permission(admin, request, codename)`; `routes.py` uses them, `can_view()` keeps its signature
- [ ] New names re-exported from `hyperadmin_reports/__init__.py` and `hyperadmin_reports/dashboard/__init__.py`
- [ ] Unit tests cover all 8 scenarios; existing reports tests stay green

## Files to Change

- `plugins/hyperadmin-reports/src/hyperadmin_reports/dashboard/widgets.py` (new)
- `plugins/hyperadmin-reports/src/hyperadmin_reports/dashboard/__init__.py`
- `plugins/hyperadmin-reports/src/hyperadmin_reports/admin_context.py` (new)
- `plugins/hyperadmin-reports/src/hyperadmin_reports/routes.py`
- `plugins/hyperadmin-reports/src/hyperadmin_reports/__init__.py`
- `plugins/hyperadmin-reports/tests/test_dashboard_widgets.py` (new)

## Dependencies

Depends on: `reviewspec-approve-sdd-for-dashboard-builder.md`

## Notes for Implementer

- `StatWidget.render` runs `report.run(session_source(admin))` and folds
  `[r[agg.name] for r in result.records]` with `agg.total(...)`; it does not catch exceptions
  (the service isolates failures).
- `QuickActionsWidget.render` resolves each `url_name` with `hyperadmin.views.urls.admin_url_for`.
- A widget registry test must clean up with `unregister_widget` (module-level registry, as reports).
