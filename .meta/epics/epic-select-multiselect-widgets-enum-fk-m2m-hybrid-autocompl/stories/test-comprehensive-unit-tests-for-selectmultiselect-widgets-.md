---
type: story
id: rLdY85eBJfmc
title: "test: comprehensive unit tests for select/multiselect widgets, adapters, and coercion"
status: done
priority: medium
assignee: null
labels:
  - agent-task
estimate: null
epic_ref:
  id: -TGq_yaQZtX_
github:
  issue_number: 173
  repo: yevheniidehtiar/hyper-admin
  last_sync_hash: sha256:9a092218066adb1e0af645f324c4aa692fc7924d70985005dece7777ece405df
  synced_at: 2026-04-07T17:23:23.790Z
created_at: 2026-03-20T20:07:30Z
updated_at: 2026-03-28T17:45:58Z
---

> **Part of:** #159
> **Depends on: #163, #164, #165, #166, #167, #168**

## Context

Each prior issue carries its own unit tests, but this issue covers integration-level
unit tests that exercise the full pipeline: field classification → widget selection →
form binding → coercion → adapter choices — without a real DB or browser.

## Acceptance Criteria

- [ ] Test module `tests/unit/test_select_widget_pipeline.py` covering end-to-end unit scenarios:
  - Enum field → `SelectWidget` auto-selected → renders correct `<option>` markup
  - `list[Enum]` → `MultiSelectWidget` → multiselect rendered
  - `list[str]` hybrid → `MultiSelectWidget` → CSV round-trip: bind → coerce → validate → coerce back
  - FK field (mocked mapper) → `RelationSelectWidget` with `preload=True` → choices injected
  - FK field with `preload=False` → HTMX attrs present, no adapter call at render
  - M2M field → `RelationMultiSelectWidget` → list of PKs bound correctly
  - Dependent select: `dependent_on` set → HTMX `hx-include` attr in rendered HTML
  - Unchecked multiselect (empty list) → valid empty list, no crash
  - Oversized `limit` (>200) on choices endpoint → HTTP 400
  - Missing field on choices endpoint → HTTP 404
- [ ] All tests run via `poe test:unit` with no additional setup
- [ ] Query counter fixture reused from #161 to assert N+1 never occurs in preload path

## Files Likely Affected

- `tests/unit/test_select_widget_pipeline.py` (new)
- `tests/conftest.py` (add shared fixtures if needed)

## Dependencies

Depends on: #160, #161, #162, #163, #164, #165, #166, #167, #168

## Notes for Implementer

Use `MockFieldInfo` pattern already established in `tests/unit/test_forms.py`.
Mock the adapter via `unittest.mock.AsyncMock` — do not hit a real DB.
Keep each test function focused on one scenario; name them descriptively.
