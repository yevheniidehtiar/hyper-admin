---
type: story
id: st-v056-fl-03
title: "feat(templates+e2e): filter sidebar, saved views panel, E2E suite"
status: todo
priority: high
assignee: null
labels:
  - size:M
  - planned
  - frontend
  - tests
  - upstream-readiness
  - H12
estimate: null
epic_ref:
  id: ep-v056-fl-01
created_at: 2026-05-11T00:00:00Z
updated_at: 2026-05-11T00:00:00Z
---

## Summary

Render the filter sidebar and saved-views panel in `list.html`. Provide the
`data-testid` set the SDD requires; cover all eight SDD scenarios in
Playwright.

**Spec:** [`docs/specs/filter-library.md`](../../../../docs/specs/filter-library.md)

## Files to Change

- **New:** `src/hyperadmin/templates/components/filter_sidebar.html`
- **New:** `src/hyperadmin/templates/components/saved_views.html`
- **Modified:** `src/hyperadmin/templates/list.html` — sidebar slot
- **New:** `tests/e2e/test_filter_library.py`

## data-testid Reference

| Element | testid |
|---|---|
| Sidebar root | `filter-sidebar` |
| Individual filter widget | `filter-{slug}` |
| Date range gte / lte inputs | `filter-{slug}-gte`, `filter-{slug}-lte` |
| Multi-FK / multi-choice option | `filter-{slug}-option-{value}` |
| Apply button | `filter-apply-btn` |
| Save current view button | `save-view-btn` |
| Saved-view link | `saved-view-{id}` |
| Saved-view delete | `saved-view-delete-{id}` |

## Scenarios → Tests

| Scenario | Test function |
|---|---|
| legacy string list_filter still classifies fields | `test_legacy_string_list_filter_classifies` |
| explicit DateRangeFilter renders two date inputs | `test_daterange_filter_renders_two_inputs` |
| applying a filter swaps only the table body | `test_applying_filter_swaps_tbody_with_push_url` |
| IsOwnerFilter restricts to objects the user owns | `test_isowner_filter_restricts_to_owned_rows` |
| CurrentPeriodDefault preselects the current month on first load | `test_current_period_default_redirects_on_first_load` |
| saving the current filter set creates a SavedView row | `test_save_current_view_creates_row` |
| loading a saved view applies its querystring | `test_loading_saved_view_applies_querystring` |
| another user does not see alice's saved views | `test_saved_views_are_scoped_per_user` |

## Acceptance Criteria

- [ ] Sidebar + saved-views partials match the `data-testid` table
- [ ] All eight scenarios covered with G/W/T comments
- [ ] `poe test:e2e -k filter_library` passes locally and in CI
- [ ] Visual snapshot baseline updated

## Blocked by

- `featviews-list-htmx-swap-and-saved-views`

## Parent

- Epic: `epic-v056-filter-library`
