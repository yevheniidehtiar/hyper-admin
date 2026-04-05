---
type: story
id: i9L9ZIfpwpaN
title: "test(uploads): unit tests for storage, fields, validation, and widgets"
status: done
priority: medium
assignee: null
labels:
  - agent-task
  - area:tests
  - size:L
  - area:uploads
estimate: null
epic_ref: null
github:
  issue_number: 397
  repo: yevheniidehtiar/hyper-admin
  last_sync_hash: sha256:8d18e0f03297eb1eaee0ea44aa93a0184d5bc97a5742a588ce6c5914f7b9d695
  synced_at: 2026-04-05T09:13:33.559Z
created_at: 2026-03-31T21:14:19Z
updated_at: 2026-04-01T20:57:13Z
---

## Context

Comprehensive unit test suite for the entire `uploads/` module and its integration points with `core/` and `views/`. Targets >95% line coverage on new code.

**Depends on**: #388, #389, #390, #391, #392

## Scenarios

**Scenario: StorageBackend wrapper saves and returns file path**
  Given a `FileSystemStorage` configured with a temp directory
  When  a file is saved via `StorageBackend.save(upload_file)`
  Then  the returned path points to an existing file in the temp directory

**Scenario: HyperAdminSettings upload_dir creates directory on startup**
  Given `HYPERADMIN_UPLOAD_DIR` set to a non-existent path
  When  `Admin` is instantiated
  Then  the directory is auto-created

**Scenario: classify_field returns FileFieldMeta for FileType column**
  (see issue #389 — run as unit test)

**Scenario: validate_upload rejects oversized file**
  (see issue #390 — run as unit test)

**Scenario: FileInputWidget is selected by _pick_widget for FileFieldMeta**
  (see issue #391 — run as unit test)

**Scenario: has_file_fields returns True when FileInputWidget present**
  Given a PydanticForm for a model with a FileType column
  When  `form.has_file_fields` is accessed
  Then  it returns `True`

**Scenario: _extract_form_data replaces UploadFile with stored filename**
  Given a multipart form submission with a file
  When  `_extract_form_data()` is called
  Then  the UploadFile is replaced with the stored filename string in the returned dict

**Scenario: fastapi-storages not installed — no ImportError**
  Given `fastapi_storages` is not importable
  When  `from hyperadmin.core.fields import classify_field` is called
  Then  no `ImportError` is raised

## Acceptance Criteria

- [ ] `tests/unit/test_storage.py`: `StorageBackend`, `FileSystemStorage` wrapper, `Admin` wiring, upload dir auto-creation
- [ ] `tests/unit/test_file_fields.py`: `FileFieldMeta`, `classify_field` for `FileType`/`ImageType`, graceful degradation
- [ ] `tests/unit/test_file_validation.py`: all validation scenarios + edge cases (empty file, None filename, zero-size)
- [ ] `tests/unit/test_file_widget.py`: widget selection, template rendering, `has_file_fields`, `accept_attr`
- [ ] `tests/unit/test_multipart_forms.py`: `_extract_form_data` UploadFile handling, update preservation
- [ ] Coverage report shows >95% for all files in `src/hyperadmin/uploads/`
- [ ] Each test function has a BDD scenario docstring

## Files Likely Affected

- `tests/unit/test_storage.py` (new)
- `tests/unit/test_file_fields.py` (new)
- `tests/unit/test_file_validation.py` (new)
- `tests/unit/test_file_widget.py` (new)
- `tests/unit/test_multipart_forms.py` (new)
