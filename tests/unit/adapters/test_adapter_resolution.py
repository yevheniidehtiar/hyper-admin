"""Adapter resolution for each SQLAlchemy declarative style (#715).

The shared ``adapter_registry`` must pick an adapter for models built on SQLAlchemy 2.0
``DeclarativeBase`` / ``DeclarativeBaseNoMeta``, on legacy ``declarative_base()``, and on
SQLModel, which must keep its own adapter.
"""

from unittest.mock import MagicMock

import pytest
from sqlalchemy import Integer, String
from sqlalchemy.orm import (
    DeclarativeBase,
    DeclarativeBaseNoMeta,
    Mapped,
    MappedAsDataclass,
    declarative_base,
    mapped_column,
)
from sqlmodel import Field, SQLModel

from hyperadmin.adapters import SQLAlchemyAdapter, SQLModelAdapter, adapter_registry
from hyperadmin.adapters.registry import AdapterNotFoundError, AdapterRegistry
from hyperadmin.core.adapters import BaseAdapter


class ModernBase(DeclarativeBase):
    pass


class ModernOrg(ModernBase):
    __tablename__ = "resolution_modern_org"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(50))


class NoMetaBase(DeclarativeBaseNoMeta):
    pass


class NoMetaOrg(NoMetaBase):
    __tablename__ = "resolution_nometa_org"
    id: Mapped[int] = mapped_column(primary_key=True)


class DataclassBase(MappedAsDataclass, DeclarativeBase):
    pass


class DataclassOrg(DataclassBase):
    __tablename__ = "resolution_dataclass_org"
    id: Mapped[int] = mapped_column(primary_key=True, init=False)


LegacyBase = declarative_base()


class LegacyOrg(LegacyBase):
    __tablename__ = "resolution_legacy_org"
    id = mapped_column(Integer, primary_key=True)


class SQLModelOrg(SQLModel, table=True):
    __tablename__ = "resolution_sqlmodel_org"
    id: int | None = Field(default=None, primary_key=True)


@pytest.mark.parametrize(
    "model",
    [ModernOrg, NoMetaOrg, DataclassOrg],
    ids=["DeclarativeBase", "DeclarativeBaseNoMeta", "MappedAsDataclass"],
)
def test_sqlalchemy_2_declarative_model_gets_sqlalchemy_adapter(model: type) -> None:
    """Scenario: SQLAlchemy 2.0 declarative models resolve to SQLAlchemyAdapter.

    Given a model subclassing a DeclarativeBase-style base
    When the shared adapter registry resolves it
    Then it gets SQLAlchemyAdapter
    """
    # Given / When
    adapter = adapter_registry.find_adapter_for_model(model)

    # Then
    assert adapter is SQLAlchemyAdapter


def test_legacy_declarative_base_model_gets_sqlalchemy_adapter() -> None:
    """Scenario: legacy declarative_base() models resolve through their metaclass.

    Given a model built on declarative_base(), whose MRO never contains DeclarativeMeta
    When the shared adapter registry resolves it
    Then it gets SQLAlchemyAdapter
    """
    # Given / When
    adapter = adapter_registry.find_adapter_for_model(LegacyOrg)

    # Then
    assert adapter is SQLAlchemyAdapter


def test_sqlmodel_model_keeps_sqlmodel_adapter() -> None:
    """Scenario: SQLModel wins over plain SQLAlchemy.

    Given a SQLModel table model, whose metaclass subclasses DeclarativeMeta
    When the shared adapter registry resolves it
    Then it gets SQLModelAdapter, not SQLAlchemyAdapter
    """
    # Given / When
    adapter = adapter_registry.find_adapter_for_model(SQLModelOrg)

    # Then
    assert adapter is SQLModelAdapter


def test_unmapped_class_still_raises() -> None:
    """Scenario: a class that is not an ORM model has no adapter.

    Given a plain Python class
    When the shared adapter registry resolves it
    Then AdapterNotFoundError is raised
    """

    # Given
    class NotAModel:
        pass

    # When / Then
    with pytest.raises(AdapterNotFoundError):
        adapter_registry.find_adapter_for_model(NotAModel)


def test_class_mro_wins_over_metaclass_mro() -> None:
    """Scenario: an adapter registered on a base class beats one on the metaclass.

    Given adapters registered for both a model's metaclass and one of its bases
    When the registry resolves the model
    Then the base-class adapter is returned
    """

    # Given
    class Meta(type):
        pass

    class Base(metaclass=Meta):
        pass

    class Model(Base):
        pass

    registry = AdapterRegistry()
    meta_adapter = MagicMock(spec=BaseAdapter)
    base_adapter = MagicMock(spec=BaseAdapter)
    registry.register(Meta, meta_adapter)
    registry.register(Base, base_adapter)

    # When
    found = registry.find_adapter_for_model(Model)

    # Then
    assert found is base_adapter
