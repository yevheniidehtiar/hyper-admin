"""The search clause is a plain ``LIKE`` on SQLite and ``ILIKE`` elsewhere."""

from __future__ import annotations

import pytest
from sqlalchemy import String, create_engine, insert, select
from sqlalchemy.dialects import mysql, postgresql, sqlite
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from hyperadmin.adapters._search import contains_clause


class _Base(DeclarativeBase):
    pass


class Note(_Base):
    __tablename__ = "search_like_note"

    id: Mapped[int] = mapped_column(primary_key=True)
    title: Mapped[str] = mapped_column(String(50))


def _sql(dialect: object, text: str = "Ab") -> str:
    query = select(Note.id).where(contains_clause(Note.title, text))
    return str(query.compile(dialect=dialect))  # type: ignore[arg-type]


def test_sqlite_search_is_a_plain_like() -> None:
    """
    Scenario: SQLite search does not call lower() on every row
      Given a string column
      When  the search clause is compiled for SQLite
      Then  it is "title LIKE ?" with no lower() call and no "= 1" suffix
    """
    sql = _sql(sqlite.dialect())

    assert "search_like_note.title LIKE ?" in sql
    assert "lower(" not in sql
    assert "= 1" not in sql


@pytest.mark.parametrize(
    ("dialect", "expected"),
    [
        (postgresql.dialect(), "search_like_note.title ILIKE %(param_1)s"),
        (mysql.dialect(), "lower(search_like_note.title) LIKE lower(%s)"),
    ],
)
def test_other_databases_keep_ilike(dialect: object, expected: str) -> None:
    """
    Scenario: other databases keep SQLAlchemy's ILIKE
      Given a string column
      When  the search clause is compiled for PostgreSQL or MySQL
      Then  it is the same clause SQLAlchemy's ilike() renders
    """
    sql = _sql(dialect)

    assert expected in sql
    assert "= 1" not in sql


def test_sqlite_search_ignores_ascii_case() -> None:
    """
    Scenario: SQLite search still ignores case
      Given notes titled "Quarterly REPORT", "report draft" and "Invoice"
      When  the notes are searched for "rePort"
      Then  both report notes match and the invoice does not
    """
    engine = create_engine("sqlite://")
    _Base.metadata.create_all(engine)
    with engine.begin() as conn:
        conn.execute(
            insert(Note),
            [{"title": "Quarterly REPORT"}, {"title": "report draft"}, {"title": "Invoice"}],
        )
        rows = conn.execute(
            select(Note.title).where(contains_clause(Note.title, "rePort")).order_by(Note.id)
        ).scalars()

        assert list(rows) == ["Quarterly REPORT", "report draft"]
    engine.dispose()


def test_search_clauses_share_one_cache_key_shape() -> None:
    """
    Scenario: searches for different text reuse the compiled statement
      Given two searches on the same column for different text
      When  their cache keys are compared
      Then  the keys are equal, so SQLAlchemy compiles the statement once
    """
    first = select(Note.id).where(contains_clause(Note.title, "a"))
    second = select(Note.id).where(contains_clause(Note.title, "b"))

    assert first._generate_cache_key() == second._generate_cache_key()
