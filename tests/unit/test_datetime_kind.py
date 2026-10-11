"""Unit tests for ``hyperadmin.adapters.introspection.datetime_kind``."""

from __future__ import annotations

from datetime import datetime

import pytest
from pydantic import NaiveDatetime
from sqlalchemy import DateTime
from sqlmodel import Column, Field, SQLModel

from hyperadmin.adapters.introspection import datetime_kind
from hyperadmin.adapters.sqlalchemy import SQLAlchemyAdapter
from hyperadmin.adapters.sqlmodel import SQLModelAdapter
from hyperadmin.auth._types import UTCNaiveDateTime

try:
    from sqlmodel.sql.sqltypes import UTCDateTime
except ImportError:
    UTCDateTime = None

# ---------------------------------------------------------------------------
# Story scenarios (st-v058-byoa-15)
# ---------------------------------------------------------------------------


class NaiveDateTimeColumnModel(SQLModel, table=True):
    __tablename__ = "datetime_kind_naive_column"

    id: int | None = Field(default=None, primary_key=True)
    stamped_at: datetime = Field(sa_column=Column(DateTime(timezone=False)))


def test_naive_datetime_column() -> None:
    """
    Scenario: naive DateTime column
      Given a column DateTime(timezone=False)
      When  datetime_kind runs
      Then  'naive' is returned
    """
    assert datetime_kind(NaiveDateTimeColumnModel, "stamped_at") == "naive"


@pytest.mark.skipif(UTCDateTime is None, reason="sqlmodel < 0.0.45 has no UTCDateTime")
def test_utc_datetime_column() -> None:
    """
    Scenario: UTCDateTime column
      Given sqlmodel UTCDateTime is importable (skip otherwise)
      When  datetime_kind runs
      Then  'aware' is returned
    """

    class UtcDatetimeColumnModel(SQLModel, table=True):
        __tablename__ = "datetime_kind_utc_column"

        id: int | None = Field(default=None, primary_key=True)
        stamped_at: datetime = Field(sa_column=Column(UTCDateTime()))

    assert datetime_kind(UtcDatetimeColumnModel, "stamped_at") == "aware"


class AnnotationWinsModel(SQLModel, table=True):
    __tablename__ = "datetime_kind_annotation_wins"

    id: int | None = Field(default=None, primary_key=True)
    stamped_at: NaiveDatetime = Field(sa_column=Column(DateTime(timezone=True)))


def test_annotation_wins() -> None:
    """
    Scenario: annotation wins
      Given annotation NaiveDatetime on a DateTime(timezone=True) column
      When  datetime_kind runs
      Then  'naive' is returned
    """
    assert datetime_kind(AnnotationWinsModel, "stamped_at") == "naive"


# ---------------------------------------------------------------------------
# Additional rule coverage
# ---------------------------------------------------------------------------


class AwareDateTimeColumnModel(SQLModel, table=True):
    __tablename__ = "datetime_kind_aware_column"

    id: int | None = Field(default=None, primary_key=True)
    stamped_at: datetime = Field(sa_column=Column(DateTime(timezone=True)))


def test_aware_datetime_timezone_true_column() -> None:
    """``DateTime(timezone=True)`` with no annotation marker is aware."""
    assert datetime_kind(AwareDateTimeColumnModel, "stamped_at") == "aware"


class HyperadminTzAwareColumnModel(SQLModel, table=True):
    __tablename__ = "datetime_kind_hyperadmin_tz_aware"

    id: int | None = Field(default=None, primary_key=True)
    stamped_at: datetime = Field(sa_column=Column(UTCNaiveDateTime()))


def test_hyperadmin_tz_aware_type_decorator_wins_over_naive_impl() -> None:
    """A ``hyperadmin_tz_aware`` TypeDecorator is aware even with a naive ``impl``."""
    assert datetime_kind(HyperadminTzAwareColumnModel, "stamped_at") == "aware"
    # Sanity: the underlying impl is naive, so this proves rule 2 wins over rule 4.
    column = HyperadminTzAwareColumnModel.__table__.c.stamped_at  # type: ignore[attr-defined]
    assert column.type.impl.timezone is False


def test_non_datetime_column_returns_none() -> None:
    """A real, non-datetime column ('id') returns None, matching BaseAdapter's
    contract (see test_base_adapter_datetime_kind in test_primary_key.py) rather
    than falling through to 'naive'."""
    assert datetime_kind(NaiveDateTimeColumnModel, "id") is None


# ---------------------------------------------------------------------------
# Adapter wiring: SQLModelAdapter.datetime_kind / SQLAlchemyAdapter.datetime_kind
# ---------------------------------------------------------------------------


def test_sqlmodel_adapter_datetime_kind_uses_column_introspection() -> None:
    adapter = SQLModelAdapter(NaiveDateTimeColumnModel, engine=None)

    assert adapter.datetime_kind("stamped_at") == "naive"


def test_sqlmodel_adapter_datetime_kind_unknown_field_returns_none() -> None:
    adapter = SQLModelAdapter(NaiveDateTimeColumnModel, engine=None)

    assert adapter.datetime_kind("does_not_exist") is None


def test_sqlmodel_adapter_datetime_kind_non_datetime_column_returns_none() -> None:
    """Matches BaseAdapter's contract: a non-datetime column is None, not 'naive'."""
    adapter = SQLModelAdapter(NaiveDateTimeColumnModel, engine=None)

    assert adapter.datetime_kind("id") is None


def test_sqlalchemy_adapter_datetime_kind_uses_column_introspection() -> None:
    adapter = SQLAlchemyAdapter(AwareDateTimeColumnModel, engine=None)

    assert adapter.datetime_kind("stamped_at") == "aware"


def test_sqlalchemy_adapter_datetime_kind_non_datetime_column_returns_none() -> None:
    """Matches BaseAdapter's contract: a non-datetime column is None, not 'naive'."""
    adapter = SQLAlchemyAdapter(AwareDateTimeColumnModel, engine=None)

    assert adapter.datetime_kind("id") is None
