---
type: story
id: st-v059-list-02
title: "feat(templates): clickable list rows and Edit/Delete on detail and edit pages"
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

Remove the View and Edit row buttons. The title cell (first non-inline-editable column) becomes `<th scope="row">` with a real `<a data-testid="row-link">` to `row_target`, stretched over the row with CSS; checkbox, inline-edit cells, cell links and the delete button sit above it. The detail page gets Edit and Delete; the edit page gets "View" and Delete.

**Spec:** [`docs/specs/navigation-and-list-ux.md`](../../../../docs/specs/navigation-and-list-ux.md)

## Files to Change

- **Modified:** `src/hyperadmin/templates/components/table_body.html`, `components/table.html`
- **Modified:** `src/hyperadmin/templates/detail.html`, `form_layout.html`
- **Modified:** `src/hyperadmin/static/css/_table.css`
- **Modified:** `docs/design/system/components/DataTable/README.md`, `CLAUDE.md`, `CHANGELOG.md`
- **Modified:** e2e tests that click row buttons (`test_list_view.py`, `test_object_permissions.py`, `test_pk_types.py`, `test_qualification.py`, …)

## Scenarios

```
Scenario: clicking a row opens the edit page for an editor
  Given alice holds change_order
  When  alice clicks the row of order 42 outside its controls
  Then  /admin/order/42/edit opens

Scenario: clicking a row opens the detail page for a read-only user
  Given bob holds view_order only
  When  bob clicks the row of order 42
  Then  /admin/order/42 opens

Scenario: row controls do not trigger the row link
  Given Order has a bulk action and list_editable=["status"]
  When  the user ticks the checkbox or clicks the status cell
  Then  the row is selected or the inline editor opens, without navigation

Scenario: the row link works as a link
  When  the user middle-clicks a row's title link
  Then  the record opens in a new tab

Scenario: the detail page offers Edit to editors
  Given alice holds change_order
  When  alice opens /admin/order/42
  Then  an "Edit" link (detail-edit-link) leads to /admin/order/42/edit
```

## Acceptance Criteria

- [ ] `row-view-link` / `row-edit-link` removed from templates, tests and CLAUDE.md; `row-link` added
- [ ] All-editable rows get a `chevron-right` open link cell
- [ ] Card layout (mobile) keeps the whole card clickable
- [ ] DataTable README updated (title link → edit or detail by permission)
- [ ] CHANGELOG "Changed" entry for the removed test ids
- [ ] Unit tests with Scenario docstrings; `uv run poe test:cov-diff` reports 100% of changed lines
- [ ] `uv run ruff check . && uv run ruff format --check .` and `poe lint` pass
- [ ] E2E tests map 1:1 to the scenarios, use role/label/test-id locators only, with `# Given / # When / # Then` comments
- [ ] Visual baselines refreshed on Linux (`RESPONSIVE_SNAPSHOTS_UPDATE=1`) where the UI changed
- [ ] Manual test scenarios attached to the PR
- [ ] New `data-testid`s added to the CLAUDE.md reference table

## Notes for Implementer

Ship in one PR with list-03 as separate commits (both own `table_body.html`).

## Blocked by

- `featviews-per-user-row-target-and-delete-permission-in-the-l` (st-v059-list-01)

## Parent

- Epic: `epic-v059-compact-list-rows`
