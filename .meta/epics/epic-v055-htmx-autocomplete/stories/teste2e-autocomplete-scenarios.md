---
type: story
id: st-v055-ac-04
title: "test(e2e): HTMX autocomplete scenarios via Playwright"
status: todo
priority: high
assignee: null
labels:
  - size:M
  - planned
  - tests
  - upstream-readiness
  - H6
estimate: null
epic_ref:
  id: ep-v055-ac-01
created_at: 2026-05-10T00:00:00Z
updated_at: 2026-05-10T00:00:00Z
---

## Summary

Translate the seven BDD scenarios in `docs/specs/htmx-autocomplete.md` to
Playwright tests under `tests/e2e/`. One test per scenario, named after the
scenario title. Inline `# Given / # When / # Then` comments are mandatory.

Use accessibility-first locators and the new `data-testid` selectors:
`autocomplete-{field}`, `autocomplete-select-{field}`,
`autocomplete-add-{field}`, `popup-root`.

## Files to Change

- **New:** `tests/e2e/test_htmx_autocomplete.py`
- **Modified:** `tests/e2e/conftest.py` (if a Supplier/Product fixture is needed)

## Scenarios → Tests

| Scenario | Test function |
|---|---|
| FK field renders an autocomplete widget by default | `test_fk_field_renders_autocomplete_widget_by_default` |
| dependent FK forwards the parent value via hx-include | `test_dependent_fk_forwards_parent_via_hx_include` |
| dependent FK with no parent value lists nothing | `test_dependent_fk_with_no_parent_lists_nothing` |
| "+" popup creates the related row and selects it | `test_popup_creates_related_row_and_selects_it` |
| "+" popup is hidden when the related model is not registered | `test_popup_hidden_when_related_model_unregistered` |
| display_template renders custom option rows | `test_display_template_renders_custom_option_rows` |
| choices_view rejects unknown relation field | `test_choices_view_rejects_unknown_relation_field` |

## Acceptance Criteria

- [ ] Seven Playwright tests, one per scenario, mandatory G/W/T comments
- [ ] Only accessibility-first or `data-testid` locators (no `.ha-*`)
- [ ] `poe test:e2e -k autocomplete` passes locally and in CI
- [ ] Visual snapshots refreshed if templates change

## Blocked by

- `feattemplates-autocomplete-widget-and-popup-modal`

## Parent

- Epic: `epic-v055-htmx-autocomplete`
