# SDD: MVP File Uploads

| Field | Value |
|---|---|
| Author | Claude Code |
| Status | Approved |
| Issue | #401 |
| Milestone | v0.3.1 — File Uploads |
| Created | 2026-04-01 |
| Last updated | 2026-04-01 |

---

## Problem

HyperAdmin has no file upload support. Models using `FileType`/`ImageType` columns from
`fastapi-storages` render as plain text inputs and cannot accept file data. Users cannot
create or edit records that contain file or image fields through the admin UI.

## Goals

- Local filesystem storage via `fastapi-storages.FileSystemStorage`
- Auto-detection of `FileType`/`ImageType` SA columns in `classify_field()`
- `FileInputWidget` with `<input type="file">` for create/update forms
- Multipart form handling (`enctype="multipart/form-data"`) with UploadFile passthrough
- Dedicated upload and file-deletion endpoints
- File cleanup on record deletion
- File/image display in list and detail views

## Non-Goals

- S3/cloud storage backends (future milestone)
- Thumbnail generation and image processing
- Drag-and-drop upload UX
- Upload progress indication
- Image cropping or resizing
- Chunked/resumable uploads
- Multi-file upload fields

## BDD Scenarios

```
Scenario: Admin with storage parameter auto-creates upload directory
  Given a FastAPI app and FileSystemStorage("uploads/")
  When  Admin(app, storage=storage) is instantiated
  Then  the "uploads/" directory exists and is served via StaticFiles

Scenario: classify_field detects FileType column
  Given a SQLModel with a FileType column "document"
  When  classify_field() is called for that field
  Then  it returns FileFieldMeta(is_image=False)

Scenario: classify_field detects ImageType column
  Given a SQLModel with an ImageType column "photo"
  When  classify_field() is called for that field
  Then  it returns FileFieldMeta(is_image=True)

Scenario: file exceeding max_size is rejected
  Given max_size=1048576 (1 MB)
  When  a 2 MB file is validated
  Then  FileValidationError is raised

Scenario: file with disallowed MIME type is rejected
  Given allowed_types=["image/jpeg", "image/png"]
  When  a "text/plain" file is validated
  Then  FileValidationError is raised

Scenario: FileInputWidget renders for FileType field
  Given a model with a FileType column
  When  the create form is rendered
  Then  the field displays an <input type="file"> widget

Scenario: create form uses multipart encoding
  Given a model with at least one FileType column
  When  the create form HTML is rendered
  Then  the <form> tag includes enctype="multipart/form-data"

Scenario: file upload via create form
  Given a model with a FileType column and storage configured
  When  the user submits the create form with a file attached
  Then  the file is written to storage and the record is created

Scenario: file replacement via update form
  Given a record with an existing file in a FileType column
  When  the user submits the update form with a new file
  Then  the old file value is replaced with the new filename

Scenario: dedicated upload endpoint saves file
  Given storage is configured
  When  POST /{model}/upload/{field} with a multipart file
  Then  the file is saved and metadata JSON is returned

Scenario: file deletion endpoint removes file
  Given a record with an uploaded file
  When  DELETE /{model}/{id}/file/{field}
  Then  the file is deleted from storage and the field is set to None

Scenario: record deletion cleans up files
  Given a record with uploaded files in FileType/ImageType columns
  When  the record is deleted via the admin UI
  Then  all associated files are removed from storage

Scenario: detail view shows download link for file fields
  Given a record with an uploaded file
  When  the detail view is rendered
  Then  the file field displays as a download link

Scenario: list view shows filename for file fields
  Given records with uploaded files
  When  the list view is rendered
  Then  file fields show the filename text (not the StorageFile repr)
```

## Design

### Architecture

```
core/uploads.py (FileFieldMeta)
     ^
     |
core/fields.py (classify_field → FileFieldMeta)
     ^
     |
views/forms.py (FileInputWidget, _pick_widget)
     ^
     |
views/dynamic.py (multipart handling, upload/delete endpoints, cleanup)

uploads/ (validation.py — standalone business logic)
```

Dependency direction: `views/ → core/` (compliant with CONSTITUTION.md).
No code in `core/` imports from `views/` or `uploads/`.

The `fastapi-storages` `FileSystemStorage` is used directly. No wrapper protocol
is needed because SA's `FileType`/`ImageType` TypeDecorators handle file I/O
in `process_bind_param()` — we pass `UploadFile` objects through to the adapter.

### Data Model Changes

No new ORM models. `FileType` and `ImageType` from `fastapi-storages` store
filenames as `String` columns. No schema migration required.

### API / Protocol Changes

- `classify_field()` return type: `SelectFieldMeta | None` → `SelectFieldMeta | FileFieldMeta | None`
- New `FileFieldMeta` dataclass in `core/uploads.py`
- New `FileInputWidget` in `views/forms.py`
- New `validate_upload()` in `uploads/validation.py`
- New endpoint: `POST /{model}/upload/{field_name}` — async file upload
- New endpoint: `DELETE /{model}/{item_id}/file/{field_name}` — file deletion
- Modified: `create_view()`, `update_view()`, `delete_action()` — file handling

### Configuration Changes

- `Admin(storage=...)` — optional `FileSystemStorage` instance
- `HyperAdminSettings.upload_dir` — default upload directory path (default: `"uploads"`)
- Storage is threaded: `Admin → HyperAdminRouter → create_admin_router → DynamicModelView`

## Edge Cases & Error Handling

| Case | Handling |
|---|---|
| No storage configured, model has FileType columns | Fields fall through to TextInput (no crash) |
| Empty file upload (0 bytes) | SA TypeDecorator returns None (no file stored) |
| File exceeds max_size | `FileValidationError` → form re-rendered with error |
| Disallowed MIME type | `FileValidationError` → form re-rendered with error |
| File missing on disk during delete | `os.path.exists()` check, log warning, continue |
| StorageFile/StorageImage in list view | Extract `.name` attribute for display |
| No file selected on update form | Skip field — don't overwrite existing value |

## Migration & Backward Compatibility

Backward compatible — no migration required. The `storage` parameter on `Admin()` is
optional and defaults to `None`. Existing apps without file fields are unaffected.
Adding `enctype="multipart/form-data"` to all forms is safe (non-file fields work
identically with multipart encoding).

## Open Questions

None — all resolved.

## Decision Log

| Decision | Rationale | Alternatives considered |
|---|---|---|
| No StorageBackend protocol wrapper | `fastapi-storages` SA TypeDecorators handle file I/O directly in `process_bind_param()` | Custom protocol wrapping FileSystemStorage — rejected as unnecessary indirection |
| `enctype="multipart/form-data"` on all forms | Simpler than conditional; non-file forms work fine with multipart | Conditional enctype via template variable — rejected as over-engineering |
| File deletion via `os.remove()` | `FileSystemStorage` has no `delete()` method | Adding delete to storage — rejected, would require forking fastapi-storages |
| UploadFile passthrough to adapter | SA TypeDecorator handles write; no view-layer file I/O needed | Pre-process files in view, pass filename to adapter — rejected, duplicates SA logic |
