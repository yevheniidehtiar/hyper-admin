"""Unit tests for FileInputWidget and _pick_widget() file-upload integration."""

from __future__ import annotations

from fastapi_storages import FileSystemStorage
from fastapi_storages.integrations.sqlalchemy import FileType, ImageType
from sqlalchemy import Column
from sqlmodel import Field, SQLModel

from hyperadmin.views.forms import FileInputWidget, PydanticForm

# ---------------------------------------------------------------------------
# Test model
# ---------------------------------------------------------------------------

_storage = FileSystemStorage("/tmp/test_uploads")  # noqa: S108


class WidgetFileModel(SQLModel, table=True):
    __tablename__ = "widget_file_model_test"
    id: int | None = Field(default=None, primary_key=True)
    document: str | None = Field(default=None, sa_column=Column(FileType(storage=_storage)))
    photo: str | None = Field(default=None, sa_column=Column(ImageType(storage=_storage)))
    name: str = ""


# ---------------------------------------------------------------------------
# FileInputWidget construction
# ---------------------------------------------------------------------------


def test_file_input_widget_default_template() -> None:
    widget = FileInputWidget()
    assert widget.template_path == "widgets/file_input.html"


def test_file_input_widget_default_not_image() -> None:
    widget = FileInputWidget()
    assert widget.is_image is False


def test_file_input_widget_is_image_flag() -> None:
    widget = FileInputWidget(is_image=True)
    assert widget.is_image is True


def test_file_input_widget_current_file() -> None:
    widget = FileInputWidget(current_file="photo.jpg")
    assert widget.current_file == "photo.jpg"


def test_file_input_widget_current_file_default_none() -> None:
    widget = FileInputWidget()
    assert widget.current_file is None


def test_file_input_widget_input_type() -> None:
    assert FileInputWidget.input_type == "file"


# ---------------------------------------------------------------------------
# _pick_widget integration via PydanticForm
# ---------------------------------------------------------------------------


def test_pick_widget_returns_file_input_for_filetype() -> None:
    form = PydanticForm(WidgetFileModel)
    field_map = {f.name: f for f in form.fields}
    widget = field_map["document"].widget
    assert isinstance(widget, FileInputWidget)
    assert widget.is_image is False


def test_pick_widget_returns_file_input_for_imagetype() -> None:
    form = PydanticForm(WidgetFileModel)
    field_map = {f.name: f for f in form.fields}
    widget = field_map["photo"].widget
    assert isinstance(widget, FileInputWidget)
    assert widget.is_image is True


def test_pick_widget_returns_text_input_for_plain_str() -> None:
    form = PydanticForm(WidgetFileModel)
    field_map = {f.name: f for f in form.fields}
    widget = field_map["name"].widget
    assert not isinstance(widget, FileInputWidget)
