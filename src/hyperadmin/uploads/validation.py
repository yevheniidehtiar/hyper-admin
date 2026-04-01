"""Upload file validation utilities."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from starlette.datastructures import UploadFile


class FileValidationError(ValueError):
    """Raised when an uploaded file fails validation checks."""


def validate_upload(
    file: UploadFile,
    *,
    allowed_types: list[str] | None = None,
    max_size: int | None = None,
) -> None:
    """Validate an uploaded file against size and MIME type constraints.

    Args:
        file: The uploaded file to validate.
        allowed_types: Allowed MIME types (e.g. ``["image/jpeg", "image/png"]``).
            When ``None``, all types are accepted.
        max_size: Maximum file size in bytes. When ``None``, no limit.

    Raises:
        FileValidationError: If validation fails.
    """
    if max_size is not None and file.size is not None and file.size > max_size:
        raise FileValidationError(f"File size {file.size} bytes exceeds limit of {max_size} bytes")
    if allowed_types is not None and file.content_type not in allowed_types:
        raise FileValidationError(
            f"File type '{file.content_type}' is not allowed. Accepted: {', '.join(allowed_types)}"
        )
