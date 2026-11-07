"""Unit tests for ``hyperadmin.core.concurrency`` (OCC foundation, SDD realtime-occ)."""

from datetime import UTC, datetime
from typing import ClassVar

import pytest
from sqlmodel import Field, SQLModel

from hyperadmin.core.concurrency import (
    ConcurrencyConfigurationError,
    StaleRecordError,
    detect_version_field,
    next_version,
    resolve_version_field,
)


class _Versioned(SQLModel):
    id: int | None = Field(default=None, primary_key=True)
    version: int = 1


class _Stamped(SQLModel):
    id: int | None = Field(default=None, primary_key=True)
    updated_at: datetime | None = None


class _Both(SQLModel):
    id: int | None = Field(default=None, primary_key=True)
    version: int = 1
    updated_at: datetime | None = None


class _Custom(SQLModel):
    __version_field__: ClassVar[str] = "rev"
    id: int | None = Field(default=None, primary_key=True)
    rev: int = 1
    version: int = 1


class _Bare(SQLModel):
    id: int | None = Field(default=None, primary_key=True)
    name: str = ""


def test_detects_version_column() -> None:
    """
    Scenario: version field is auto-detected on a model with `version: int`
      Given a model with a version: int field
      When  the framework introspects the model
      Then  the detected version_field is "version"
    """
    assert detect_version_field(_Versioned) == "version"


def test_explicit_dunder_override_wins() -> None:
    """
    Scenario: a model-declared __version_field__ wins over convention
      Given a model declaring __version_field__ = "rev" and also a version field
      When  the framework introspects the model
      Then  the detected version_field is "rev"
    """
    assert detect_version_field(_Custom) == "rev"


def test_version_preferred_over_updated_at() -> None:
    """
    Scenario: version beats updated_at when both exist
      Given a model with version and updated_at
      When  updated_at fallback is allowed
      Then  the detected version_field is "version"
    """
    assert detect_version_field(_Both, use_updated_at=True) == "version"


def test_updated_at_fallback_requires_opt_in() -> None:
    """
    Scenario: updated_at fallback when version column is absent
      Given a model with updated_at but no version
      When  use_updated_at is True the field is "updated_at", otherwise None
    """
    assert detect_version_field(_Stamped, use_updated_at=True) == "updated_at"
    assert detect_version_field(_Stamped) is None


def test_detects_sqlalchemy_table_columns() -> None:
    """
    Scenario: plain SQLAlchemy models are introspected through their table
      Given a declarative model with a version column
      Then  the detected version_field is "version"
    """
    from sqlalchemy import Column, Integer
    from sqlalchemy.orm import declarative_base

    base = declarative_base()

    class Row(base):  # type: ignore[valid-type, misc]
        __tablename__ = "occ_row"
        id = Column(Integer, primary_key=True)
        version = Column(Integer)

    assert detect_version_field(Row) == "version"


def test_no_version_field_returns_none() -> None:
    assert detect_version_field(_Bare) is None


def test_resolve_returns_none_when_not_enforced() -> None:
    """
    Scenario: enforce_occ=False preserves legacy behaviour
      Given a model without a version field
      When  OCC is not enforced
      Then  no version field is resolved and nothing is raised
    """
    assert resolve_version_field(_Bare, enforce=False) is None
    assert resolve_version_field(_Versioned, enforce=False) is None


def test_resolve_returns_field_when_enforced() -> None:
    assert resolve_version_field(_Versioned, enforce=True) == "version"


def test_resolve_raises_when_enforced_without_version_field() -> None:
    """
    Scenario: no version field detected when neither is present
      Given a model with no version and no updated_at
      When  the framework resolves it with enforce_occ=True
      Then  a clear ConcurrencyConfigurationError is raised
    """
    with pytest.raises(ConcurrencyConfigurationError, match="_Bare"):
        resolve_version_field(_Bare, enforce=True)


def test_stale_record_error_carries_versions() -> None:
    """
    Scenario: update raises StaleRecordError when expected_version is stale
      Then  the error exposes current=3, expected=2
    """
    err = StaleRecordError(model=_Versioned, pk=42, expected=2, current=3)
    assert isinstance(err, Exception)
    assert (err.expected, err.current) == (2, 3)
    assert (err.expected_version, err.current_version) == (2, 3)
    assert err.pk == 42
    assert err.model is _Versioned
    assert "_Versioned" in str(err)


def test_next_version_increments_integers() -> None:
    assert next_version("version", 3) == 4


def test_next_version_refreshes_timestamps() -> None:
    before = datetime.now(UTC)
    bumped = next_version("updated_at", datetime(2020, 1, 1, tzinfo=UTC))
    assert isinstance(bumped, datetime)
    assert bumped >= before
    assert bumped.tzinfo is not None
