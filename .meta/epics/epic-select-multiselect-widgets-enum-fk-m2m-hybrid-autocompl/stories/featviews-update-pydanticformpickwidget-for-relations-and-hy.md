---
type: story
id: scxYSRNkwFzX
title: "feat(views): update PydanticForm._pick_widget() for relations and hybrid fields"
status: done
priority: medium
assignee: null
labels:
  - enhancement
  - agent-task
  - size:XL
estimate: null
epic_ref:
  id: -TGq_yaQZtX_
github:
  issue_number: 167
  repo: yevheniidehtiar/hyper-admin
  last_sync_hash: sha256:a25e7b9db253a1c70dbbb5e97a59a47c26f2194074196f79a9f81f3519563027
  synced_at: 2026-04-07T17:23:23.790Z
created_at: 2026-03-20T15:38:45Z
updated_at: 2026-03-26T23:50:29Z
---

> **Part of:** #159
> **Depends on: #162, #163, #164**

## Context

`PydanticForm._pick_widget()` needs to call `classify_field()` from #162 to auto-select
`RelationSelectWidget`, `RelationMultiSelectWidget`, `SelectWidget`, or `MultiSelectWidget`
based on field type. This is the wiring step that makes auto-detection work end-to-end.

## Acceptance Criteria

- [ ] `_pick_widget()` calls `classify_field(field_info, model_cls)` first
- [ ] If `SelectFieldMeta` returned:
  - `choices_source="enum"` + `multiple=False` → `SelectWidget` (with choices from enum members)
  - `choices_source="enum"` + `multiple=True` → `MultiSelectWidget`
  - `choices_source="static"` + `multiple=True` → `MultiSelectWidget` (list[str] hybrid)
  - `choices_source="relation"` + `multiple=False` → `RelationSelectWidget`
  - `choices_source="relation"` + `multiple=True` → `RelationMultiSelectWidget`
- [ ] Falls through to existing heuristics when `classify_field()` returns `None`
- [ ] `preload` and `dependent_on` from `SelectFieldMeta` passed to widget constructor
- [ ] Existing tests remain green (backward compatible)
- [ ] New unit tests covering each auto-detected branch

## Files Likely Affected

- `src/hyperadmin/views/forms.py`
- `tests/unit/test_forms.py`

## Dependencies

Depends on: #162, #163, #164

## Notes for Implementer

`_pick_widget()` is a private method — feel free to refactor its internals without breaking the public API.
The `choices_url` for relation widgets is constructed from the model name and field name; the view layer must pass this context into `PydanticForm` (add a `choices_base_url: str = ""` parameter to `PydanticForm.__init__`).
