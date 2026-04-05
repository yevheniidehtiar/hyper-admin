---
type: story
id: BWS_v9mTbyQZ
title: "test(e2e): dashboard E2E test suite"
status: todo
priority: medium
assignee: null
labels:
  - agent-task
  - area:tests
  - size:L
estimate: null
epic_ref: null
github:
  issue_number: 469
  repo: yevheniidehtiar/hyper-admin
  last_sync_hash: sha256:3ee7d142c0919eea4cf697bfffca426dfde3f495d7bf7aa48ed2c05115e0e39f
  synced_at: 2026-04-05T09:13:33.560Z
created_at: 2026-04-01T21:45:50Z
updated_at: 2026-04-01T21:45:50Z
---

## Context

Comprehensive E2E tests for the dashboard builder: widget rendering, drag-drop reordering, error handling, and configuration.

## Scenarios

**Scenario: dashboard page loads with widget cards**
  Given a configured dashboard with 2 widgets
  When  the admin navigates to `/admin/`
  Then  2 widget cards are visible

**Scenario: count widget displays correct record count**
  Given 5 Order records in the database
  And   a CountWidget configured for Order
  When  the dashboard loads
  Then  the count widget shows "5"

**Scenario: drag-drop reorders widgets**
  Given 3 widget cards [A, B, C]
  When  C is dragged to the first position
  Then  the order becomes [C, A, B] and is persisted

**Scenario: dashboard shows empty state when no widgets configured**
  Given `dashboard_enabled=True` but no widgets configured
  When  the admin navigates to `/admin/`
  Then  an empty state message is shown

**Scenario: recent items widget shows latest records**
  Given 10 Order records and a RecentItemsWidget with `limit=3`
  When  the dashboard loads
  Then  the 3 most recent orders are shown

**Scenario: failed widget shows error card without crashing dashboard**
  Given a misconfigured widget that fails to render
  When  the dashboard loads
  Then  one error card is shown and other widgets render normally

## Acceptance Criteria

- [ ] E2E test app with dashboard, widgets, and sample data
- [ ] All 6 scenarios pass as Playwright tests
- [ ] Drag-drop test uses Playwright drag API
- [ ] Inline `# Given / # When / # Then` comments
- [ ] Accessibility-first selectors (`data-testid="widget-card"`)
- [ ] Tests verify position persistence after drag-drop

## Files Likely Affected
- `tests/e2e/test_dashboard.py` (new)
- `tests/e2e/conftest.py`

## Dependencies
Depends on: #466 (drag-drop), #468 (dashboard config)

## Notes for Implementer
- For drag-drop testing, use Playwright's `page.drag_and_drop()` or manual mouse events
- Create a test app fixture with Order model and pre-seeded data
- Follow patterns in existing E2E tests (`tests/e2e/test_list_view.py`)
