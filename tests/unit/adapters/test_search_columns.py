"""Search-column detection skips native enum columns (PostgreSQL has no ILIKE for them)."""

import enum

from sqlalchemy import inspect
from sqlmodel import Field, SQLModel

from hyperadmin.adapters._search import detect_search_columns


class SearchKind(str, enum.Enum):
    ALPHA = "Alpha"
    BETA = "Beta"


class SearchColumnsLedger(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    name: str
    kind: SearchKind


def test_enum_columns_are_not_detected_as_search_columns() -> None:
    """
    Scenario: autocomplete on a model with an enum column
      Given a model with a string column and an enum column
      When  the default search columns are detected
      Then  only the string column is searched
    """
    columns = detect_search_columns(SearchColumnsLedger, inspect(SearchColumnsLedger))

    assert columns == ["name"]
