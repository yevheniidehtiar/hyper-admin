---
type: story
id: 0KnlAcgyIzOM
title: "feat(core): model introspection utility for field metadata"
status: done
priority: medium
assignee: null
labels:
  - enhancement
  - agent-task
  - area:core
  - size:M
estimate: null
epic_ref: null
github:
  issue_number: 363
  repo: yevheniidehtiar/hyper-admin
  last_sync_hash: sha256:d8a4c641c1f9b824581c6268400a968169c34812bb43ae3f42308704ff48a8a1
  synced_at: 2026-04-05T09:13:33.559Z
created_at: 2026-03-31T08:45:23Z
updated_at: 2026-03-31T20:43:33Z
---

## Context

New `core/introspection.py` module — pure utility that extracts field type, nullable, FK, M2M, choices, and length from SQLModel/SQLAlchemy column metadata. Foundation for all zero-config features.

Imports only from `sqlalchemy` (inspection only — no writes). Must NOT import from `views/`, `auth/`, or `adapters/`.

## Scenarios

**Scenario: get_field_metadata returns correct types for mixed fields**
  Given a model with `id` (int), `name` (str), `email` (str), `is_active` (bool), `status` (Enum), `category_id` (FK)
  When  `get_field_metadata(model)` is called
  Then  each field's FieldMeta has correct type, nullable, is_fk, is_enum flags

**Scenario: FK field detected via foreign_keys**
  Given a model with `category_id: int = Field(foreign_key="categories.id")`
  When  `get_field_metadata(model)` is called
  Then  `category_id` FieldMeta has `is_fk=True` and `fk_target="categories"`

**Scenario: abstract model (no table=True) raises error**
  Given a SQLModel class without `table=True`
  When  `get_field_metadata(model)` is called
  Then  ValueError is raised

## Acceptance criteria

- [ ] New file: `src/hyperadmin/core/introspection.py`
- [ ] `FieldMeta` dataclass with: name, python_type, is_pk, is_fk, is_enum, is_nullable, max_length, fk_target
- [ ] `get_field_metadata(model) -> dict[str, FieldMeta]`
- [ ] `infer_list_display(model) -> list[str]` — 3-5 fields, priority: id > name/title > email > created_at > status
- [ ] `infer_search_fields(model) -> list[str]` — str/email fields only
- [ ] `infer_list_filter(model) -> list[str]` — bool, enum, FK fields
- [ ] Unit tests in `tests/unit/test_introspection.py`
- [ ] No imports from `views/`, `auth/`, `adapters/`
- [ ] Exported via `core/__init__.py`

## Files likely affected

- `src/hyperadmin/core/introspection.py` (new)
- `src/hyperadmin/core/__init__.py` (export new functions)
- `tests/unit/test_introspection.py` (new)

## Dependencies

None — this is the foundation task for Epic B.

## Notes for implementer

Use `sqlalchemy.inspect(model)` for column metadata. Priority for `infer_list_display`: id first, then name/title fields, then email, then timestamps, then status/enum. Exclude long text fields (Text type). Cap at 5 fields. If model has only `id`, return `["id", "__str__"]`.
