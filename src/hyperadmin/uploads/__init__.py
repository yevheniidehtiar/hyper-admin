"""File upload support for HyperAdmin."""

from __future__ import annotations

from hyperadmin.uploads.images import (
    DEFAULT_THUMBNAIL_SIZE,
    MAX_IMAGE_PIXELS,
    PLACEHOLDER_THUMBNAIL,
    THUMBNAIL_DIR,
    ImageMetadata,
    ImageTooLargeError,
    auto_rotate,
    extract_metadata,
    generate_thumbnail,
    prepare_image_upload,
    thumbnail_name,
)
from hyperadmin.uploads.storage import (
    S3StorageBackend,
    is_remote_storage,
    remote_file_name,
    remote_file_url,
)
from hyperadmin.uploads.validation import FileValidationError, validate_upload

__all__ = [
    "DEFAULT_THUMBNAIL_SIZE",
    "MAX_IMAGE_PIXELS",
    "PLACEHOLDER_THUMBNAIL",
    "THUMBNAIL_DIR",
    "FileValidationError",
    "ImageMetadata",
    "ImageTooLargeError",
    "S3StorageBackend",
    "auto_rotate",
    "extract_metadata",
    "generate_thumbnail",
    "is_remote_storage",
    "prepare_image_upload",
    "remote_file_name",
    "remote_file_url",
    "thumbnail_name",
    "validate_upload",
]
