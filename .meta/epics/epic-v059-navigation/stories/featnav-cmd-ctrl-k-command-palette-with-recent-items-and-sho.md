---
type: story
id: st-v059-nav-04
title: "feat(nav): Cmd/Ctrl+K command palette with recent items and shortcut registry"
status: backlog
priority: high
assignee: null
labels:
  - size:M
  - planned
  - area:templates
  - frontend
  - ui
estimate: null
epic_ref:
  id: ep-v059-nav-01
created_at: 2026-11-01T00:00:00Z
updated_at: 2026-11-01T00:00:00Z
---

## Summary

Add `components/command_palette.html` (native `<dialog>`, Combobox ARIA), a permission-filtered JSON data island of the nav tree, client-side matching over model, group and plugin page labels, recent pages and records in localStorage `ha-recent`, a navbar trigger, and `static/js/shortcuts.js` (shared registry, single-key off switch). Cmd/Ctrl+K opens the palette; `/` keeps focusing the list search.

**Spec:** [`docs/specs/navigation-and-list-ux.md`](../../../../docs/specs/navigation-and-list-ux.md)

## Files to Change

- **New:** `src/hyperadmin/templates/components/command_palette.html`
- **New:** `src/hyperadmin/static/js/palette.js`, `static/js/shortcuts.js`, `static/css/_palette.css`
- **Modified:** `src/hyperadmin/templates/_base.html`, `_navbar.html`, `list.html`, `detail.html`, `update.html` (`data-ha-recent`)
- **New:** `tests/unit/test_command_palette.py`, `tests/e2e/test_command_palette.py`

## Scenarios

```
Scenario: the palette finds a model by group name
  Given "Accounting" contains Invoices and Bills
  When  the user presses Cmd+K and types "acco"
  Then  Invoices and Bills are listed and Enter on Invoices opens /admin/invoice

Scenario: the palette offers "New" only where allowed
  Given the user holds view_invoice but not add_invoice
  When  the user searches "invoice"
  Then  the Invoices result has no "New invoice" action

Scenario: the palette lists recent records
  Given the user opened the edit page of order "ORD-1042"
  When  the user opens the palette with an empty query
  Then  "ORD-1042" is listed under Recent

Scenario: forbidden models never reach the page
  Given the user lacks view_invoice
  When  any admin page renders
  Then  the ha-nav-data island contains no Invoices entry

Scenario: Esc closes and returns focus
  Given the palette was opened from the navbar trigger
  When  the user presses Esc
  Then  the dialog closes and focus is back on the trigger
```

## Acceptance Criteria

- [ ] Works on the dashboard (lives in `_base.html`)
- [ ] No DB query added per keystroke (client-side only)
- [ ] Existing Cmd/Ctrl+K handler in `_base.html` moved into `shortcuts.js`
- [ ] localStorage access wrapped in try/catch
- [ ] JS stays plain ES2019, no build step; combined new JS ≤ 8 KB
- [ ] Unit tests with Scenario docstrings; `uv run poe test:cov-diff` reports 100% of changed lines
- [ ] `uv run ruff check . && uv run ruff format --check .` and `poe lint` pass
- [ ] E2E tests map 1:1 to the scenarios, use role/label/test-id locators only, with `# Given / # When / # Then` comments
- [ ] Visual baselines refreshed on Linux (`RESPONSIVE_SNAPSHOTS_UPDATE=1`) where the UI changed
- [ ] Manual test scenarios attached to the PR
- [ ] New `data-testid`s added to the CLAUDE.md reference table

## Notes for Implementer

Hotspot owner for `_base.html` until kbd-01 starts. Serialize labels with `tojson` in the request locale. Reuse the Combobox design-system CSS.

## Blocked by

- `featcore-nav-tree-with-navgroup-nav-group-nav-order-and-a-do` (st-v059-nav-01)

## Parent

- Epic: `epic-v059-navigation`
