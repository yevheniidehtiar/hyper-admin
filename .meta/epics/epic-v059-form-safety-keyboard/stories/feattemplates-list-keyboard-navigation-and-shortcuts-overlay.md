---
type: story
id: st-v059-kbd-02
title: "feat(templates): list keyboard navigation and shortcuts overlay"
status: backlog
priority: medium
assignee: null
labels:
  - size:M
  - planned
  - area:templates
  - frontend
  - ui
estimate: null
epic_ref:
  id: ep-v059-kbd-01
created_at: 2026-11-01T00:00:00Z
updated_at: 2026-11-01T00:00:00Z
---

## Summary

Register list shortcuts in `shortcuts.js`: `j`/`k` focus the next or previous `row-link`, Enter opens it, `x` toggles the bulk checkbox, `c` goes to create. `?` opens `components/shortcuts_overlay.html` listing every registered shortcut, with a switch that turns single-key shortcuts off (WCAG 2.1.4).

**Spec:** [`docs/specs/navigation-and-list-ux.md`](../../../../docs/specs/navigation-and-list-ux.md)

## Files to Change

- **Modified:** `src/hyperadmin/static/js/shortcuts.js`
- **New:** `src/hyperadmin/templates/components/shortcuts_overlay.html`
- **Modified:** `src/hyperadmin/templates/_base.html`
- **New:** `tests/e2e/test_keyboard_navigation.py`

## Scenarios

```
Scenario: j/k move between rows and Enter opens one
  Given a list of 3 orders
  When  the user presses j twice and then Enter
  Then  the second row's record opens

Scenario: x selects the focused row
  Given a list with a bulk action and row 1 focused
  When  the user presses x
  Then  row 1's checkbox is checked and the bulk bar shows "1 selected"

Scenario: single-key shortcuts can be turned off
  Given the user turns shortcuts off in the ? overlay
  When  the user presses j on a list
  Then  nothing happens and Cmd+K still opens the palette

Scenario: typing in the search box is not hijacked
  Given focus is in the list search input
  When  the user types "jack"
  Then  the input contains "jack" and no row is focused
```

## Acceptance Criteria

- [ ] Off state persisted in localStorage `ha-shortcuts`
- [ ] Overlay is a native `<dialog>` with focus management
- [ ] Unit tests with Scenario docstrings; `uv run poe test:cov-diff` reports 100% of changed lines
- [ ] `uv run ruff check . && uv run ruff format --check .` and `poe lint` pass
- [ ] E2E tests map 1:1 to the scenarios, use role/label/test-id locators only, with `# Given / # When / # Then` comments
- [ ] Visual baselines refreshed on Linux (`RESPONSIVE_SNAPSHOTS_UPDATE=1`) where the UI changed
- [ ] Manual test scenarios attached to the PR
- [ ] New `data-testid`s added to the CLAUDE.md reference table

## Blocked by

- `featnav-cmd-ctrl-k-command-palette-with-recent-items-and-sho` (st-v059-nav-04)
- `feattemplates-clickable-list-rows-and-edit-delete-on-detail` (st-v059-list-02)

## Parent

- Epic: `epic-v059-form-safety-keyboard`
