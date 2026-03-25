from enum import Enum
from typing import List, Optional, Union
from unittest.mock import MagicMock, patch

import pytest
from pydantic import BaseModel, Field
from sqlalchemy.exc import NoInspectionAvailable

from hyperadmin.core.fields import classify_field


class Status(Enum):
    ACTIVE = "active"
    INACTIVE = "inactive"


class MockModel(BaseModel):
    name: str
    status: Status
    tags: List[str]
    roles: List[Status]
    optional_status: Optional[Status]
    optional_tags: Optional[List[str]]
    other: int


def test_classify_enum():
    field_info = MockModel.model_fields["status"]
    meta = classify_field(field_info, MockModel)
    assert meta is not None
    assert meta.choices_source == "enum"
    assert meta.multiple is False
    assert meta.preload is True


def test_classify_optional_enum():
    field_info = MockModel.model_fields["optional_status"]
    meta = classify_field(field_info, MockModel)
    assert meta is not None
    assert meta.choices_source == "enum"
    assert meta.multiple is False
    assert meta.preload is True


def test_classify_list_enum():
    field_info = MockModel.model_fields["roles"]
    meta = classify_field(field_info, MockModel)
    assert meta is not None
    assert meta.choices_source == "enum"
    assert meta.multiple is True
    assert meta.preload is True


def test_classify_static_list():
    field_info = MockModel.model_fields["tags"]
    meta = classify_field(field_info, MockModel)
    assert meta is not None
    assert meta.choices_source == "static"
    assert meta.multiple is True
    assert meta.preload is True


def test_classify_optional_static_list():
    field_info = MockModel.model_fields["optional_tags"]
    meta = classify_field(field_info, MockModel)
    assert meta is not None
    assert meta.choices_source == "static"
    assert meta.multiple is True
    assert meta.preload is True


def test_classify_non_select():
    field_info = MockModel.model_fields["name"]
    meta = classify_field(field_info, MockModel)
    assert meta is None

    field_info = MockModel.model_fields["other"]
    meta = classify_field(field_info, MockModel)
    assert meta is None


@patch("hyperadmin.core.fields.sa_inspect")
def test_classify_sqlalchemy_fk(mock_inspect):
    mock_mapper = MagicMock()
    mock_inspect.return_value = mock_mapper

    # Mock columns
    mock_column = MagicMock()
    mock_column.key = "team_id"
    mock_column.foreign_keys = {MagicMock()}
    mock_mapper.columns = [mock_column]
    mock_mapper.relationships = []

    class SQLAlchemyModel(BaseModel):
        team_id: int

    field_info = SQLAlchemyModel.model_fields["team_id"]
    meta = classify_field(field_info, SQLAlchemyModel)

    assert meta is not None
    assert meta.choices_source == "relation"
    assert meta.multiple is False
    assert meta.preload is False


@patch("hyperadmin.core.fields.sa_inspect")
def test_classify_sqlalchemy_relationship(mock_inspect):
    mock_mapper = MagicMock()
    mock_inspect.return_value = mock_mapper

    # Mock relationship
    mock_rel = MagicMock()
    mock_rel.key = "team"
    mock_rel.uselist = False
    mock_mapper.relationships = [mock_rel]
    mock_mapper.columns = []

    class SQLAlchemyModel(BaseModel):
        team: Optional[dict] = None  # In practice this would be a model

    field_info = SQLAlchemyModel.model_fields["team"]
    meta = classify_field(field_info, SQLAlchemyModel)

    assert meta is not None
    assert meta.choices_source == "relation"
    assert meta.multiple is False
    assert meta.preload is False


@patch("hyperadmin.core.fields.sa_inspect")
def test_classify_sqlalchemy_m2m(mock_inspect):
    mock_mapper = MagicMock()
    mock_inspect.return_value = mock_mapper

    # Mock relationship
    mock_rel = MagicMock()
    mock_rel.key = "members"
    mock_rel.uselist = True
    mock_mapper.relationships = [mock_rel]
    mock_mapper.columns = []

    class SQLAlchemyModel(BaseModel):
        members: List[dict] = []

    field_info = SQLAlchemyModel.model_fields["members"]
    meta = classify_field(field_info, SQLAlchemyModel)

    assert meta is not None
    assert meta.choices_source == "relation"
    assert meta.multiple is True
    assert meta.preload is False


@patch("hyperadmin.core.fields.sa_inspect")
def test_classify_no_inspection(mock_inspect):
    mock_inspect.side_effect = NoInspectionAvailable("No inspection")

    class PurePydanticModel(BaseModel):
        name: str

    field_info = PurePydanticModel.model_fields["name"]
    meta = classify_field(field_info, PurePydanticModel)
    assert meta is None
