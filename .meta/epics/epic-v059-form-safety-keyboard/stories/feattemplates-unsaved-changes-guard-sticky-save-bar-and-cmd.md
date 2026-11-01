---
type: story
id: st-v059-kbd-01
title: "feat(templates): unsaved-changes guard, sticky save bar and Cmd/Ctrl+S"
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
  id: ep-v059-kbd-01
created_at: 2026-11-01T00:00:00Z
updated_at: 2026-11-01T00:00:00Z
---

## Summary

Add `static/js/form_guard.js`: mark the model form dirty on input, ask before leaving (`beforeunload`, `htmx:confirm` for requests that would replace the form), clear on submit. Make the form actions a sticky bar. Register `mod+s` in `shortcuts.js` to `requestSubmit()` the form. Opt out per model with `AdminOptions.warn_unsaved_changes=False`.

**Spec:** [`docs/specs/navigation-and-list-ux.md`](../../../../docs/specs/navigation-and-list-ux.md)

## Files to Change

- **New:** `src/hyperadmin/static/js/form_guard.js`
- **Modified:** `src/hyperadmin/templates/form_layout.html`, `static/js/shortcuts.js`, `static/css/_forms.css`
- **Modified:** `src/hyperadmin/core/options.py`
- **New:** `tests/e2e/test_form_safety.py`

## Scenarios

```
Scenario: leaving a dirty form asks first
  Given the user changed a field on the order edit form
  When  the user clicks a sidebar link
  Then  the browser asks to confirm leaving

Scenario: saving does not trigger the guard
  Given a dirty form
  When  the user clicks Save
  Then  the form submits without a leave prompt

Scenario: Cmd+S saves the form
  Given the user is on the order edit form
  When  the user presses Cmd+S
  Then  the form is submitted as if Save was clicked

Scenario: the guard can be turned off per model
  Given AdminOptions(warn_unsaved_changes=False)
  When  the user edits and leaves the form
  Then  no prompt is shown
```

## Acceptance Criteria

- [ ] Save bar stays visible while scrolling long forms (desktop and mobile)
- [ ] Popup create forms (`_popup=1`) are guarded too
- [ ] Unit tests with Scenario docstrings; `uv run poe test:cov-diff` reports 100% of changed lines
- [ ] `uv run ruff check . && uv run ruff format --check .` and `poe lint` pass
- [ ] E2E tests map 1:1 to the scenarios, use role/label/test-id locators only, with `# Given / # When / # Then` comments
- [ ] Visual baselines refreshed on Linux (`RESPONSIVE_SNAPSHOTS_UPDATE=1`) where the UI changed
- [ ] Manual test scenarios attached to the PR
- [ ] New `data-testid`s added to the CLAUDE.md reference table

## Blocked by

- `featnav-cmd-ctrl-k-command-palette-with-recent-items-and-sho` (st-v059-nav-04)

## Parent

- Epic: `epic-v059-form-safety-keyboard`
