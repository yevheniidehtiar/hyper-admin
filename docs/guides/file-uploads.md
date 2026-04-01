# File Uploads

HyperAdmin supports file and image uploads via
[fastapi-storages](https://github.com/aminalaee/fastapi-storages). Models
with `FileType` or `ImageType` columns automatically render file input
widgets in create/update forms.

## Quick Start

```python
from fastapi import FastAPI
from fastapi_storages import FileSystemStorage
from fastapi_storages.integrations.sqlalchemy import FileType, ImageType
from sqlalchemy import Column
from sqlmodel import Field, SQLModel

from hyperadmin import Admin, HyperAdminSettings

# 1. Create a storage backend
storage = FileSystemStorage("uploads/")

# 2. Define a model with file columns
class Product(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    name: str
    manual: str | None = Field(
        default=None,
        sa_column=Column(FileType(storage=storage)),
    )
    photo: str | None = Field(
        default=None,
        sa_column=Column(ImageType(storage=storage)),
    )

# 3. Pass storage to Admin
app = FastAPI()
admin = Admin(app, engine=engine, settings=settings, storage=storage)
admin.mount("/admin")
```

That's it. HyperAdmin will:

- Detect `FileType` / `ImageType` columns automatically
- Render `<input type="file">` widgets in forms
- Handle multipart form submission
- Store files via the configured storage backend
- Display filenames in list views and download links in detail views
- Clean up stored files when records are deleted

## Configuration

### Storage

Pass any `fastapi-storages` backend to `Admin(storage=...)`:

```python
from fastapi_storages import FileSystemStorage

storage = FileSystemStorage("uploads/")
admin = Admin(app, storage=storage)
```

The upload directory is created automatically and served at `/uploads/`
via FastAPI's `StaticFiles`.

### Settings

| Setting | Default | Description |
|---------|---------|-------------|
| `upload_dir` | `"uploads"` | Default upload directory path |

Set via environment variable `HYPERADMIN_UPLOAD_DIR` or in settings:

```python
settings = HyperAdminSettings(upload_dir="media/files")
```

## File Validation

Use `validate_upload()` for custom validation in action handlers:

```python
from hyperadmin.uploads import validate_upload, FileValidationError

try:
    validate_upload(
        file,
        allowed_types=["image/jpeg", "image/png"],
        max_size=5 * 1024 * 1024,  # 5 MB
    )
except FileValidationError as e:
    # Handle validation error
    ...
```

## How It Works

1. **Field Detection**: `classify_field()` inspects SQLAlchemy column types.
   `FileType` columns return `FileFieldMeta(is_image=False)`, `ImageType`
   columns return `FileFieldMeta(is_image=True)`.

2. **Widget Selection**: `_pick_widget()` maps `FileFieldMeta` to
   `FileInputWidget`, which renders `widgets/file_input.html`.

3. **Form Submission**: Forms use `enctype="multipart/form-data"`.
   `UploadFile` objects are extracted before Pydantic validation and
   passed through to the SQLAlchemy adapter, where the column's
   `TypeDecorator.process_bind_param()` writes the file to storage.

4. **Deletion**: When a record is deleted, `_cleanup_item_files()` removes
   all associated files from storage before the database row is deleted.
