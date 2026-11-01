---
type: story
id: st-v059-list-03
title: "feat(templates): red icon delete with a shared confirm dialog"
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
  id: ep-v059-list-01
created_at: 2026-11-01T00:00:00Z
updated_at: 2026-11-01T00:00:00Z
---

## Summary

Replace the text Delete button and native `hx-confirm` with a ghost icon button (`trash-2` in `ha-color-danger-text`, `aria-label="Delete {object}"`, tooltip) shown only when `user_can_delete`, opening one shared `components/confirm_delete_dialog.html` (`role="alertdialog"`, focus on Cancel, solid danger confirm) that issues the DELETE via `htmx.ajax`. The same dialog serves the detail and edit pages.

**Spec:** [`docs/specs/navigation-and-list-ux.md`](../../../../docs/specs/navigation-and-list-ux.md)

## Files to Change

- **New:** `src/hyperadmin/templates/components/confirm_delete_dialog.html`
- **Modified:** `src/hyperadmin/templates/base.html`, `components/table_body.html`, `detail.html`, `form_layout.html`
- **Modified:** `src/hyperadmin/static/css/_forms.css` (dialog), `_table.css`
- **Modified:** `tests/e2e/test_update_delete_view.py`, `docs/design/system/README.md`

## Scenarios

```
Scenario: delete asks for confirmation in a dialog
  Given alice holds delete_order
  When  alice clicks the delete icon on "ORD-1042"
  Then  an alertdialog "Delete ORD-1042?" opens with focus on Cancel

Scenario: cancelling keeps the record
  When  alice presses Cancel (or Esc)
  Then  the dialog closes, the row remains and focus returns to the delete icon

Scenario: confirming deletes and reloads the list
  When  alice confirms
  Then  the order is deleted and the list reloads without it

Scenario: users without delete_order see no delete icon
  Given bob lacks delete_order
  When  bob opens the order list
  Then  no row-delete-btn is rendered

Scenario: a protected record shows the error toast
  Given the order is referenced by a PROTECT foreign key
  When  alice confirms its deletion
  Then  the dialog closes and the 409 error toast is shown
```

## Acceptance Criteria

- [ ] CSRF header applied (`htmx.ajax` with `source` inside `<body hx-headers>`)
- [ ] `tests/e2e/test_update_delete_view.py:47,60` move from `page.on("dialog")` to `get_by_role("alertdialog")`
- [ ] `docs/design/system/README.md` line about `hx-confirm` updated
- [ ] `dialog-confirm-delete` added to CLAUDE.md
- [ ] Unit tests with Scenario docstrings; `uv run poe test:cov-diff` reports 100% of changed lines
- [ ] `uv run ruff check . && uv run ruff format --check .` and `poe lint` pass
- [ ] E2E tests map 1:1 to the scenarios, use role/label/test-id locators only, with `# Given / # When / # Then` comments
- [ ] Visual baselines refreshed on Linux (`RESPONSIVE_SNAPSHOTS_UPDATE=1`) where the UI changed
- [ ] Manual test scenarios attached to the PR
- [ ] New `data-testid`s added to the CLAUDE.md reference table

## Notes for Implementer

Reuse the native `<dialog>` + `showModal()` pattern from `components/saved_views.html:45-53`.

## Blocked by

- `feattemplates-clickable-list-rows-and-edit-delete-on-detail` (st-v059-list-02)

## Parent

- Epic: `epic-v059-compact-list-rows`
