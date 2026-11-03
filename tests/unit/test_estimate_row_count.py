"""estimate_row_count (SDD filter-choice-scalability): the contract, SQLite and PostgreSQL paths."""

from __future__ import annotations

from collections.abc import AsyncIterator
from types import SimpleNamespace
from typing import Any

import pytest
from sqlalchemy import Column, Integer, MetaData, Table
from sqlalchemy.dialects import postgresql, sqlite
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine
from sqlalchemy.pool import StaticPool
from sqlmodel import Field, SQLModel

from hyperadmin.adapters._estimate import estimate_table_rows
from hyperadmin.adapters.sqlalchemy import SQLAlchemyAdapter
from hyperadmin.adapters.sqlmodel import SQLModelAdapter
from hyperadmin.core.adapters import BaseAdapter

pytestmark = pytest.mark.anyio


class Country(SQLModel, table=True):
    __tablename__ = "estimate_country"

    id: int | None = Field(default=None, primary_key=True)
    name: str


class LegacyAdapter(BaseAdapter):
    """An adapter written before estimate_row_count existed: it does not override it."""

    get = list = create = update = delete = get_related = get_schema = (  # type: ignore[assignment]
        get_choices
    ) = save_inline_rows = to_dict = lambda *args, **kwargs: None  # type: ignore[assignment]


@pytest.fixture
async def engine() -> AsyncIterator[AsyncEngine]:
    eng = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        poolclass=StaticPool,
        connect_args={"check_same_thread": False},
    )
    async with eng.begin() as conn:
        await conn.run_sync(SQLModel.metadata.create_all)
    yield eng
    await eng.dispose()


class _Result:
    def __init__(self, value: Any) -> None:
        self._value = value

    def scalar_one_or_none(self) -> Any:
        return self._value

    def scalar_one(self) -> Any:
        return self._value


class FakePostgresSession:
    """A session whose dialect is PostgreSQL; ``reltuples`` is what the catalog returns."""

    def __init__(self, reltuples: Any, exact: int = 7) -> None:
        self.reltuples = reltuples
        self.exact = exact
        self.statements: list[tuple[str, dict[str, Any]]] = []

    async def connection(self) -> Any:
        return SimpleNamespace(dialect=postgresql.dialect())

    async def execute(self, statement: Any, params: dict[str, Any] | None = None) -> _Result:
        self.statements.append((str(statement), params or {}))
        return _Result(self.reltuples if params else self.exact)


def _table(name: str = "city", schema: str | None = None) -> Table:
    return Table(name, MetaData(), Column("id", Integer, primary_key=True), schema=schema)


async def test_a_legacy_adapter_reports_no_estimate_available() -> None:
    """
    Scenario: an adapter that predates estimate_row_count keeps working
      Given a BaseAdapter subclass that does not override it
      When  estimate_row_count() is awaited
      Then  NotImplementedError is raised, which callers read as "unknown"
    """
    adapter = LegacyAdapter(model=Country, engine=object())
    with pytest.raises(NotImplementedError):
        await adapter.estimate_row_count()
    assert adapter.estimates_row_count is False


@pytest.mark.parametrize("adapter_cls", [SQLModelAdapter, SQLAlchemyAdapter])
async def test_sqlite_counts_exactly_and_says_it_is_not_an_estimate(
    engine: AsyncEngine, adapter_cls: type
) -> None:
    """
    Scenario: SQLite has no row-estimate catalog
      Given a table with 3 rows on SQLite
      When  estimate_row_count() is awaited
      Then  it returns 3 and estimates_row_count is False
    """
    adapter = adapter_cls(model=Country, engine=engine)
    for name in ("a", "b", "c"):
        await adapter.create({"name": name})

    assert await adapter.estimate_row_count() == 3
    assert adapter.estimates_row_count is False


async def test_postgres_uses_the_planner_statistic() -> None:
    """
    Scenario: PostgreSQL answers from reltuples
      Given the catalog reports 4_200_000 rows
      When  the table's rows are estimated
      Then  that value is returned as an estimate, from one catalog query and no count
    """
    session = FakePostgresSession(reltuples=4_200_000)

    assert await estimate_table_rows(session, _table()) == (4_200_000, True)
    assert len(session.statements) == 1
    assert "reltuples" in session.statements[0][0]
    assert "count(" not in session.statements[0][0].lower()


async def test_postgres_passes_the_quoted_schema_qualified_name_as_a_parameter() -> None:
    """
    Scenario: the table name is bound, schema-qualified and quoted, never interpolated
      Given a table "Odd Name" in schema "tenant"
      When  its rows are estimated on PostgreSQL
      Then  the regclass argument is a bound parameter holding tenant."Odd Name" (quoted only where needed)
    """
    session = FakePostgresSession(reltuples=10)

    await estimate_table_rows(session, _table("Odd Name", schema="tenant"))

    sql, params = session.statements[0]
    assert params == {"tbl": 'tenant."Odd Name"'}
    assert "Odd Name" not in sql
    assert ":tbl" in sql


@pytest.mark.parametrize("reltuples", [0, -1, None])
async def test_postgres_falls_back_to_an_exact_count_when_statistics_are_missing(
    reltuples: int | None,
) -> None:
    """
    Scenario: a never-analyzed or freshly loaded table is counted exactly
      Given reltuples is 0, -1 or absent
      When  the table's rows are estimated
      Then  the exact count is returned and it is not flagged as an estimate
    """
    session = FakePostgresSession(reltuples=reltuples, exact=12)

    assert await estimate_table_rows(session, _table()) == (12, False)
    assert len(session.statements) == 2


async def test_other_dialects_never_query_the_postgres_catalog() -> None:
    """
    Scenario: only PostgreSQL gets the catalog query
      Given a SQLite dialect
      When  the table's rows are estimated
      Then  a single count statement runs
    """

    class SqliteSession(FakePostgresSession):
        async def connection(self) -> Any:
            return SimpleNamespace(dialect=sqlite.dialect())

    session = SqliteSession(reltuples=999, exact=5)

    assert await estimate_table_rows(session, _table()) == (5, False)
    assert len(session.statements) == 1
