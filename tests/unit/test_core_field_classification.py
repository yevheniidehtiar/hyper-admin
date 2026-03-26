"""Unit tests for classify_field() — no real DB required."""

from __future__ import annotations

from enum import Enum
from unittest.mock import MagicMock, patch

import pytest
from pydantic import BaseModel

from hyperadmin.core.choices import SelectFieldMeta
from hyperadmin.core.fields import classify_field


class Color(Enum):
    RED = "red"
    BLUE = "blue"
    GREEN = "green"


class PureModel(BaseModel):
    color: Color
    colors: list[Color]
    tags: list[str]
    name: str
    opt_color: Color | None = None
    opt_name: str | None = None


def test_enum_field_returns_single_select() -> None:
    fi = PureModel.model_fields["color"]
    result = classify_field(fi, PureModel)
    assert isinstance(result, SelectFieldMeta)
    assert result.choices_source == "enum"
    assert result.multiple is False
    assert result.preload is True


def test_list_enum_field_returns_multi_select() -> None:
    fi = PureModel.model_fields["colors"]
    result = classify_field(fi, PureModel)
    assert isinstance(result, SelectFieldMeta)
    assert result.choices_source == "enum"
    assert result.multiple is True


def test_optional_enum_field_returns_single_select() -> None:
    fi = PureModel.model_fields["opt_color"]
    result = classify_field(fi, PureModel)
    assert isinstance(result, SelectFieldMeta)
    assert result.choices_source == "enum"
    assert result.multiple is False


def test_list_str_hybrid_returns_static_multi() -> None:
    fi = PureModel.model_fields["tags"]
    result = classify_field(fi, PureModel)
    assert isinstance(result, SelectFieldMeta)
    assert result.choices_source == "static"
    assert result.multiple is True
    assert result.preload is True


def test_plain_str_returns_none() -> None:
    fi = PureModel.model_fields["name"]
    result = classify_field(fi, PureModel)
    assert result is None


def test_optional_str_returns_none() -> None:
    fi = PureModel.model_fields["opt_name"]
    result = classify_field(fi, PureModel)
    assert result is None


def test_fk_field_via_relationship_returns_relation_single() -> None:
    mock_rel = MagicMock()
    mock_rel.key = "category_id"
    mock_rel.uselist = False

    mock_mapper = MagicMock()
    mock_mapper.relationships = [mock_rel]
    mock_mapper.columns = []

    class OrmLikeModel(BaseModel):
        category_id: int

    with (
        patch("hyperadmin.core.fields._HAS_SQLALCHEMY", True),
        patch("hyperadmin.core.fields.sa_inspect", return_value=mock_mapper, create=True),
    ):
        fi = OrmLikeModel.model_fields["category_id"]
        result = classify_field(fi, OrmLikeModel)

    assert isinstance(result, SelectFieldMeta)
    assert result.choices_source == "relation"
    assert result.multiple is False
    assert result.preload is False


def test_m2m_field_via_relationship_returns_relation_multi() -> None:
    mock_rel = MagicMock()
    mock_rel.key = "tags"
    mock_rel.uselist = True

    mock_mapper = MagicMock()
    mock_mapper.relationships = [mock_rel]
    mock_mapper.columns = []

    class OrmLikeModel(BaseModel):
        tags: list[int]

    with (
        patch("hyperadmin.core.fields._HAS_SQLALCHEMY", True),
        patch("hyperadmin.core.fields.sa_inspect", return_value=mock_mapper, create=True),
    ):
        fi = OrmLikeModel.model_fields["tags"]
        result = classify_field(fi, OrmLikeModel)

    assert isinstance(result, SelectFieldMeta)
    assert result.choices_source == "relation"
    assert result.multiple is True


def test_bare_fk_column_returns_relation_single() -> None:
    mock_col = MagicMock()
    mock_col.key = "country_id"
    mock_col.foreign_keys = {"fk"}

    mock_mapper = MagicMock()
    mock_mapper.relationships = []
    mock_mapper.columns = [mock_col]

    class OrmLikeModel(BaseModel):
        country_id: int

    with (
        patch("hyperadmin.core.fields._HAS_SQLALCHEMY", True),
        patch("hyperadmin.core.fields.sa_inspect", return_value=mock_mapper, create=True),
    ):
        fi = OrmLikeModel.model_fields["country_id"]
        result = classify_field(fi, OrmLikeModel)

    assert isinstance(result, SelectFieldMeta)
    assert result.choices_source == "relation"
    assert result.multiple is False


def test_no_inspection_available_falls_through() -> None:
    from sqlalchemy.exc import NoInspectionAvailable

    class PurePydanticModel(BaseModel):
        fk_id: int

    with (
        patch("hyperadmin.core.fields._HAS_SQLALCHEMY", True),
        patch("hyperadmin.core.fields.sa_inspect", side_effect=NoInspectionAvailable, create=True),
    ):
        fi = PurePydanticModel.model_fields["fk_id"]
        result = classify_field(fi, PurePydanticModel)

    assert result is None


@pytest.mark.parametrize("field_name", ["name", "opt_name"])
def test_non_select_fields_return_none(field_name: str) -> None:
    fi = PureModel.model_fields[field_name]
    assert classify_field(fi, PureModel) is None
