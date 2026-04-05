---
type: story
id: 8Wv1KsLdSIQb
title: "feat(ui): add Sortable.js drag-drop widget reordering"
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
  issue_number: 466
  repo: yevheniidehtiar/hyper-admin
  last_sync_hash: sha256:f178dab77ed46af95f9010e2f0ad22730062ca46fafd89bad373f254821a87d7
  synced_at: 2026-04-05T09:13:33.560Z
created_at: 2026-04-01T21:45:21Z
updated_at: 2026-04-01T21:45:21Z
---

## Context

Users should be able to reorder dashboard widgets by drag-and-drop. Uses Sortable.js (CDN) with HTMX integration for saving positions.

## Scenarios

**Scenario: dragging a widget card to new position saves order**
  Given a dashboard with 3 widgets in order [A, B, C]
  When  widget C is dragged to position 0
  Then  an HTMX POST to `/admin/dashboard/save-order` is sent
  And   the new order [C, A, B] is persisted

**Scenario: drag-drop is keyboard accessible**
  Given a widget card is focused
  When  Space is pressed to grab, Arrow keys to move, Space to drop
  Then  the widget is repositioned and order is saved

**Scenario: drag-drop visual feedback shows drop target**
  Given a widget is being dragged
  When  it hovers over a valid drop target
  Then  a visual placeholder indicates the drop position

## Acceptance Criteria

- [ ] Sortable.js loaded from CDN in dashboard template
- [ ] `dashboard.js` initializes Sortable on widget grid container
- [ ] On drop: collect new positions, POST to save-order via HTMX
- [ ] Keyboard accessibility: Space to grab/drop, arrows to move
- [ ] Ghost/placeholder element during drag
- [ ] Visual feedback (opacity, border) on drag
- [ ] Unit/integration tests for position save endpoint

## Files Likely Affected
- `src/hyperadmin/templates/dashboard.html` — Sortable.js script tag + init
- `src/hyperadmin/static/js/dashboard.js` (new)

## Dependencies
Depends on: #463 (dashboard template with widget cards)

## Notes for Implementer
- Sortable.js CDN: `https://cdn.jsdelivr.net/npm/sortablejs@latest/Sortable.min.js`
- On `onEnd` event: build position array, send via `htmx.ajax("POST", ...)`
- Follow HTMX pattern used elsewhere in the project
- Keyboard support: Sortable.js has built-in keyboard handling when configured
