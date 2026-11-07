"""Relationships named like dict methods validate through ``PydanticForm`` (st-ux-erp-01)."""

import pytest
from sqlmodel import Field, Relationship, SQLModel

from hyperadmin.views.forms import PydanticForm


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
