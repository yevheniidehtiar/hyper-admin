---
type: story
id: cYQJ8fjx301U
title: "feat(views): multiselect form binding and value coercion (list↔JSON/CSV)"
status: done
priority: medium
assignee: null
labels:
  - enhancement
  - agent-task
  - size:XL
estimate: null
epic_ref:
  id: IYTFerusYXD-
github:
  issue_number: 168
  repo: yevheniidehtiar/hyper-admin
  last_sync_hash: sha256:bf28ca7a158760784ef91054f1c54957cbfdc5c73d091c71efe8d903d1d14d57
  synced_at: 2026-04-05T09:13:33.559Z
created_at: 2026-03-20T15:39:07Z
updated_at: 2026-03-28T17:45:27Z
---

> **Part of:** #159
> **Depends on: #163, #164**

## Context

HTML multiselect submits multiple values as repeated keys (`field=v1&field=v2`).
Starlette's `request.form()` returns a `FormData` object where `getlist(key)` is needed.
The current `PydanticForm.bind()` only calls `form_data.get(key)` — it must be extended
to handle list fields. Hybrid fields (list[str] stored as JSON/CSV) also need coercion.

## Acceptance Criteria

- [ ] `PydanticForm.bind(form_data)`:
  - For fields where widget is `MultiSelectWidget` or `RelationMultiSelectWidget`: calls `form_data.getlist(field.name)` instead of `.get()`
  - For hybrid fields with `storage="json"`: passes list through `HybridFieldCoercer.to_storage(value, "json")` before Pydantic validation
  - For hybrid fields with `storage="csv"`: same with `"csv"`
- [ ] Checkbox fix remains intact (unchecked checkbox → `False`)
- [ ] M2M field values (list of PKs as strings) coerced to correct PK type before passing to adapter's `save()`
- [ ] Unit tests for: list binding, JSON coercion round-trip, CSV coercion round-trip, M2M PK coercion

## Files Likely Affected

- `src/hyperadmin/views/forms.py`
- `src/hyperadmin/views/dynamic.py`
- `tests/unit/test_forms.py`

## Dependencies

Depends on: #163, #167

## Notes for Implementer

`FormData.getlist(key)` returns `[]` when no checkboxes selected — treat empty list as clearing the relation (not an error).
Pydantic validation of `list[int]` (M2M PKs) must happen before the adapter call — the adapter should receive typed Python values, not raw strings.
