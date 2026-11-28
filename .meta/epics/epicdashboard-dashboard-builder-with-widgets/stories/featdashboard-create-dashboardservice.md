---
type: story
id: Md4cN4uup9FF
title: "feat(dashboard): create DashboardService"
status: done
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
  issue_number: 460
  repo: yevheniidehtiar/hyper-admin
  last_sync_hash: sha256:fcbb3a870d4dacce0b7d37938dc112edc7e153fd52c405f1180db4d591c6c657
  synced_at: 2026-04-07T17:23:23.791Z
created_at: 2026-04-01T21:44:36Z
updated_at: 2026-11-20T00:00:00Z
---

## Context

Spec: `docs/specs/dashboard-builder.md` (Service, Edge Cases).

`DashboardService` holds the dashboard's rules so the routes stay thin: which widgets a user may
see, in which order, which orders may be saved, and how a failing widget is contained. It combines
the widget registry (`featdashboard-create-dashboardwidget-protocol-and-built-in-w.md`) with the
layout store (`featdashboard-create-dashboard-data-models.md`).

## Scenarios

**Scenario: a saved order is applied**
  Given widgets A, B, C are registered in that order
  And   alice saved `[C, A, B]`
  When  `layout_for(alice_request)` is awaited
  Then  the widgets come back as `[C, A, B]`

**Scenario: a user without a saved order gets the default order**
  Given widgets A, B, C are registered in that order and bob has no row
  When  `layout_for(bob_request)` is awaited
  Then  the widgets come back as `[A, B, C]`

**Scenario: widgets the user may not view are left out**
  Given widget P requires `view_report_payroll_total`
  And   user "viewer" lacks it
  When  `layout_for(viewer_request)` is awaited
  Then  P is not in the result

**Scenario: a widget missing from the saved order is appended**
  Given alice saved `[B, A]` and widgets A, B, C are registered
  When  `layout_for(alice_request)` is awaited
  Then  the widgets come back as `[B, A, C]`

**Scenario: an unknown key in the saved order is dropped**
  Given alice saved `[old, A, B]` and "old" is not registered
  When  `layout_for(alice_request)` is awaited
  Then  the widgets come back as `[A, B]`

**Scenario: an order that is not a permutation of the visible keys is rejected**
  Given alice sees `[A, B, C]`
  When  `save_order(alice_request, ["A", "B", "P"])` is awaited
  Then  `LayoutRejectedError` is raised
  And   alice's stored order is unchanged

**Scenario: move up swaps a widget with its predecessor**
  Given alice sees `[A, B, C]`
  When  `move(alice_request, "B", "up")` is awaited
  Then  the result and the stored order are `[B, A, C]`

**Scenario: moving the first widget up changes nothing**
  Given alice sees `[A, B, C]`
  When  `move(alice_request, "A", "up")` is awaited
  Then  the result is `[A, B, C]`

**Scenario: a failing widget renders an error body**
  Given a widget whose `render()` raises `RuntimeError`
  When  `render_body(request, widget)` is awaited
  Then  the body template is `dashboard/_error.html` with the widget key and a retry URL
  And   the error is logged at ERROR with its traceback

**Scenario: a missing layout table turns persistence off once**
  Given the layout table does not exist
  When  `layout_for` is awaited twice
  Then  both calls return the default order
  And   `can_persist` is `False`
  And   one warning naming `hyperadmin_reports_dashboard_layout` is logged

## Acceptance Criteria

- [ ] `DashboardService(admin, store)` with `can_persist`, `visible`, `layout_for`, `save_order`,
      `move`, `reset`, `render_body` as in the SDD
- [ ] Permission checks through `admin_context.has_permission`; no auth means every widget is visible
- [ ] `user_key` read from `request.state.user_key`; without it `can_persist` is `False` for that
      request and the write methods raise `PermissionError`
- [ ] `LayoutRejectedError` for unknown, hidden, duplicate or missing keys and for a bad move key or direction
- [ ] `store=None` (`dashboard_layouts=False`) means no table access and no warning
- [ ] Unit tests cover all 10 scenarios

## Files to Change

- `plugins/hyperadmin-reports/src/hyperadmin_reports/dashboard/service.py` (new)
- `plugins/hyperadmin-reports/src/hyperadmin_reports/dashboard/__init__.py`
- `plugins/hyperadmin-reports/tests/test_dashboard_service.py` (new)

## Dependencies

Depends on: `featdashboard-create-dashboard-data-models.md`,
`featdashboard-create-dashboardwidget-protocol-and-built-in-w.md`

## Notes for Implementer

- Widget bodies are rendered one per request (HTMX lazy load); the service does not gather all
  widgets in one call.
- Catch `Exception` in `render_body` only; `HTTPException` is not raised by widgets.
