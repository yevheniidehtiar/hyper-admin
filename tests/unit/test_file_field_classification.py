"""Unit tests for classify_field() — FileType / ImageType detection."""

from __future__ import annotations

from unittest.mock import patch

# ---------------------------------------------------------------------------
# Test model with FileType / ImageType columns (requires fastapi-storages)
# ---------------------------------------------------------------------------
from fastapi_storages import FileSystemStorage
from fastapi_storages.integrations.sqlalchemy import FileType, ImageType
from pydantic import BaseModel
from sqlalchemy import Column
from sqlmodel import Field, SQLModel

from hyperadmin.core.fields import classify_field
from hyperadmin.core.uploads import FileFieldMeta

_storage = FileSystemStorage("/tmp/test_uploads")  # noqa: S108


class FileModel(SQLModel, table=True):
    __tablename__ = "file_model_classify_test"
    id: int | None = Field(default=None, primary_key=True)
    document: str | None = Field(default=None, sa_column=Column(FileType(storage=_storage)))
    photo: str | None = Field(default=None, sa_column=Column(ImageType(storage=_storage)))
    name: str = ""


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_filetype_column_returns_file_field_meta() -> None:
    fi = FileModel.model_fields["document"]
    result = classify_field(fi, FileModel)
    assert isinstance(result, FileFieldMeta)
    assert result.is_image is False


def test_imagetype_column_returns_image_field_meta() -> None:
    fi = FileModel.model_fields["photo"]
    result = classify_field(fi, FileModel)
    assert isinstance(result, FileFieldMeta)
    assert result.is_image is True


def test_regular_str_column_returns_none() -> None:
    fi = FileModel.model_fields["name"]
    result = classify_field(fi, FileModel)
    assert result is None


def test_graceful_degradation_without_fastapi_storages() -> None:
    """When _HAS_FILE_TYPES is False, file columns are not detected."""
    fi = FileModel.model_fields["document"]
    with patch("hyperadmin.core.fields._HAS_FILE_TYPES", False):
        result = classify_field(fi, FileModel)
    # Without file-type detection the field falls through to None
    # (no enum, no relation, no list[str] — just Optional[str]).
    assert not isinstance(result, FileFieldMeta)


def test_plain_pydantic_model_str_field_returns_none() -> None:
    """A plain Pydantic model (no ORM) with a str field returns None."""

    class PlainModel(BaseModel):
        title: str

    fi = PlainModel.model_fields["title"]
    result = classify_field(fi, PlainModel)
    assert result is None
