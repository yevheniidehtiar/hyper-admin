---
type: story
id: st-v055-bulk-04
title: "test(e2e): bulk action scenarios via Playwright"
status: todo
priority: high
assignee: null
labels:
  - size:M
  - planned
  - tests
  - upstream-readiness
  - H3
estimate: null
epic_ref:
  id: ep-v055-bulk-01
created_at: 2026-05-10T00:00:00Z
updated_at: 2026-05-10T00:00:00Z
---

## Summary

Translate the six BDD scenarios in `docs/specs/bulk-actions.md` to Playwright
tests under `tests/e2e/`. One test per scenario, named after the scenario
title. Inline `# Given / # When / # Then` comments are mandatory.

Use `get_by_role`, `get_by_label`, `get_by_text`, `get_by_test_id` — never
`.ha-*` CSS selectors.

## Files to Change

- **New:** `tests/e2e/test_bulk_actions.py`
- **Modified:** `tests/e2e/conftest.py` (if a new admin fixture is required)

## Scenarios → Tests

| Scenario | Test function |
|---|---|
| bulk action with no selection re-renders list with warning | `test_bulk_action_with_no_selection_shows_warning` |
| bulk action with param form prompts before running | `test_bulk_action_with_param_form_prompts_before_running` |
| bulk action with valid params runs over selected rows | `test_bulk_action_with_valid_params_runs_over_selected_rows` |
| per-row failure is surfaced without aborting the bulk run | `test_per_row_failure_is_surfaced` |
| requires_selection blocks zero-row submission server-side | `test_requires_selection_blocks_zero_row_post` |
| object-level permission is enforced per row | `test_object_permission_enforced_per_row` |

## Acceptance Criteria

- [ ] Six Playwright tests, one per scenario, with mandatory G/W/T comments
- [ ] Each test uses accessibility-first locators or `data-testid` only
- [ ] `poe test:e2e -k bulk_actions` passes locally and in CI
- [ ] Visual snapshots refreshed if list/result templates change

## Blocked by

- `feattemplates-add-checkbox-column-and-bulk-toolbar`

## Parent

- Epic: `epic-v055-bulk-actions`
