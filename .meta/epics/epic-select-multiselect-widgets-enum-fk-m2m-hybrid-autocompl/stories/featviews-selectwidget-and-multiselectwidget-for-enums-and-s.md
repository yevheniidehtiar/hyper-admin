---
type: story
id: DbPPKwPpLTa4
title: "feat(views): SelectWidget and MultiSelectWidget for enums and static lists"
status: done
priority: medium
assignee: null
labels:
  - enhancement
  - agent-task
estimate: null
epic_ref:
  id: -TGq_yaQZtX_
github:
  issue_number: 163
  repo: yevheniidehtiar/hyper-admin
  last_sync_hash: sha256:b933ebfccdefe31e4ca02b38145c3b4db9806d9fc9b31d6d39c12e3778335bd4
  synced_at: 2026-04-07T17:23:23.790Z
created_at: 2026-03-20T15:37:13Z
updated_at: 2026-03-26T23:50:59Z
---

> **Part of:** #159
> **Depends on: #160, #162**

## Context

The current `SelectInput` widget only handles Enum fields via direct template iteration.
We need a first-class `SelectWidget` and `MultiSelectWidget` that accept a `choices` list at construction,
support hybrid `list[str]` fields, and handle value coercion (CSV / JSON ↔ Python list).

## Acceptance Criteria

- [ ] `SelectWidget(HtmxWidget)` in `views/forms.py`:
  - Accepts `choices: list[ChoiceItem]` at construction
  - Renders single `<select>` with correct `selected` state
  - Uses `template_path = "widgets/select_input.html"`
- [ ] `MultiSelectWidget(HtmxWidget)`:
  - Accepts `choices: list[ChoiceItem]`
  - Renders `<select multiple>` or equivalent
  - Uses `template_path = "widgets/multiselect_input.html"`
- [ ] `HybridFieldCoercer` utility (pure function, not a class) in `views/forms.py`:
  - `to_python(raw: str | list, storage: Literal["json","csv"]) -> list[str]`
  - `to_storage(value: list[str], storage: Literal["json","csv"]) -> str`
- [ ] Backward-compatible: existing `SelectInput` (Enum) continues to work unchanged
- [ ] Unit tests for widget rendering and coercer round-trips

## Files Likely Affected

- `src/hyperadmin/views/forms.py`
- `src/hyperadmin/templates/widgets/select_input.html` (update)
- `src/hyperadmin/templates/widgets/multiselect_input.html` (new)
- `tests/unit/test_forms.py`

## Dependencies

Depends on: #160, #162

## Notes for Implementer

`ChoiceItem.selected` must be set correctly before passing to the widget — the form layer sets it, not the widget.
The `MultiSelectWidget` must emit all selected values as multiple `<option selected>` tags, not a single comma string, so HTML form submission sends `field=v1&field=v2`.
