---
type: story
id: 1kzcsrMHcqip
title: "feat(uploads): detect FileType/ImageType columns for file field classification"
status: done
priority: medium
assignee: null
labels:
  - enhancement
  - agent-task
  - area:core
  - size:M
  - area:uploads
estimate: null
epic_ref: null
github:
  issue_number: 389
  repo: yevheniidehtiar/hyper-admin
  last_sync_hash: sha256:dfe751731e7a46825b9e1950cbd5580b2006542ce4862dab2daac015fa316601
  synced_at: 2026-04-05T09:13:33.559Z
created_at: 2026-03-31T21:11:52Z
updated_at: 2026-04-01T20:56:56Z
---

## Context

`core/fields.py` `classify_field()` currently returns `SelectFieldMeta | None`. The upload feature needs it to detect `fastapi_storages` `FileType` / `ImageType` SQLAlchemy column types and return a new `FileFieldMeta` so the widget layer can pick the correct input widget.

**Spec**: `docs/specs/file-uploads.md`
**Depends on**: #387 (SDD approval), #388

## Scenarios

**Scenario: classify_field detects FileType column**
  Given a SQLModel with a column `document = Column(FileType(storage=storage))`
  When  `classify_field(field_info, model_cls)` is called for `document`
  Then  a `FileFieldMeta(field_type="file")` is returned

**Scenario: classify_field detects ImageType column**
  Given a SQLModel with a column `photo = Column(ImageType(storage=storage))`
  When  `classify_field(field_info, model_cls)` is called for `photo`
  Then  a `FileFieldMeta(field_type="image")` is returned

**Scenario: classify_field ignores non-file columns**
  Given a SQLModel with only `str`, `int`, `bool` columns
  When  `classify_field()` is called for each field
  Then  `None` or `SelectFieldMeta` is returned (never `FileFieldMeta`)

**Scenario: graceful degradation when fastapi-storages is not installed**
  Given `fastapi-storages` is not importable
  When  `classify_field()` is called
  Then  `ImportError` is not raised and non-file columns are classified normally

## Acceptance Criteria

- [ ] `src/hyperadmin/uploads/fields.py` defines `FileFieldMeta` dataclass: `field_type: Literal["file", "image"]`
- [ ] `classify_field()` return type updated to `SelectFieldMeta | FileFieldMeta | None`
- [ ] SA column inspection in `core/fields.py` (`_inspect_orm_field`) extended to detect `FileType` / `ImageType`
- [ ] Import of `fastapi_storages` in `core/fields.py` guarded with `try/except ImportError`
- [ ] Unit tests covering all four scenarios

## Files Likely Affected

- `src/hyperadmin/uploads/fields.py` (new)
- `src/hyperadmin/uploads/__init__.py` (add FileFieldMeta export)
- `src/hyperadmin/core/fields.py`
- `src/hyperadmin/core/choices.py` (update type annotations referencing classify_field return type)
- `tests/unit/test_file_fields.py` (new)

## Notes for Implementer

- Pattern to follow: `SelectFieldMeta` in `core/choices.py` — `FileFieldMeta` follows the same dataclass structure
- The SA column inspection lives in `_inspect_orm_field()` in `core/fields.py` — extend it there
- `fastapi_storages.integrations.sqlalchemy.FileType` and `ImageType` are the column types to detect
