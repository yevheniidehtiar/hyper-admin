---
type: story
id: aNSsEDD3bxKz
title: "feat(views): handle multipart/form-data and UploadFile in CRUD forms"
status: done
priority: medium
assignee: null
labels:
  - enhancement
  - agent-task
  - area:views
  - area:templates
  - size:L
estimate: null
epic_ref:
  id: P6jeUKkioZJh
github:
  issue_number: 392
  repo: yevheniidehtiar/hyper-admin
  last_sync_hash: sha256:ed284f183ebd2e5901621f524abddd55343122fc091a12d56753e10705d15ee6
  synced_at: 2026-04-07T17:23:23.791Z
created_at: 2026-03-31T21:12:57Z
updated_at: 2026-04-01T20:57:03Z
---

## Context

This is the integration glue that makes file uploads work end-to-end in create/edit forms. It covers: the form tag's `hx-encoding` attribute, extracting `UploadFile` objects from the multipart request, saving files to storage, and passing the stored filename to the adapter. Also handles the `hx-preserve` pattern so file inputs survive HTMX validation-error re-renders.

**Spec**: `docs/specs/file-uploads.md`
**Depends on**: #388, #389, #390, #391

## Scenarios

**Scenario: form tag includes hx-encoding when file fields are present**
  Given a model with a `FileType` column
  When  the create form page is rendered
  Then  the `<form>` tag has `hx-encoding="multipart/form-data"`

**Scenario: form tag omits hx-encoding when no file fields**
  Given a model with only `str`, `int`, `bool` fields
  When  the create form page is rendered
  Then  the `<form>` tag has no `hx-encoding` attribute

**Scenario: UploadFile is extracted and saved on create**
  Given a model with a `FileType` column `document`
  When  the create form is submitted with a file `report.pdf` attached
  Then  `report.pdf` is saved to the storage backend
  And   `adapter.create()` receives `data={"document": "<stored_filename>"}`

**Scenario: file is replaced on update**
  Given an existing record with `document="old.pdf"`
  When  the update form is submitted with a new file `new.pdf`
  Then  `new.pdf` is saved to storage
  And   `adapter.update(pk, data={"document": "<new_stored_filename>"})` is called

**Scenario: existing file preserved when no new file uploaded on update**
  Given an existing record with `document="existing.pdf"`
  When  the update form is submitted without attaching a new file
  Then  the `document` field retains `"existing.pdf"` in the data dict

**Scenario: file input survives validation error re-render**
  Given a form with a file field and a required text field
  When  the form is submitted with a file but the required text field is empty
  Then  the form is re-rendered with the validation error
  And   the file input element is preserved (not lost) via `hx-preserve`

## Acceptance Criteria

- [ ] `PydanticForm` gains `has_file_fields: bool` property (returns True if any field widget is `FileInputWidget`)
- [ ] `form_layout.html` adds `hx-encoding="multipart/form-data"` conditionally when `form.has_file_fields`
- [ ] File `<input>` element in `file_input.html` has `id="{{ field.name }}-input"` and `hx-preserve` attribute
- [ ] `DynamicModelView._extract_form_data()` handles `UploadFile` objects from multipart requests: extracts each, runs `validate_upload()`, saves to `self.storage`, replaces entry in data dict with stored filename
- [ ] On update, if `UploadFile.size == 0` or no file submitted, preserve the existing field value from the current record
- [ ] `create_view` and `update_view` in `dynamic.py` use the extended `_extract_form_data()`
- [ ] `FileValidationError` from validation is caught and surfaced as a form field error (HTTP 422 re-render)
- [ ] Integration tests covering all six scenarios

## Files Likely Affected

- `src/hyperadmin/views/forms.py` (`has_file_fields` property)
- `src/hyperadmin/views/dynamic.py` (`_extract_form_data`, `create_view`, `update_view`)
- `src/hyperadmin/templates/form_layout.html` (`hx-encoding` conditional)
- `src/hyperadmin/templates/widgets/file_input.html` (`hx-preserve`, stable `id`)
- `tests/unit/test_multipart_forms.py` (new)

## Notes for Implementer

- HTMX pattern: `hx-encoding="multipart/form-data"` on the form — NOT `enctype`. These are different. `enctype` only works with `hx-boost="true"`.
- `hx-preserve` requires a stable `id` on the element (not just `name`). Use `id="{{ field.name }}-input"`.
- File processing order: extract → validate → save → replace in dict. All before `adapter.create()` / `adapter.update()`.
- Detect "no new file": `UploadFile` with `size=0` or `filename=""` means the user did not select a file.
- Do not pass `UploadFile` objects to the adapter — adapters only accept plain `dict[str, Any]`.
