---
type: story
id: 8P_Nvk3MBko0
title: "feat(core): relationship field introspection for widget auto-detection"
status: done
priority: medium
assignee: null
labels:
  - enhancement
  - in-progress
  - jules
  - agent-task
estimate: null
epic_ref:
  id: IYTFerusYXD-
github:
  issue_number: 162
  repo: yevheniidehtiar/hyper-admin
  last_sync_hash: sha256:1ca89149ab4a05df11e4efe75041227e4d8906b2f5a3188c18940f5a0d9b68ae
  synced_at: 2026-04-05T09:13:33.559Z
created_at: 2026-03-20T15:36:57Z
updated_at: 2026-03-28T19:44:34Z
---

> **Part of:** #159
> **Depends on: #160**

## Context

`PydanticForm._pick_widget()` currently uses simple annotation checks (is Enum? is bool? etc.).
To auto-select the correct select/multiselect widget, the form layer needs a richer field classification
that can distinguish FK, M2M, Enum, and `list[str]` hybrid fields from the Pydantic model's field info.

## Acceptance Criteria

- [ ] New function `classify_field(field_info: FieldInfo, model_cls: type) -> SelectFieldMeta | None` in `core/discovery.py` (or `core/fields.py`):
  - Returns `None` for non-select fields (widget picks fall through to existing logic)
  - Detects `Enum` annotation → `choices_source="enum"`, `multiple=False`
  - Detects `list[EnumType]` → `choices_source="enum"`, `multiple=True`
  - Detects SQLModel/SQLAlchemy FK (via mapper inspection) → `choices_source="relation"`, `multiple=False`
  - Detects M2M relation → `choices_source="relation"`, `multiple=True`
  - Detects `list[str]` without a relation → `choices_source="static"`, `multiple=True`
- [ ] `preload=True` default for Enum and small static lists; `preload=False` for relations (configurable via `ModelAdmin.preload_fields`)
- [ ] Exported from `core/__init__.py`
- [ ] Unit tests covering each detected type (no real DB needed — use mock mapper)

## Files Likely Affected

- `src/hyperadmin/core/discovery.py`
- `src/hyperadmin/core/__init__.py`
- `tests/unit/test_core_field_classification.py` (new)

## Dependencies

Depends on: #160

## Notes for Implementer

Keep SQLAlchemy mapper inspection isolated so it degrades gracefully when a pure Pydantic model (non-ORM) is used.
Wrap `inspect(model_cls)` in a try/except `NoInspectionAvailable`.
