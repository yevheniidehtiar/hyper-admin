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

The upload directory is created automatically. Every upload is stored
under a unique name (`<uuid4 hex>-<sanitised name>`), so uploading a file with
the same name as another record's file never overwrites it.

### Serving files

Files are not served by a public static mount. Each stored file is served
per record and field, under the admin prefix:

```
GET /admin/{model}/{item_id}/file/{field}
```

The route:

- requires the `view` permission on the model;
- loads the record under the admin's `get_queryset` filter, then runs the
  object-level `view` check;
- returns 404 unless `field` is a (non-sensitive) file field holding a file
  that exists inside the storage root;
- sends `X-Content-Type-Options: nosniff` and `Content-Security-Policy: sandbox`;
- sends `Content-Disposition: inline` only for PNG, JPEG, GIF and WebP, and
  `attachment` for everything else, SVG included.

The detail page links each file to this route.

!!! warning "Legacy public mount"
    Setting `public_uploads_path` (for example `"/uploads"`) mounts the storage
    directory publicly at that host path again, outside the admin's
    authentication. Anyone who knows a file name can then fetch it. HyperAdmin
    logs a warning at startup when it is set.

### Settings

| Setting | Default | Description |
|---------|---------|-------------|
| `upload_dir` | `"uploads"` | Default upload directory path |
| `public_uploads_path` | `None` | Legacy escape hatch: also serve the storage directory publicly at this host path |

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

## Images: EXIF Rotation, Metadata and Thumbnails

`hyperadmin.uploads.images` adds three pure helpers for `ImageType` fields. All of
them refuse decompression bombs before decoding a single pixel (the header size is
checked against `MAX_IMAGE_PIXELS`, Pillow's own default) and never raise on
non-image input.

```python
from hyperadmin.uploads import (
    ImageTooLargeError,
    auto_rotate,
    extract_metadata,
    generate_thumbnail,
    prepare_image_upload,
)

meta = extract_metadata(upload)  # ImageMetadata(width, height, format, orientation) or None
upright = auto_rotate(pil_image)  # transposed to its EXIF orientation, tag removed
thumb = generate_thumbnail(storage, "photo.jpg", max_size=(200, 200))
# -> ".thumbs/photo_200x200.jpg" (cached next to the original),
#    or PLACEHOLDER_THUMBNAIL when the file is missing, corrupt or too large
```

The admin's create and update forms call `prepare_image_upload()` on every
`ImageType` upload before the column saves it: a photo whose camera recorded an
EXIF orientation is re-encoded upright, so it displays correctly everywhere. An
image above the pixel limit raises `ImageTooLargeError` (a `FileValidationError`),
which the form answers with a `422` keyed by the field name.

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
