---
type: story
id: hv72do4RQve1
title: "test(e2e): dashboard E2E test suite"
status: done
priority: medium
assignee: null
labels:
  - agent-task
  - area:tests
  - size:L
estimate: null
epic_ref:
  id: _MkBhj2OoiGp
github:
  issue_number: 469
  repo: yevheniidehtiar/hyper-admin
  last_sync_hash: sha256:3ee7d142c0919eea4cf697bfffca426dfde3f495d7bf7aa48ed2c05115e0e39f
  synced_at: 2026-04-07T17:23:23.791Z
created_at: 2026-04-01T21:45:50Z
updated_at: 2026-11-20T00:00:00Z
---

## Context

Spec: `docs/specs/dashboard-builder.md` (BDD Scenarios).

End-to-end tests for the dashboard through a real browser: rendering, permissions, failure
isolation, drag and drop, keyboard reorder, per-user layout and reset. They run against a new
E2E app with generic Order data, two reports, a quick-actions widget and a deliberately failing
custom widget, with the layout table created.

## Scenarios

**Scenario: dashboard replaces the welcome page when widgets are registered**
  Given the dashboard app with registered widgets
  When  alice opens `{prefix}/`
  Then  `dashboard-grid` is visible
  And   the text "Welcome to HyperAdmin Dashboard" is not on the page

**Scenario: stat widget shows the grand total of its report aggregate**
  Given Orders with amounts 100, 200 and 300
  When  alice opens the dashboard
  Then  `stat-stat-orders-revenue` shows "600"

**Scenario: chart widget embeds the report chart fragment**
  Given a ChartWidget over "orders-by-month"
  When  alice opens the dashboard
  Then  the card `widget-chart-orders-by-month` contains `report-chart`

**Scenario: quick actions widget shows only the actions the user may use**
  Given user "viewer" lacks `add_order`
  When  viewer opens the dashboard
  Then  the quick actions card has the link "All reports"
  And   it has no link "New order"

**Scenario: widgets the user may not view are not shown**
  Given user "viewer" lacks `view_report_payroll_total`
  When  viewer opens the dashboard
  Then  the card `widget-stat-payroll-total` is not on the page

**Scenario: failing widget shows an error state and the others render**
  Given the custom widget "broken" raises in `render()`
  When  alice opens the dashboard
  Then  the card `widget-broken` shows `widget-error` with a "Retry" button
  And   `stat-stat-orders-revenue` shows "600"

**Scenario: drag and drop saves the new order**
  Given alice sees the default order
  When  alice drags the last card's handle onto the first card
  Then  after a reload the last card is first

**Scenario: move up button reorders without drag and drop**
  Given alice sees cards `[A, B, C]`
  When  alice focuses B's "Move up" button and presses Enter
  Then  the cards are `[B, A, C]`
  And   B's "Move up" button is focused

**Scenario: layout is per user**
  Given alice moved a card
  When  bob opens the dashboard
  Then  bob sees the default order

**Scenario: reset returns to the default order**
  Given alice moved a card
  When  alice clicks "Reset layout"
  Then  alice sees the default order

**Scenario: user with no visible widgets sees an empty state**
  Given user "nobody" holds no report permission
  When  nobody opens the dashboard
  Then  `dashboard-empty` is visible

## Acceptance Criteria

- [ ] E2E app `tests/e2e/apps/dashboard_builder.py`: Order model, reports "orders-revenue",
      "orders-by-month", "payroll-total", widgets as in the scenarios, users alice (superuser),
      bob (same permissions as alice, not superuser), viewer, nobody (`secret123`), layout table created
- [ ] Fixture `dashboard_base_url` in `tests/e2e/plugins/conftest.py` (not the hotspot `tests/e2e/conftest.py`)
- [ ] One Playwright test per scenario, named after it, with `# Given / # When / # Then` comments
- [ ] Locators: `get_by_role`, `get_by_label`, `get_by_text`, `get_by_test_id` only; no `.ha-*` selectors
- [ ] Drag uses `locator.drag_to()` on the drag handle; persistence asserted after `page.reload()`
- [ ] All 11 tests pass locally

## Files to Change

- `tests/e2e/apps/dashboard_builder.py` (new)
- `tests/e2e/plugins/conftest.py`
- `tests/e2e/plugins/test_dashboard.py` (new)

## Dependencies

Depends on: `featui-add-sortablejs-drag-drop-widget-reordering.md`

## Notes for Implementer

- Follow `tests/e2e/apps/olap_reporting.py` and `tests/e2e/plugins/test_tasks_ui.py`.
- Register reports and widgets at import time of the app module, before `Admin(...)`.
