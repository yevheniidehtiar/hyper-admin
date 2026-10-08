"""Unit tests for ``hyperadmin.auth._types.UTCNaiveDateTime`` and auth timestamps.

The column type must give the same behaviour on both sides of the sqlmodel 0.0.45
cap: below it, sqlmodel maps ``datetime`` to a naive ``DateTime`` that returns naive
values; from 0.0.45 it maps to ``UTCDateTime`` (``timestamptz`` DDL, naive binds
rejected). The auth models pin ``sa_type=UTCNaiveDateTime()``, so these tests
exercise the decorator directly with both naive and aware driver values instead of
installing two sqlmodel versions.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
from sqlalchemy import Column, DateTime, MetaData, Table, create_engine, insert, select, text
from sqlalchemy.dialects import postgresql, sqlite
from sqlalchemy.schema import CreateTable
from sqlmodel import Session, SQLModel

from hyperadmin.auth._types import UTCNaiveDateTime
from hyperadmin.auth.models import Group, Permission, User
from hyperadmin.core.timezones import utc_now

UTC = timezone.utc
PLUS_TWO = timezone(timedelta(hours=2))


@pytest.fixture
def engine(tmp_path: Path):
    eng = create_engine(f"sqlite:///{tmp_path / 'auth_tz.db'}")
    SQLModel.metadata.create_all(eng)
    return eng


@pytest.fixture
def probe(engine):
    metadata = MetaData()
    table = Table("tz_probe", metadata, Column("value", UTCNaiveDateTime()))
    metadata.create_all(engine)
    return table


# ---------------------------------------------------------------------------
# Story scenarios (st-v058-byoa-16)
# ---------------------------------------------------------------------------


def test_created_at_is_aware_utc(engine) -> None:
    """
    Scenario: created_at is aware UTC
      Given a new User
      When  it is saved and reloaded
      Then  created_at is an aware UTC datetime
    """
    with Session(engine) as session:
        user = User(username="tz", email="tz@example.com", password_hash="x")
        session.add(user)
        session.commit()
        user_id = user.id

    with Session(engine) as session:
        reloaded = session.get(User, user_id)
        assert reloaded is not None
        assert reloaded.created_at.tzinfo is not None
        assert reloaded.created_at.utcoffset() == timedelta(0)


def test_naive_bind_is_stored_unchanged(engine, probe: Table) -> None:
    """
    Scenario: naive bind is stored unchanged
      Given a naive datetime bound to UTCNaiveDateTime
      When  it is saved and reloaded
      Then  the value is unchanged and tagged UTC
    """
    naive = datetime(2026, 7, 1, 10, 0, 0, 123456)

    with engine.begin() as conn:
        conn.execute(insert(probe).values(value=naive))
        raw = conn.execute(text("SELECT value FROM tz_probe")).scalar_one()
        loaded = conn.execute(select(probe.c.value)).scalar_one()

    assert raw == "2026-07-01 10:00:00.123456"
    assert loaded == naive.replace(tzinfo=UTC)
    assert loaded.tzinfo is UTC


def test_aware_bind_is_normalised(engine, probe: Table) -> None:
    """
    Scenario: aware bind is normalised
      Given an aware +02:00 datetime
      When  it is saved
      Then  the stored value is naive UTC
    """
    aware = datetime(2026, 7, 1, 10, 0, tzinfo=PLUS_TWO)

    with engine.begin() as conn:
        conn.execute(insert(probe).values(value=aware))
        raw = conn.execute(text("SELECT value FROM tz_probe")).scalar_one()

    assert raw == "2026-07-01 08:00:00.000000"


@pytest.mark.parametrize("model", [User, Group, Permission])
def test_ddl_is_unchanged(model: type[SQLModel]) -> None:
    """
    Scenario: DDL is unchanged
      Given the existing hyperadmin_users table
      When  create_all runs
      Then  no column type change is emitted
    """
    naive_pg = DateTime(timezone=False).compile(dialect=postgresql.dialect())
    ddl = str(CreateTable(model.__table__).compile(dialect=postgresql.dialect()))  # type: ignore[attr-defined]

    assert naive_pg == "TIMESTAMP WITHOUT TIME ZONE"
    assert f"created_at {naive_pg} NOT NULL" in ddl
    assert "WITH TIME ZONE" not in ddl


def test_user_updated_at_ddl_stays_naive() -> None:
    ddl = str(CreateTable(User.__table__).compile(dialect=postgresql.dialect()))  # type: ignore[attr-defined]

    assert "updated_at TIMESTAMP WITHOUT TIME ZONE" in ddl


def test_sqlite_ddl_matches_plain_datetime() -> None:
    plain = DateTime().compile(dialect=sqlite.dialect())

    assert UTCNaiveDateTime().compile(dialect=sqlite.dialect()) == plain


# ---------------------------------------------------------------------------
# Version-independent decorator semantics (both sides of the sqlmodel cap)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("model", [User, Group, Permission])
def test_auth_models_pin_the_column_type(model: type[SQLModel]) -> None:
    """``sa_type`` overrides sqlmodel's datetime mapping on every version."""
    column = model.__table__.c.created_at  # type: ignore[attr-defined]

    assert isinstance(column.type, UTCNaiveDateTime)
    assert model.model_fields["created_at"].default_factory is utc_now


def test_user_updated_at_pins_the_column_type() -> None:
    assert isinstance(User.__table__.c.updated_at.type, UTCNaiveDateTime)  # type: ignore[attr-defined]


def test_bind_accepts_naive_values_that_strict_utc_types_reject() -> None:
    """sqlmodel>=0.0.45 ``UTCDateTime`` raises on naive binds; this type assumes UTC."""
    decorator = UTCNaiveDateTime()
    naive = datetime(2026, 1, 1, 12, 0)

    assert decorator.process_bind_param(naive, sqlite.dialect()) == naive


def test_bind_normalises_aware_values() -> None:
    decorator = UTCNaiveDateTime()
    aware = datetime(2026, 1, 1, 12, 0, tzinfo=PLUS_TWO)

    result = decorator.process_bind_param(aware, sqlite.dialect())

    assert result == datetime(2026, 1, 1, 10, 0)
    assert result is not None
    assert result.tzinfo is None


def test_result_tags_naive_driver_values_as_utc() -> None:
    """Below the cap drivers return naive values from ``timestamp`` columns."""
    decorator = UTCNaiveDateTime()

    result = decorator.process_result_value(datetime(2026, 1, 1, 12, 0), sqlite.dialect())

    assert result == datetime(2026, 1, 1, 12, 0, tzinfo=UTC)


def test_result_normalises_aware_driver_values_to_utc() -> None:
    """A driver (or a ``timestamptz`` column) may already return aware values."""
    decorator = UTCNaiveDateTime()

    result = decorator.process_result_value(
        datetime(2026, 1, 1, 12, 0, tzinfo=PLUS_TWO), postgresql.dialect()
    )

    assert result == datetime(2026, 1, 1, 10, 0, tzinfo=UTC)
    assert result is not None
    assert result.utcoffset() == timedelta(0)


def test_none_passes_through() -> None:
    decorator = UTCNaiveDateTime()

    assert decorator.process_bind_param(None, sqlite.dialect()) is None
    assert decorator.process_result_value(None, sqlite.dialect()) is None


def test_type_is_marked_tz_aware_and_cacheable() -> None:
    decorator = UTCNaiveDateTime()

    assert decorator.hyperadmin_tz_aware is True
    assert decorator.cache_ok is True
    assert decorator.impl.timezone is False  # type: ignore[attr-defined]
    assert decorator.python_type is datetime
