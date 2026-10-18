"""Unit tests for the ``FactTableSource`` cache seam and the ``ReportView`` source dispatcher.

Scenarios map 1:1 to
``.meta/epics/epic-v054-olap-reporting/stories/featreports-source-dispatch-and-filters.md``.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from datetime import datetime, timezone
from typing import Any

import pytest
from sqlalchemy import event
from sqlalchemy.dialects import postgresql
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlmodel import Field, SQLModel

from hyperadmin_reports import (
    FactTableSource,
    Group,
    ReportView,
    Sum,
    TimeBucket,
    register_report,
)

pytestmark = pytest.mark.anyio

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


class CacheOrder(SQLModel, table=True):
    __tablename__ = "test_reports_cache_order"

    id: int | None = Field(default=None, primary_key=True)
    sku: str
    amount: int
    created_at: datetime


class CacheOrderDailyFact(SQLModel, table=True):
    """Pre-aggregated fact table: one row per (sku, day)."""

    __tablename__ = "test_reports_cache_order_daily_fact"

    id: int | None = Field(default=None, primary_key=True)
    sku: str
    amount: int
    created_at: datetime


class CacheFactWithoutSku(SQLModel, table=True):
    __tablename__ = "test_reports_cache_fact_without_sku"

    id: int | None = Field(default=None, primary_key=True)
    amount: int
    created_at: datetime


class CacheFactAmountOnly(SQLModel, table=True):
    __tablename__ = "test_reports_cache_fact_amount_only"

    id: int | None = Field(default=None, primary_key=True)
    amount: int


class LiveRevenue(ReportView):
    slug = "cache-live-revenue"
    model = CacheOrder
    rows = [Group("sku")]
    cols = [TimeBucket("created_at", period="auto")]
    values = [Sum("amount")]


class CachedRevenue(LiveRevenue):
    slug = "cache-cached-revenue"
    cache = FactTableSource(model=CacheOrderDailyFact)


def _at(month: int, day: int, hour: int = 0) -> datetime:
    return datetime(2025, month, day, hour, tzinfo=timezone.utc)


ORDERS: list[tuple[str, int, datetime]] = [
    ("A", 10, _at(1, 5, 9)),
    ("A", 15, _at(1, 5, 17)),
    ("A", 20, _at(2, 10)),
    ("B", 5, _at(1, 20)),
    ("A", 7, _at(11, 30)),
]

DAILY_FACTS: list[tuple[str, int, datetime]] = [
    ("A", 25, _at(1, 5)),
    ("A", 20, _at(2, 10)),
    ("B", 5, _at(1, 20)),
    ("A", 7, _at(11, 30)),
]


@pytest.fixture
async def engine() -> AsyncIterator[AsyncEngine]:
    eng = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with eng.begin() as conn:
        await conn.run_sync(SQLModel.metadata.create_all)
    yield eng
    await eng.dispose()


@pytest.fixture
async def seeded(engine: AsyncEngine) -> AsyncIterator[AsyncSession]:
    async with AsyncSession(engine) as session:
        session.add_all(CacheOrder(sku=s, amount=a, created_at=at) for s, a, at in ORDERS)
        session.add_all(
            CacheOrderDailyFact(sku=s, amount=a, created_at=at) for s, a, at in DAILY_FACTS
        )
        await session.commit()
        yield session


def _capture_sql(engine: AsyncEngine) -> list[str]:
    statements: list[str] = []

    def before_execute(*args: Any) -> None:
        statements.append(args[2])

    event.listen(engine.sync_engine, "before_cursor_execute", before_execute)
    return statements


# ---------------------------------------------------------------------------
# Scenario: cache source replaces live query
# ---------------------------------------------------------------------------


async def test_cache_source_replaces_live_query(engine: AsyncEngine, seeded: AsyncSession) -> None:
    # Given
    reference = await LiveRevenue.run(seeded)
    statements = _capture_sql(engine)
    # When
    result = await CachedRevenue.run(seeded)
    # Then
    assert statements
    assert all("test_reports_cache_order_daily_fact" in sql for sql in statements)
    assert not any("FROM test_reports_cache_order " in f"{sql} " for sql in statements)
    assert result.records == reference.records
    assert result.periods == reference.periods == {"created_at": "quarter"}


def test_live_query_is_the_default_source() -> None:
    assert LiveRevenue.cache is None
    assert LiveRevenue.source_model() is CacheOrder
    assert CachedRevenue.source_model() is CacheOrderDailyFact
    sql = str(
        CachedRevenue.build_query("postgresql", {"created_at": "month"}).compile(
            dialect=postgresql.dialect()
        )
    )
    assert "FROM test_reports_cache_order_daily_fact" in sql


# ---------------------------------------------------------------------------
# Scenario: cache validation rejects missing columns
# ---------------------------------------------------------------------------


def test_cache_validation_rejects_missing_columns() -> None:
    # Given
    class MissingSku(LiveRevenue):
        slug = "cache-missing-sku"
        cache = FactTableSource(model=CacheFactWithoutSku)

    # When / Then
    with pytest.raises(ValueError, match=r"^FactTableSource missing column 'sku'$"):
        register_report(MissingSku)


def test_cache_validation_lists_every_missing_column() -> None:
    class MissingMany(LiveRevenue):
        slug = "cache-missing-many"
        cache = FactTableSource(model=CacheFactAmountOnly)

    with pytest.raises(ValueError, match=r"^FactTableSource missing columns 'sku', 'created_at'$"):
        register_report(MissingMany)


def test_register_report_returns_the_valid_report() -> None:
    assert register_report(CachedRevenue) is CachedRevenue
    assert register_report(LiveRevenue) is LiveRevenue


def test_fact_table_source_columns_and_repr() -> None:
    source = FactTableSource(model=CacheFactAmountOnly)
    assert source.columns == {"id", "amount"}
    assert repr(source) == "FactTableSource(model=CacheFactAmountOnly)"


# ---------------------------------------------------------------------------
# ``where`` seam (filter library integration lands with v0.5.6)
# ---------------------------------------------------------------------------


async def test_where_clauses_apply_before_the_aggregate(seeded: AsyncSession) -> None:
    window = [CacheOrder.created_at >= _at(1, 10), CacheOrder.created_at < _at(3, 1)]
    result = await LiveRevenue.run(seeded, where=window)
    assert result.records == [
        {"sku": "A", "created_at": "2025-02-10", "sum_amount": 20},
        {"sku": "B", "created_at": "2025-01-20", "sum_amount": 5},
    ]
    # The auto period is resolved over the filtered range (2025-01-20 .. 2025-02-10).
    assert result.periods == {"created_at": "day"}


async def test_where_clauses_target_the_cache_source(
    engine: AsyncEngine, seeded: AsyncSession
) -> None:
    factory = async_sessionmaker(engine, expire_on_commit=False)
    result = await CachedRevenue.run(factory, where=[CacheOrderDailyFact.sku == "B"])
    assert result.records == [{"sku": "B", "created_at": "2025-01-20", "sum_amount": 5}]
