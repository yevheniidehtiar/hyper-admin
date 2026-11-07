"""Relationships named like dict methods validate through ``PydanticForm`` (st-ux-erp-01)."""

import uuid

import pytest
from pydantic import BaseModel
from sqlmodel import Field, Relationship, SQLModel

from hyperadmin.core.inlines import InlineModelSpec
from hyperadmin.core.primary_key import DEFAULT_PK
from hyperadmin.views.forms import InlineFormset, PydanticForm


class RnParent(SQLModel, table=True):
    __tablename__ = "rn_parent"  # type: ignore[assignment]

    id: int | None = Field(default=None, primary_key=True)
    number: str
    items: list["RnItem"] = Relationship(back_populates="parent")
    keys: list["RnKey"] = Relationship(back_populates="parent")
    values: list["RnValue"] = Relationship(back_populates="parent")


class RnItem(SQLModel, table=True):
    __tablename__ = "rn_item"  # type: ignore[assignment]

    id: int | None = Field(default=None, primary_key=True)
    parent_id: int | None = Field(default=None, foreign_key="rn_parent.id")
    parent: "RnParent" = Relationship(back_populates="items")


class RnKey(SQLModel, table=True):
    __tablename__ = "rn_key"  # type: ignore[assignment]

    id: int | None = Field(default=None, primary_key=True)
    parent_id: int | None = Field(default=None, foreign_key="rn_parent.id")
    parent: "RnParent" = Relationship(back_populates="keys")


class RnValue(SQLModel, table=True):
    __tablename__ = "rn_value"  # type: ignore[assignment]

    id: int | None = Field(default=None, primary_key=True)
    parent_id: int | None = Field(default=None, foreign_key="rn_parent.id")
    parent: "RnParent" = Relationship(back_populates="values")


@pytest.mark.parametrize("name", ["items", "keys", "values"])
def test_validate_accepts_a_relationship_named_like_a_dict_method(name: str) -> None:
    """
    Scenario: invoice edit saves
      Given a table model with a relationship named like a dict method
      When  the form validates submitted data
      Then  validation succeeds and the relationship is not the dict method
    """
    form = PydanticForm(RnParent)

    instance, errors = form.validate({"number": "INV-1"})

    assert errors == {}
    assert instance is not None
    assert instance.number == "INV-1"
    assert not callable(getattr(instance, name))


class IntLine(BaseModel):
    parent_id: int
    sku: str


class UuidParentLine(BaseModel):
    parent_id: uuid.UUID
    sku: str


class StrParentLine(BaseModel):
    parent_id: str
    sku: str


class OpaqueParentLine(BaseModel):
    parent_id: dict[str, int]
    sku: str


@pytest.mark.parametrize("model", [IntLine, UuidParentLine, StrParentLine])
def test_inline_row_of_a_new_parent_validates_with_a_required_fk(model: type[BaseModel]) -> None:
    """
    Scenario: invoice create saves with one line item
      Given an inline model whose parent key is required and the parent is not saved yet
      When  its row is validated
      Then  the row is valid and the parent key is left for the save to fill
    """
    formset = InlineFormset(spec=InlineModelSpec(model=model, fk_field="parent_id"), pk=DEFAULT_PK)

    valid, errors = formset.validate_rows([{"sku": "a"}])

    assert errors == {}
    assert valid[0]["sku"] == "a"


def test_inline_row_reports_a_parent_key_it_cannot_stand_in_for() -> None:
    """
    Scenario: an unplaceholderable parent key is still reported
      Given an inline model whose parent key type accepts no stand-in value
      When  its row is validated for a new parent
      Then  the parent key error is reported
    """
    formset = InlineFormset(
        spec=InlineModelSpec(model=OpaqueParentLine, fk_field="parent_id"), pk=DEFAULT_PK
    )

    _, errors = formset.validate_rows([{"sku": "a"}])

    assert "parent_id" in errors[0]
