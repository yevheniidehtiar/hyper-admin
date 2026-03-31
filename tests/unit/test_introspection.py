"""Unit tests for core/introspection.py — model introspection and smart defaults."""

from __future__ import annotations

from datetime import datetime
from enum import Enum

import pytest
from sqlmodel import Field, SQLModel

from hyperadmin.core.introspection import (
    FieldMeta,
    discover_sqlmodel_models,
    get_field_metadata,
    infer_list_display,
    infer_list_filter,
    infer_search_fields,
)

# ── Test models ────────────────────────────────────────────────────────


class StatusEnum(str, Enum):
    ACTIVE = "active"
    INACTIVE = "inactive"


class MixedFieldModel(SQLModel, table=True):
    __tablename__ = "test_mixed_field"

    id: int | None = Field(default=None, primary_key=True)
    name: str = Field(min_length=1)
    email: str | None = None
    is_active: bool = True
    status: StatusEnum = Field(default=StatusEnum.ACTIVE)
    category_id: int | None = Field(default=None, foreign_key="test_categories.id")
    created_at: datetime | None = Field(default_factory=datetime.now)


class MinimalModel(SQLModel, table=True):
    __tablename__ = "test_minimal"

    id: int | None = Field(default=None, primary_key=True)


class NumericOnlyModel(SQLModel, table=True):
    __tablename__ = "test_numeric_only"

    id: int | None = Field(default=None, primary_key=True)
    count: int = 0
    score: float = 0.0
    is_active: bool = True


class TextHeavyModel(SQLModel, table=True):
    __tablename__ = "test_text_heavy"

    id: int | None = Field(default=None, primary_key=True)
    title: str = ""
    bio: str = ""
    description: str = ""
    notes: str = ""


class AbstractModel(SQLModel):
    """Not a table model — no table=True."""

    name: str = ""


class CategoryModel(SQLModel, table=True):
    __tablename__ = "test_categories"

    id: int | None = Field(default=None, primary_key=True)
    name: str = Field(min_length=1)


# ── get_field_metadata ─────────────────────────────────────────────────


class TestGetFieldMetadata:
    def test_returns_correct_types_for_mixed_fields(self) -> None:
        meta = get_field_metadata(MixedFieldModel)

        assert isinstance(meta["id"], FieldMeta)
        assert meta["id"].is_pk is True
        assert meta["name"].python_type is str
        assert meta["is_active"].python_type is bool
        assert meta["status"].is_enum is True
        assert meta["category_id"].is_fk is True

    def test_fk_field_detected_with_target(self) -> None:
        meta = get_field_metadata(MixedFieldModel)
        fk = meta["category_id"]

        assert fk.is_fk is True
        assert fk.fk_target == "test_categories"

    def test_abstract_model_raises_error(self) -> None:
        with pytest.raises(ValueError, match="not a table model"):
            get_field_metadata(AbstractModel)

    def test_nullable_fields(self) -> None:
        meta = get_field_metadata(MixedFieldModel)
        assert meta["email"].is_nullable is True

    def test_all_fields_returned(self) -> None:
        meta = get_field_metadata(MixedFieldModel)
        expected = {"id", "name", "email", "is_active", "status", "category_id", "created_at"}
        assert set(meta.keys()) == expected


# ── infer_list_display ─────────────────────────────────────────────────


class TestInferListDisplay:
    def test_infers_key_fields_for_mixed_model(self) -> None:
        result = infer_list_display(MixedFieldModel)

        assert "id" in result
        assert "name" in result
        assert "email" in result
        assert len(result) <= 5

    def test_long_text_excluded(self) -> None:
        result = infer_list_display(TextHeavyModel)

        assert "bio" not in result
        assert "description" not in result
        assert "notes" not in result
        assert "title" in result

    def test_minimal_model_returns_id_and_str(self) -> None:
        result = infer_list_display(MinimalModel)
        assert result == ["id", "__str__"]

    def test_caps_at_five_fields(self) -> None:
        result = infer_list_display(MixedFieldModel)
        assert len(result) <= 5

    def test_id_is_first(self) -> None:
        result = infer_list_display(MixedFieldModel)
        assert result[0] == "id"


# ── infer_search_fields ───────────────────────────────────────────────


class TestInferSearchFields:
    def test_infers_string_fields(self) -> None:
        result = infer_search_fields(MixedFieldModel)

        assert "name" in result
        assert "email" in result
        assert "id" not in result
        assert "is_active" not in result
        assert "category_id" not in result

    def test_no_string_fields_returns_empty(self) -> None:
        result = infer_search_fields(NumericOnlyModel)
        assert result == []


# ── infer_list_filter ──────────────────────────────────────────────────


class TestInferListFilter:
    def test_infers_bool_and_enum_and_fk(self) -> None:
        result = infer_list_filter(MixedFieldModel)

        assert "is_active" in result
        assert "status" in result
        assert "category_id" in result
        assert "name" not in result

    def test_no_filterable_fields_returns_empty(self) -> None:
        result = infer_list_filter(MinimalModel)
        assert result == []

    def test_bool_only_model(self) -> None:
        result = infer_list_filter(NumericOnlyModel)
        assert "is_active" in result


# ── discover_sqlmodel_models ───────────────────────────────────────────


class TestDiscoverSqlmodelModels:
    def test_discovers_user_defined_models(self) -> None:
        models = discover_sqlmodel_models()
        model_names = {m.__name__ for m in models}

        assert "MixedFieldModel" in model_names
        assert "MinimalModel" in model_names
        assert "CategoryModel" in model_names

    def test_excludes_hyperadmin_internal_models(self) -> None:
        models = discover_sqlmodel_models()
        modules = {m.__module__ for m in models}

        for mod in modules:
            assert not mod.startswith("hyperadmin"), f"Internal model from {mod} should be excluded"

    def test_excludes_abstract_models(self) -> None:
        models = discover_sqlmodel_models()
        model_names = {m.__name__ for m in models}

        assert "AbstractModel" not in model_names
