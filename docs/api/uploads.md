# Uploads

File and image fields store their files through a `fastapi-storages` backend passed as
`Admin(storage=...)`; see [File Uploads](../guides/file-uploads.md) for the column types and the
per-record download route. `S3StorageBackend` needs the `s3` extra
(`pip install 'hyper-admin[s3]'`); the image helpers need Pillow.

| Name | What it does |
|---|---|
| `S3StorageBackend` | An S3-compatible storage backend configured per instance or from `HYPERADMIN_AWS_*` settings |
| `validate_upload` | Checks an `UploadFile` against allowed MIME types and a size limit; raises `FileValidationError` |
| `prepare_image_upload` | Rewrites an uploaded image upright when its EXIF orientation asks for it and returns its metadata; raises `ImageTooLargeError` above `max_pixels` |
| `extract_metadata` | Width, height, format and EXIF orientation of an image without decoding its pixels, or `None` for a non-image |
| `auto_rotate` | Applies the EXIF orientation to a Pillow image |
| `generate_thumbnail` | Makes a thumbnail of a stored image once and returns its name, or a placeholder icon when the file cannot be read |

## API Reference

::: hyperadmin.uploads.S3StorageBackend

::: hyperadmin.uploads.validate_upload

::: hyperadmin.uploads.FileValidationError

::: hyperadmin.uploads.prepare_image_upload

::: hyperadmin.uploads.ImageTooLargeError

::: hyperadmin.uploads.extract_metadata

::: hyperadmin.uploads.auto_rotate

::: hyperadmin.uploads.generate_thumbnail
