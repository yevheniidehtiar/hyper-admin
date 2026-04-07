---
type: story
id: XL2rTBZVsXbR
title: "feat(ui): create dashboard template with widget cards"
status: todo
priority: medium
assignee: null
labels:
  - enhancement
  - agent-task
  - area:templates
  - size:M
  - area:frontend
estimate: null
epic_ref: null
github:
  issue_number: 463
  repo: yevheniidehtiar/hyper-admin
  last_sync_hash: sha256:2f5f7720388b2d553374d088724ad25f558b4f9b969e5eae288676deee7523c4
  synced_at: 2026-04-07T17:23:23.791Z
created_at: 2026-04-01T21:45:06Z
updated_at: 2026-04-01T21:45:06Z
---

## Context

The dashboard template needs to render widget cards in a responsive grid. Each card shows the widget title, content, and handles loading/error states.

## Scenarios

**Scenario: dashboard renders widget cards in a responsive grid**
  Given a dashboard with 4 widgets
  When  the dashboard page loads
  Then  4 widget cards are rendered in a CSS grid layout

**Scenario: widget card displays title, content, and loading state**
  Given a CountWidget with title "Total Orders"
  When  the widget card renders
  Then  it shows the title "Total Orders" and the count value

**Scenario: error widget card shows error message**
  Given a widget that failed to render
  When  the dashboard page loads
  Then  the widget card shows "Widget unavailable" with a retry button

## Acceptance Criteria

- [ ] `dashboard.html` template updated with widget card grid
- [ ] `components/widget_card.html` component template (new)
- [ ] Responsive CSS grid (1-col mobile, 2-col tablet, 3-col desktop)
- [ ] Widget card: title bar, content area, loading spinner, error state
- [ ] Type-specific content rendering (count number, item list, action links)
- [ ] `data-testid="widget-card"`, `data-testid="widget-title"` for E2E
- [ ] Empty state message when no widgets configured

## Files Likely Affected
- `src/hyperadmin/templates/dashboard.html`
- `src/hyperadmin/templates/components/widget_card.html` (new)

## Dependencies
Depends on: #462 (dashboard view handler — provides template context)

## Notes for Implementer
- Use HTMX for widget loading: `hx-get` to load widget content lazily
- Widget card CSS: `ha-widget-card`, `ha-widget-title`, `ha-widget-content`
- Error card: red border, "Widget unavailable" text, retry icon button
- Follow existing template patterns (e.g., `components/filter_bar.html`)
