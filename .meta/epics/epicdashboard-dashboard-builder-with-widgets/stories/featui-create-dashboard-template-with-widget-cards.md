---
type: story
id: XL2rTBZVsXbR
title: "feat(ui): create dashboard template with widget cards"
status: done
priority: medium
assignee: null
labels:
  - enhancement
  - agent-task
  - area:templates
  - size:M
  - area:frontend
estimate: null
epic_ref:
  id: _MkBhj2OoiGp
github:
  issue_number: 463
  repo: yevheniidehtiar/hyper-admin
  last_sync_hash: sha256:2f5f7720388b2d553374d088724ad25f558b4f9b969e5eae288676deee7523c4
  synced_at: 2026-04-07T17:23:23.791Z
created_at: 2026-04-01T21:45:06Z
updated_at: 2026-11-20T00:00:00Z
---

## Context

Spec: `docs/specs/dashboard-builder.md` (Front end).

The cards of the dashboard: a responsive grid, the stat card body (following
`docs/design/system/components/StatCard/README.md`), the quick-actions body, the loading skeleton,
the error state with Retry, the 403 fragment and the empty state. Each lazy card loads its body
with `hx-get` on `load`; chart cards load the report chart fragment, which brings its own loading,
no-data and error states.

## Scenarios

**Scenario: the grid renders one card per visible widget in layout order**
  Given alice sees widgets `[stat-orders-revenue, chart-orders-by-month, quick-actions]`
  When  the dashboard page renders
  Then  `data-testid="dashboard-grid"` holds cards `widget-stat-orders-revenue`,
        `widget-chart-orders-by-month`, `widget-quick-actions` in that order

**Scenario: a stat card shows the value and links to its report**
  Given the "orders-revenue" total is 600
  When  the stat widget body renders
  Then  `data-testid="stat-stat-orders-revenue"` shows "600"
  And   the card has an "Open report" link to `{prefix}/reports/orders-revenue/`

**Scenario: a stat card without data shows an em dash**
  Given the "orders-revenue" total is `None`
  When  the stat widget body renders
  Then  the value shows "—"
  And   a muted line says "No data"

**Scenario: a lazy card shows a skeleton and a fallback link before it loads**
  Given a StatWidget card
  When  the page HTML is served
  Then  the card body has `hx-get` to its fragment URL, `hx-trigger="load"` and `aria-busy="true"`
  And   the body contains an "Open report" link

**Scenario: a failed widget shows an error state with Retry**
  Given the service returned the error body for widget "broken"
  When  the body renders
  Then  it shows `data-testid="widget-error"` with the text "Widget unavailable"
  And   a Retry button re-requests the widget fragment

**Scenario: a user without visible widgets sees the empty state**
  Given the user may view none of the registered widgets
  When  the dashboard page renders
  Then  it shows `data-testid="dashboard-empty"`
  And   no "Reset layout" button is shown

**Scenario: reorder controls are hidden without persistence**
  Given the service cannot persist for the request
  When  the dashboard page renders
  Then  no card has `widget-move-up`, `widget-move-down` or `widget-drag-handle`
  And   no `dashboard-reset` button is shown

## Acceptance Criteria

- [ ] `_stat.html`, `_actions.html`, `_error.html`, `_forbidden.html` (new); `_card.html` and
      `index.html` completed (title as `ha-h4`, `span` mapped to grid columns, skeleton, Open link)
- [ ] `dashboard.css`: 4 columns from `ha-bp-lg`, 2 from `ha-bp-md`, 1 below; tokens only; works
      at 375px and 200 % zoom without horizontal scroll; dark mode via tokens
- [ ] Every `data-testid` from the SDD present; the new ones added to the CLAUDE.md `data-testid`
      reference table (one anchored hunk)
- [ ] Templates and CSS follow `docs/design/system/README.md`; no inline styles
- [ ] Route-level tests assert the rendered HTML for all 7 scenarios
- [ ] Visual baseline for the dashboard page added under `tests/e2e/snapshots/` (Linux render, per
      `docs/design/system/README.md`), or the PR says why it could not be produced

## Files to Change

- `plugins/hyperadmin-reports/src/hyperadmin_reports/templates/dashboard/index.html`
- `plugins/hyperadmin-reports/src/hyperadmin_reports/templates/dashboard/_card.html`
- `plugins/hyperadmin-reports/src/hyperadmin_reports/templates/dashboard/_stat.html` (new)
- `plugins/hyperadmin-reports/src/hyperadmin_reports/templates/dashboard/_actions.html` (new)
- `plugins/hyperadmin-reports/src/hyperadmin_reports/templates/dashboard/_error.html` (new)
- `plugins/hyperadmin-reports/src/hyperadmin_reports/templates/dashboard/_forbidden.html` (new)
- `plugins/hyperadmin-reports/src/hyperadmin_reports/static/hyperadmin_reports/dashboard.css` (new)
- `plugins/hyperadmin-reports/tests/test_dashboard_templates.py` (new)
- `CLAUDE.md`

## Dependencies

Depends on: `featviews-create-dashboard-view-handler.md`

## Notes for Implementer

- Use `ha-card` / `ha-stat` and the sizes of the StatCard design; `ha-*` classes are for styling
  only and never appear in test selectors.
- The error state returns status 200 so HTMX swaps it.
