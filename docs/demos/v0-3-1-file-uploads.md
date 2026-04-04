# Demo: v0.3.1 — File Uploads

| Field | Value |
|-------|-------|
| Milestone | v0.3.1 — File Uploads |
| Completed | 2026-04-01 |
| Demo Date | 2026-04-04 |
| Issues Closed | 15 |
| Squad | Squad 1 — Core Platform |
| Key Commit | epic(uploads): MVP file uploads -- v0.3.1 (#401) (#417) |

---

## What Shipped

### StorageBackend Protocol & Admin Wiring (#388)

HyperAdmin now integrates with `fastapi-storages` to handle file and image uploads. Any
SQLModel column declared with `FileType` or `ImageType` from `fastapi-storages` is
automatically detected and handled through the upload pipeline.

**Example — wiring storage into a model:**

```python
from fastapi_storages import FileSystemStorage
from fastapi_storages.integrations.sqlalchemy import FileType, ImageType
from sqlalchemy import Column
from sqlmodel import Field, SQLModel

upload_storage = FileSystemStorage("uploads/")

class Product(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    name: str
    manual: str | None = Field(
        default=None,
        sa_column=Column(FileType(storage=upload_storage)),
    )
    photo: str | None = Field(
        default=None,
        sa_column=Column(ImageType(storage=upload_storage)),
    )
```

No further configuration is needed — HyperAdmin detects `FileType`/`ImageType` columns
automatically and routes them through the upload endpoints.

### Automatic Field Detection (#389)

The `classify_field()` utility now recognises `FileType` and `ImageType` SQLAlchemy column
types and returns a `FileFieldMeta` descriptor. This drives widget selection, form rendering,
and display in list/detail views — all without any `ModelAdmin` configuration changes.

### File Validation (#390)

Uploaded files are validated against configurable constraints before being written to storage:

```python
from hyperadmin.uploads.validation import validate_upload, FileValidationError

validate_upload(
    file,
    allowed_types=["image/jpeg", "image/png", "image/webp"],
    max_size=5 * 1024 * 1024,  # 5 MB
)
```

Validation raises `FileValidationError` with a descriptive message that surfaces in the
admin form error list.

### Upload Endpoints (#393, #394)

Two new endpoints are added automatically for each model with file fields:

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/admin/{model}/upload` | `POST` | Receive `multipart/form-data`, write to storage |
| `/admin/{model}/{pk}/delete-file` | `POST` | Remove a stored file and clear the DB column |

Forms with file fields are automatically submitted as `multipart/form-data` — no template
changes are required in downstream apps.

### FileInputWidget (#391)

A new `FileInputWidget` renders a `<input type="file">` with:

- Current file name and download link (when a file is already stored)
- Clear/delete checkbox
- Allowed types and size hints (when configured)

### List and Detail View Display (#396)

File fields are displayed in list and detail views as download links. Image fields show a
thumbnail preview in the detail view. No `list_display` or `readonly_fields` configuration
is needed.

### Safe File Cleanup on Delete (#395, #401)

When a model record is deleted, all associated stored files are removed from the storage
backend. The cleanup is ordered carefully: file paths are collected before the DB delete,
then removed afterwards to avoid `PIL.Image.open()` errors from `ImageType.process_result_value()`
on a deleted file.

### ERP / Simple Example Integration (#400)

The `examples/simple` app now demonstrates file uploads end-to-end:

```python
# examples/simple/models.py (excerpt)
upload_storage = FileSystemStorage("uploads/")

class Product(SQLModel, table=True):
    ...
    manual: str | None = Field(
        default=None,
        sa_column=Column(FileType(storage=upload_storage)),
    )
    photo: str | None = Field(
        default=None,
        sa_column=Column(ImageType(storage=upload_storage)),
    )
```

Running `examples/simple` shows the full upload workflow: create a Product with a PDF manual
and a product photo, view the download link in the list, and confirm the files are cleaned
up when the record is deleted.

### Tests (#397, #398)

| Test Suite | Coverage |
|------------|---------|
| Unit — field classification | `FileType`/`ImageType` → `FileFieldMeta` detection |
| Unit — validation | allowed types, max size, combined constraints |
| Unit — widget | `FileInputWidget` renders, handles existing file, handles delete flag |
| E2E — upload workflow | Create record with file, display in list/detail, download link |
| E2E — delete workflow | Delete record, verify file is removed from storage |

### Documentation (#399)

A new guide at `docs/uploads/file-uploads.md` covers:

- Storage backend setup (FileSystemStorage, S3-compatible)
- Model field configuration (`FileType`, `ImageType`)
- Validation configuration
- Template customization
- Handling existing files and deletion

---

## Issues Closed

| # | Title | Type |
|---|-------|------|
| #387 | review(spec): approve SDD for file upload system | spec |
| #388 | feat(uploads): define StorageBackend protocol and wire into Admin | feat |
| #389 | feat(uploads): detect FileType/ImageType columns for file field classification | feat |
| #390 | feat(uploads): add file validation by allowed types list and max size | feat |
| #391 | feat(views): create FileInputWidget with basic file input | feat |
| #392 | feat(views): handle multipart/form-data and UploadFile in CRUD forms | feat |
| #393 | feat(views): add dedicated file upload endpoint | feat |
| #394 | feat(views): add file deletion endpoint | feat |
| #395 | feat(adapters): clean up stored files when model record is deleted | feat |
| #396 | feat(views): display file fields in list and detail views | feat |
| #397 | test(uploads): unit tests for storage, fields, validation, and widgets | test |
| #398 | test(e2e): file upload create, edit, delete, and display workflows | test |
| #399 | docs(uploads): file upload usage guide and API reference | docs |
| #400 | feat(examples): add file upload fields to example apps | feat |
| #401 | epic(uploads): MVP File Uploads -- v0.3.1 | epic |

---

## Next Milestone

v0.4.0 — Responsive Design is next for Squad 1. 9 issues remain open (1/10 closed, 10%).
