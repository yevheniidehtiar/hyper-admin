"""Unit tests for validate_upload() — size and MIME type checks."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from hyperadmin.uploads.validation import FileValidationError, validate_upload

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_upload(
    filename: str = "test.txt",
    content_type: str = "text/plain",
    size: int | None = 100,
) -> MagicMock:
    upload = MagicMock()
    upload.filename = filename
    upload.content_type = content_type
    upload.size = size
    return upload


# ---------------------------------------------------------------------------
# Size validation
# ---------------------------------------------------------------------------


def test_file_within_max_size_passes() -> None:
    upload = _make_upload(size=500)
    validate_upload(upload, max_size=1024)


def test_file_exceeding_max_size_raises() -> None:
    upload = _make_upload(size=2048)
    with pytest.raises(FileValidationError, match="exceeds limit"):
        validate_upload(upload, max_size=1024)


def test_file_exactly_at_max_size_passes() -> None:
    upload = _make_upload(size=1024)
    validate_upload(upload, max_size=1024)


def test_file_with_none_size_and_max_size_set_does_not_raise() -> None:
    """When the upload has size=None, the size check is skipped."""
    upload = _make_upload(size=None)
    validate_upload(upload, max_size=512)


# ---------------------------------------------------------------------------
# Content-type validation
# ---------------------------------------------------------------------------


def test_file_with_allowed_content_type_passes() -> None:
    upload = _make_upload(content_type="image/png")
    validate_upload(upload, allowed_types=["image/png", "image/jpeg"])


def test_file_with_disallowed_content_type_raises() -> None:
    upload = _make_upload(content_type="application/pdf")
    with pytest.raises(FileValidationError, match="not allowed"):
        validate_upload(upload, allowed_types=["image/png", "image/jpeg"])


# ---------------------------------------------------------------------------
# No limits
# ---------------------------------------------------------------------------


def test_no_limits_passes_any_file() -> None:
    upload = _make_upload(size=999_999, content_type="video/mp4")
    validate_upload(upload, max_size=None, allowed_types=None)


def test_no_limits_is_default() -> None:
    upload = _make_upload(size=999_999, content_type="video/mp4")
    validate_upload(upload)


# ---------------------------------------------------------------------------
# Combined constraints
# ---------------------------------------------------------------------------


def test_valid_size_but_bad_type_raises() -> None:
    upload = _make_upload(size=100, content_type="text/html")
    with pytest.raises(FileValidationError, match="not allowed"):
        validate_upload(upload, max_size=1024, allowed_types=["text/plain"])


def test_valid_type_but_bad_size_raises() -> None:
    upload = _make_upload(size=2048, content_type="text/plain")
    with pytest.raises(FileValidationError, match="exceeds limit"):
        validate_upload(upload, max_size=1024, allowed_types=["text/plain"])
