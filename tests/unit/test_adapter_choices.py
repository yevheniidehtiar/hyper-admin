"""Unit tests for SQLModelAdapter.get_choices() — N+1 safety verified."""

import pytest
from sqlalchemy import event
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, create_async_engine
from sqlalchemy.orm import Mapped
from sqlmodel import Field, Relationship, SQLModel, select

# ---------------------------------------------------------------------------
# Schema fixtures
# ---------------------------------------------------------------------------


class Country(SQLModel, table=True):
    __tablename__: str = "countries_choices"
    id: int | None = Field(default=None, primary_key=True)
    name: str

    cities: Mapped[list["City"]] = Relationship(back_populates="country")

    def __str__(self) -> str:
        return self.name


class City(SQLModel, table=True):
    __tablename__: str = "cities_choices"
    id: int | None = Field(default=None, primary_key=True)
    name: str
    country_id: int | None = Field(default=None, foreign_key="countries_choices.id")

    country: Mapped[Country | None] = Relationship(back_populates="cities")

    def __str__(self) -> str:
        return self.name


@pytest.fixture
async def engine() -> AsyncEngine:
    eng = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    async with eng.begin() as conn:
        await conn.run_sync(SQLModel.metadata.create_all)
    yield eng
    async with eng.begin() as conn:
        await conn.run_sync(SQLModel.metadata.drop_all)
    await eng.dispose()


@pytest.fixture
async def populated_db(engine: AsyncEngine) -> None:
    async with AsyncSession(engine) as session:
        uk = Country(name="United Kingdom")
        fr = Country(name="France")
        session.add_all([uk, fr])
        await session.commit()
        await session.refresh(uk)
        await session.refresh(fr)
        session.add_all(
            [
                City(name="London", country_id=uk.id),
                City(name="Manchester", country_id=uk.id),
                City(name="Paris", country_id=fr.id),
            ]
        )
        await session.commit()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def query_counter(engine: AsyncEngine) -> list[str]:
    """Accumulate SQL statements issued against *engine* during a test."""
    log: list[str] = []

    @event.listens_for(engine.sync_engine, "before_cursor_execute")
    def _record(conn, cursor, statement, parameters, context, executemany):
        log.append(statement)

    return log


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


@pytest.mark.anyio
async def test_get_choices_fk_single_query(engine: AsyncEngine, populated_db: None) -> None:
    from hyperadmin.adapters.sqlmodel import SQLModelAdapter

    adapter = SQLModelAdapter(City, engine)
    log = query_counter(engine)

    choices = await adapter.get_choices("country")

    select_stmts = [s for s in log if s.strip().upper().startswith("SELECT")]
    assert len(select_stmts) == 1, f"Expected 1 SELECT, got {len(select_stmts)}"
    assert len(choices) == 2
    labels = {c["label"] for c in choices}
    assert "United Kingdom" in labels
    assert "France" in labels
    assert all(c["selected"] is False for c in choices)


@pytest.mark.anyio
async def test_get_choices_search_filters_results(engine: AsyncEngine, populated_db: None) -> None:
    from hyperadmin.adapters.sqlmodel import SQLModelAdapter

    adapter = SQLModelAdapter(City, engine)
    choices = await adapter.get_choices("country", q="uni")

    assert len(choices) == 1
    assert choices[0]["label"] == "United Kingdom"


@pytest.mark.anyio
async def test_get_choices_pagination(engine: AsyncEngine, populated_db: None) -> None:
    from hyperadmin.adapters.sqlmodel import SQLModelAdapter

    adapter = SQLModelAdapter(City, engine)
    page1 = await adapter.get_choices("country", limit=1, offset=0)
    page2 = await adapter.get_choices("country", limit=1, offset=1)

    assert len(page1) == 1
    assert len(page2) == 1
    assert page1[0]["value"] != page2[0]["value"]


@pytest.mark.anyio
async def test_get_choices_cascading_filter(engine: AsyncEngine, populated_db: None) -> None:
    from hyperadmin.adapters.sqlmodel import SQLModelAdapter

    async with AsyncSession(engine) as session:
        result = await session.execute(select(Country).where(Country.name == "United Kingdom"))
        uk = result.scalar_one()
        uk_id = uk.id

    adapter = SQLModelAdapter(Country, engine)
    choices = await adapter.get_choices("cities", country_id=uk_id)

    assert len(choices) == 2
    labels = {c["label"] for c in choices}
    assert "London" in labels
    assert "Manchester" in labels


@pytest.mark.anyio
async def test_get_choices_limit_exceeds_max_raises(engine: AsyncEngine) -> None:
    from hyperadmin.adapters.sqlmodel import SQLModelAdapter

    adapter = SQLModelAdapter(City, engine)
    with pytest.raises(ValueError, match="exceeds maximum"):
        await adapter.get_choices("country", limit=201)


@pytest.mark.anyio
async def test_get_choices_unknown_field_returns_empty(engine: AsyncEngine) -> None:
    from hyperadmin.adapters.sqlmodel import SQLModelAdapter

    adapter = SQLModelAdapter(City, engine)
    choices = await adapter.get_choices("nonexistent_field")
    assert choices == []
