"""Unit tests for ``hyperadmin.adapters.introspection.introspect_primary_key``."""

from __future__ import annotations

import uuid

from sqlalchemy import Column, Integer
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from sqlmodel import Field, SQLModel

from hyperadmin.adapters.introspection import introspect_primary_key
from hyperadmin.adapters.sqlalchemy import SQLAlchemyAdapter
from hyperadmin.adapters.sqlmodel import SQLModelAdapter

# Adapters need an engine or a session factory (SDD C.3); creating one opens no connection.
_ENGINE = create_async_engine("sqlite+aiosqlite://")

# ---------------------------------------------------------------------------
# Story scenarios (st-v058-byoa-15)
# ---------------------------------------------------------------------------


class IntAutoModel(SQLModel, table=True):
    __tablename__ = "pk_introspection_int_auto"

    id: int | None = Field(default=None, primary_key=True)


def test_int_autoincrement_id() -> None:
    """
    Scenario: int autoincrement id
      Given a model with an int autoincrement id
      When  introspect_primary_key runs
      Then  pk is attr 'id', type int, generated True
    """
    pk = introspect_primary_key(IntAutoModel)

    assert pk.attr == "id"
    assert pk.python_type is int
    assert pk.generated is True
    assert pk.composite is False


class UuidModel(SQLModel, table=True):
    __tablename__ = "pk_introspection_uuid"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)


def test_uuid_with_default_factory() -> None:
    """
    Scenario: UUID with default_factory
      Given a model with id: UUID = Field(default_factory=uuid4, primary_key=True)
      When  introspect_primary_key runs
      Then  kind is 'uuid' and generated is True
    """
    pk = introspect_primary_key(UuidModel)

    assert pk.kind == "uuid"
    assert pk.generated is True


class NaturalStringKeyModel(SQLModel, table=True):
    __tablename__ = "pk_introspection_natural_str"

    code: str = Field(primary_key=True)


def test_natural_string_key() -> None:
    """
    Scenario: natural string key
      Given a model with code: str primary key and no default
      When  introspect_primary_key runs
      Then  kind is 'str' and generated is False
    """
    pk = introspect_primary_key(NaturalStringKeyModel)

    assert pk.kind == "str"
    assert pk.generated is False


class RemappedColumnModel(SQLModel, table=True):
    __tablename__ = "pk_introspection_remapped"

    id_: int | None = Field(default=None, sa_column=Column("id", Integer, primary_key=True))


def test_remapped_column() -> None:
    """
    Scenario: remapped column
      Given a pk mapped via sa_column=Column('id') under attribute 'id_'
      When  introspect_primary_key runs
      Then  attr is 'id_'
    """
    pk = introspect_primary_key(RemappedColumnModel)

    assert pk.attr == "id_"


class _Base(DeclarativeBase):
    pass


class CompositeKeyModel(_Base):
    __tablename__ = "pk_introspection_composite"

    a: Mapped[int] = mapped_column(primary_key=True)
    b: Mapped[int] = mapped_column(primary_key=True)


def test_composite_key() -> None:
    """
    Scenario: composite key
      Given a two-column primary key
      When  introspect_primary_key runs
      Then  composite is True
    """
    pk = introspect_primary_key(CompositeKeyModel)

    assert pk.composite is True
    assert pk.attrs == ("a", "b")


# ---------------------------------------------------------------------------
# Python-type fallback: no pydantic annotation available (plain SQLAlchemy)
# ---------------------------------------------------------------------------


class PlainSqlAlchemyModel(_Base):
    __tablename__ = "pk_introspection_plain_sa"

    id: Mapped[int] = mapped_column(primary_key=True)


def test_python_type_falls_back_to_column_type_without_pydantic_annotation() -> None:
    """A model with no ``model_fields`` resolves its pk type from the column."""
    pk = introspect_primary_key(PlainSqlAlchemyModel)

    assert pk.python_type is int
    assert pk.generated is True  # autoincrement == "auto" on a single int column


# ---------------------------------------------------------------------------
# Adapter wiring: SQLModelAdapter.pk / SQLAlchemyAdapter.pk
# ---------------------------------------------------------------------------


def test_sqlmodel_adapter_sets_pk_from_introspection() -> None:
    adapter = SQLModelAdapter(UuidModel, engine=_ENGINE)

    assert adapter.pk.attr == "id"
    assert adapter.pk.kind == "uuid"


def test_sqlalchemy_adapter_sets_pk_from_introspection() -> None:
    adapter = SQLAlchemyAdapter(IntAutoModel, engine=_ENGINE)

    assert adapter.pk.attr == "id"
    assert adapter.pk.kind == "int"
    assert adapter.pk.generated is True
