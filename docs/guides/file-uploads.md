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

## S3-Compatible Storage

Uploads can live in an S3 bucket instead of a local directory: AWS S3,
Cloudflare R2, MinIO, Hetzner Object Storage, DigitalOcean Spaces or any
other S3-compatible service. Install the optional extra:

```bash
pip install 'hyper-admin[s3]'
```

`S3StorageBackend` is a `fastapi_storages.S3Storage` configured per instance
(bucket, endpoint, region, credentials) instead of from process-wide
environment variables read at import time:

```python
from fastapi_storages.integrations.sqlalchemy import FileType
from sqlalchemy import Column
from sqlmodel import Field, SQLModel

from hyperadmin import Admin
from hyperadmin.uploads import S3StorageBackend

storage = S3StorageBackend(
    bucket_name="admin-files",
    region="eu-central-1",
    # endpoint_url="https://minio.internal:9000",  # S3-compatible services only
)

class Product(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    manual: str | None = Field(default=None, sa_column=Column(FileType(storage=storage)))

admin = Admin(app, engine=engine, storage=storage)
```

Credentials are optional. When `access_key_id` / `secret_access_key` are not
given, boto3's own credential chain applies (`AWS_*` environment variables,
profiles, instance and task roles).

### Settings-driven configuration

Set `storage_backend="s3"` and `Admin()` builds the backend itself when no
`storage=` is passed. Each `aws_*` setting reads `HYPERADMIN_AWS_*` first and
then the plain `AWS_*` variable the AWS SDK and `fastapi-storages` use, so one
set of variables configures both:

```bash
export HYPERADMIN_STORAGE_BACKEND=s3
export AWS_S3_BUCKET_NAME=admin-files
export AWS_DEFAULT_REGION=eu-central-1
export AWS_ACCESS_KEY_ID=...
export AWS_SECRET_ACCESS_KEY=...
```

```python
admin = Admin(app, engine=engine)   # admin.storage is an S3StorageBackend
```

Models still need the storage on their columns, so build it once from the
same settings and share it:

```python
settings = HyperAdminSettings()
storage = S3StorageBackend.from_settings(settings)
# FileType(storage=storage) on the models, then:
admin = Admin(app, engine=engine, settings=settings, storage=storage)
```

| Setting | Env (prefixed / plain) | Default | Description |
|---------|------------------------|---------|-------------|
| `storage_backend` | `HYPERADMIN_STORAGE_BACKEND` | `"local"` | `"s3"` builds an `S3StorageBackend` when no `storage=` is passed |
| `aws_s3_bucket_name` | `HYPERADMIN_AWS_S3_BUCKET_NAME` / `AWS_S3_BUCKET_NAME` | `None` | Bucket (required for `"s3"`) |
| `aws_s3_region` | `HYPERADMIN_AWS_S3_REGION` / `AWS_S3_REGION` / `AWS_DEFAULT_REGION` | `None` | Region name |
| `aws_s3_endpoint_url` | `HYPERADMIN_AWS_S3_ENDPOINT_URL` / `AWS_S3_ENDPOINT_URL` | `None` | `http(s)://host[:port]` of an S3-compatible service; unset for AWS |
| `aws_access_key_id` | `HYPERADMIN_AWS_ACCESS_KEY_ID` / `AWS_ACCESS_KEY_ID` | `None` | Static credentials (optional) |
| `aws_secret_access_key` | `HYPERADMIN_AWS_SECRET_ACCESS_KEY` / `AWS_SECRET_ACCESS_KEY` | `None` | Stored as a `SecretStr` |
| `aws_s3_querystring_auth` | `HYPERADMIN_AWS_S3_QUERYSTRING_AUTH` / `AWS_QUERYSTRING_AUTH` | `True` | Sign object URLs (presigned, time-limited) |
| `aws_s3_custom_domain` | `HYPERADMIN_AWS_S3_CUSTOM_DOMAIN` / `AWS_S3_CUSTOM_DOMAIN` | `None` | Serve object URLs from a CDN or public-bucket domain (unsigned) |
| `aws_s3_default_acl` | `HYPERADMIN_AWS_S3_DEFAULT_ACL` / `AWS_DEFAULT_ACL` | `None` | ACL on written objects, e.g. `public-read`; unset sends no ACL |

### Providers

The bucket must exist. `endpoint_url` is the service's S3 API host; the
region is whatever the provider documents (`auto` for R2).

=== "AWS S3"

    ```bash
    export AWS_S3_BUCKET_NAME=admin-files
    export AWS_DEFAULT_REGION=eu-central-1
    # credentials via AWS_ACCESS_KEY_ID / AWS_SECRET_ACCESS_KEY, a profile or an IAM role
    ```

=== "Cloudflare R2"

    ```bash
    export AWS_S3_BUCKET_NAME=admin-files
    export AWS_S3_ENDPOINT_URL=https://<account-id>.r2.cloudflarestorage.com
    export AWS_S3_REGION=auto
    export AWS_ACCESS_KEY_ID=<r2 access key>
    export AWS_SECRET_ACCESS_KEY=<r2 secret>
    ```

    R2 has no ACLs: leave `aws_s3_default_acl` unset. For a public bucket, set
    `AWS_S3_CUSTOM_DOMAIN` to its public domain and `AWS_QUERYSTRING_AUTH=false`.

=== "MinIO"

    ```bash
    export AWS_S3_BUCKET_NAME=admin-files
    export AWS_S3_ENDPOINT_URL=http://localhost:9000   # http:// turns SSL off
    export AWS_ACCESS_KEY_ID=minioadmin
    export AWS_SECRET_ACCESS_KEY=minioadmin
    ```

=== "Hetzner Object Storage"

    ```bash
    export AWS_S3_BUCKET_NAME=admin-files
    export AWS_S3_ENDPOINT_URL=https://fsn1.your-objectstorage.com
    export AWS_S3_REGION=fsn1
    export AWS_ACCESS_KEY_ID=<access key>
    export AWS_SECRET_ACCESS_KEY=<secret key>
    ```

=== "DigitalOcean Spaces"

    ```bash
    export AWS_S3_BUCKET_NAME=admin-files
    export AWS_S3_ENDPOINT_URL=https://fra1.digitaloceanspaces.com
    export AWS_S3_REGION=fra1
    export AWS_ACCESS_KEY_ID=<spaces key>
    export AWS_SECRET_ACCESS_KEY=<spaces secret>
    ```

### How files are served from S3

The per-record route (`GET /admin/{model}/{item_id}/file/{field}`) runs the
same permission, queryset and object checks as for local storage, then
redirects (302, `Cache-Control: private, no-store`) to the object URL. With
`aws_s3_querystring_auth` on (the default) that URL is presigned and
time-limited, so a private bucket works out of the box and the link stays
behind the admin's authentication. Deleting a file, or a record with files,
deletes the objects from the bucket.

As with local storage, a stored name is only used when it is a plain object
key: names with empty, `.` or `..` segments (which could leave the bucket
prefix on a path-style URL) are refused, logged, and return 404.

`public_uploads_path` has no effect with S3: there is no local directory to
mount.

!!! note "`ImageType` columns"
    `fastapi-storages` reads an `ImageType` column by opening the image from a
    local path, so use `FileType` columns with S3.

### API

::: hyperadmin.uploads.storage.S3StorageBackend

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
