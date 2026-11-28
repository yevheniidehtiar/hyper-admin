---
type: story
id: N74iNzr5um1a
title: "feat(ui): add Sortable.js drag-drop widget reordering"
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
  issue_number: 466
  repo: yevheniidehtiar/hyper-admin
  last_sync_hash: sha256:f178dab77ed46af95f9010e2f0ad22730062ca46fafd89bad373f254821a87d7
  synced_at: 2026-04-07T17:23:23.791Z
created_at: 2026-04-01T21:45:21Z
updated_at: 2026-11-20T00:00:00Z
---

## Context

Spec: `docs/specs/dashboard-builder.md` (Front end, Decision Log: drag and drop).

Users reorder cards by dragging them, or with the "Move up" / "Move down" buttons from the
keyboard. SortableJS has no keyboard model, so the buttons are the accessible path; they already
work as plain forms (`featviews-create-dashboard-view-handler.md`). This story vendors SortableJS
as a static file of the plugin (no CDN, no JS build step), wires drag and drop to
`POST {prefix}/dashboard/layout`, and upgrades the buttons to HTMX with focus restore and a live
announcement.

## Scenarios

**Scenario: dragging a card saves the new order**
  Given alice sees cards in the order `[A, B, C]`
  When  alice drags C by its handle onto the first position
  Then  a POST to `{prefix}/dashboard/layout` carries `widgets=[C, A, B]`
  And   after a reload alice sees `[C, A, B]`

**Scenario: move up from the keyboard keeps focus on the moved card**
  Given alice sees cards in the order `[A, B, C]`
  When  alice tabs to B's "Move up" button and presses Enter
  Then  the grid shows `[B, A, C]`
  And   focus is on B's "Move up" button
  And   the live region announces "Moved B to position 1 of 3"

**Scenario: a failed save puts the cards back**
  Given alice sees `[A, B, C]` and the layout POST answers 400
  When  alice drags C onto the first position
  Then  the grid shows `[A, B, C]` again
  And   an error toast says the order could not be saved

**Scenario: the vendored library is served with the plugin's static files**
  When  `GET {prefix}/static/plugins/reports/vendor/sortable-1.15.6.min.js`
  Then  the response is 200

## Acceptance Criteria

- [ ] SortableJS 1.15.6 minified build vendored at
      `static/hyperadmin_reports/vendor/sortable-1.15.6.min.js` with `LICENSE-sortablejs.txt` (MIT),
      byte-identical to the npm release; source URL and version noted in the README
- [ ] `dashboard.js`: Sortable on `[data-dashboard-grid]`, `handle: "[data-drag-handle]"`, ghost
      class for the drop placeholder; `onEnd` posts the keys in DOM order with `htmx.ajax`, swap none;
      on an error response the previous order is restored and an error toast is shown in the admin's
      toast region (as `request_errors.js` does for failed HTMX requests)
- [ ] Move buttons get `hx-post` / `hx-target="#dashboard-grid"` / `hx-swap="outerHTML"`; after
      the swap focus returns to the same button of the moved card; an `aria-live="polite"` region announces the move
- [ ] Scripts load with `defer` from `index.html`, only when controls are rendered; no inline script
- [ ] Drag handle is a `<button>` with an accessible name ("Drag to reorder {title}") and
      `data-testid="widget-drag-handle"`
- [ ] Route test for the static file; the drag and keyboard scenarios run in the E2E suite
      (`teste2e-dashboard-e2e-test-suite.md`)

## Files to Change

- `plugins/hyperadmin-reports/src/hyperadmin_reports/static/hyperadmin_reports/vendor/sortable-1.15.6.min.js` (new)
- `plugins/hyperadmin-reports/src/hyperadmin_reports/static/hyperadmin_reports/vendor/LICENSE-sortablejs.txt` (new)
- `plugins/hyperadmin-reports/src/hyperadmin_reports/static/hyperadmin_reports/dashboard.js` (new)
- `plugins/hyperadmin-reports/src/hyperadmin_reports/templates/dashboard/index.html`
- `plugins/hyperadmin-reports/src/hyperadmin_reports/templates/dashboard/_card.html`
- `plugins/hyperadmin-reports/src/hyperadmin_reports/static/hyperadmin_reports/dashboard.css`
- `plugins/hyperadmin-reports/tests/test_dashboard_routes.py`
- `plugins/hyperadmin-reports/README.md`

## Dependencies

Depends on: `featui-create-dashboard-template-with-widget-cards.md`

## Notes for Implementer

- Not a Python dependency: nothing changes in any `pyproject.toml`. Call the vendored file out in
  the PR body under "New dependencies" so the owner can veto it.
- Follow `src/hyperadmin/static/js/vendor/` (versioned file name plus licence file).
- The CSRF header comes from the `hx-headers` on `<body>`; `htmx.ajax` sends it.
