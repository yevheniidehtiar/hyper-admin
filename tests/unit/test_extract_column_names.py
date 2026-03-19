"""Tests for _extract_column_names in routing module."""

from sqlmodel import Field, SQLModel

from hyperadmin.routing import _extract_column_names


class DummyModel(SQLModel, table=True):
    __tablename__ = "dummy_extract"
    __table_args__ = {"extend_existing": True}

    id: int | None = Field(default=None, primary_key=True)
    name: str
    email: str

    @property
    def display_name(self) -> str:
        return self.name.upper()


def test_returns_none_for_none():
    assert _extract_column_names(None) is None


def test_returns_none_for_empty_list():
    assert _extract_column_names([]) is None


def test_extracts_key_from_column_attributes():
    result = _extract_column_names([DummyModel.id, DummyModel.name], model=DummyModel)
    assert result == ["id", "name"]


def test_extracts_property_name_via_mro():
    result = _extract_column_names([DummyModel.display_name], model=DummyModel)
    assert result == ["display_name"]


def test_mixed_columns_and_properties():
    result = _extract_column_names(
        [DummyModel.id, DummyModel.display_name, DummyModel.email], model=DummyModel
    )
    assert result == ["id", "display_name", "email"]


def test_string_passthrough():
    result = _extract_column_names(["id", "name"])
    assert result == ["id", "name"]


def test_property_without_model_falls_back_to_str():
    result = _extract_column_names([DummyModel.display_name])
    assert len(result) == 1
    # Without model, property can't be resolved — falls back to str()
    assert "property" in result[0].lower()
