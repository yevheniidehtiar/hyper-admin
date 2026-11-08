"""Unfiltered list totals can come from the table estimate (SDD adapter-query-performance A3)."""

from typing import Any

import anyio
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from pydantic import ValidationError
from sqlalchemy import event
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, create_async_engine
from sqlmodel import Field, SQLModel

from hyperadmin import Admin
from hyperadmin.adapters.sqlalchemy import SQLAlchemyAdapter
from hyperadmin.adapters.sqlmodel import SQLModelAdapter
from hyperadmin.core.model import ModelAdmin
from hyperadmin.core.options import AdminOptions
from hyperadmin.core.registry import site
from hyperadmin.core.settings import HyperAdminSettings

ROWS = 3


class CeItem(SQLModel, table=True):
    __tablename__ = "test_ce_item"
    id: int | None = Field(default=None, primary_key=True)
    name: str


@pytest.fixture(autouse=True)
def _cleanup_registry():
    site._registry = {}
    yield
    site._registry = {}


@pytest.fixture(params=[SQLModelAdapter, SQLAlchemyAdapter], ids=["sqlmodel", "sqlalchemy"])
def adapter_cls(request: pytest.FixtureRequest) -> type[SQLModelAdapter]:
    return request.param


async def _seed_engine() -> AsyncEngine:
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.create_all)
    async with AsyncSession(engine) as session:
        for i in range(1, ROWS + 1):
            session.add(CeItem(id=i, name=f"item {i}"))
        await session.commit()
    return engine


def _seeded_engine() -> AsyncEngine:
    return anyio.run(_seed_engine)


def _count_statements(engine: AsyncEngine) -> list[str]:
    statements: list[str] = []

    @event.listens_for(engine.sync_engine, "before_cursor_execute")
    def _capture(conn: Any, cursor: Any, statement: str, *rest: Any) -> None:
        if "count(" in statement.lower():
            statements.append(statement)

    return statements


def _adapter(
    adapter_cls: type[SQLModelAdapter],
    engine: AsyncEngine,
    *,
    threshold: int | None,
    estimate: int | None,
    planner: bool = True,
) -> SQLModelAdapter:
    """An adapter whose table estimate is ``estimate`` (``None``: cannot estimate)."""
    adapter = adapter_cls(CeItem, engine)
    adapter.count_estimate_threshold = threshold

    async def fake_estimate() -> int:
        if estimate is None:
            raise NotImplementedError
        adapter.estimates_row_count = planner
        return estimate

    adapter.estimate_row_count = fake_estimate  # type: ignore[method-assign]
    return adapter


@pytest.mark.anyio
async def test_large_unfiltered_table_uses_the_estimate(adapter_cls: type[SQLModelAdapter]) -> None:
    """
    Scenario: a large unfiltered table uses the estimate instead of COUNT(*)
      Given count_estimate_threshold = 1_000_000 and an estimate of 4_200_000
      When  list() is called with no search or filters
      Then  no COUNT(*) query is issued
      And   the total is 4_200_000 and flagged as an estimate
    """
    engine = await _seed_engine()
    counts = _count_statements(engine)
    adapter = _adapter(adapter_cls, engine, threshold=1_000_000, estimate=4_200_000)

    _, total = await adapter.list()

    assert total == 4_200_000
    assert counts == []
    assert adapter.total_is_estimate() is True


@pytest.mark.anyio
async def test_filtered_list_uses_the_exact_count(adapter_cls: type[SQLModelAdapter]) -> None:
    """
    Scenario: a filtered list always uses the exact count
      Given the same options and estimate
      When  list() is called with a search
      Then  an exact COUNT(*) is issued
      And   the total is not flagged as an estimate
    """
    engine = await _seed_engine()
    counts = _count_statements(engine)
    adapter = _adapter(adapter_cls, engine, threshold=1_000_000, estimate=4_200_000)

    _, total = await adapter.list(search="item", search_fields=["name"])

    assert total == ROWS
    assert len(counts) == 1
    assert adapter.total_is_estimate() is False


@pytest.mark.anyio
async def test_table_below_the_threshold_stays_exact(adapter_cls: type[SQLModelAdapter]) -> None:
    """
    Scenario: a table below the threshold stays exact
      Given count_estimate_threshold = 1_000_000 and an estimate of 12_000
      When  list() is called with no filters
      Then  an exact COUNT(*) is issued
    """
    engine = await _seed_engine()
    counts = _count_statements(engine)
    adapter = _adapter(adapter_cls, engine, threshold=1_000_000, estimate=12_000)

    _, total = await adapter.list()

    assert total == ROWS
    assert len(counts) == 1
    assert adapter.total_is_estimate() is False


@pytest.mark.anyio
async def test_adapter_that_cannot_estimate_falls_back_to_exact(
    adapter_cls: type[SQLModelAdapter],
) -> None:
    """
    Scenario: an adapter that cannot estimate falls back to the exact count
      Given a threshold and an adapter whose estimate_row_count is not implemented
      When  list() is called with no filters
      Then  an exact COUNT(*) is issued
    """
    engine = await _seed_engine()
    counts = _count_statements(engine)
    adapter = _adapter(adapter_cls, engine, threshold=1_000_000, estimate=None)

    _, total = await adapter.list()

    assert total == ROWS
    assert len(counts) == 1
    assert adapter.total_is_estimate() is False


@pytest.mark.anyio
@pytest.mark.parametrize("estimate", [0, -1])
async def test_stale_estimate_falls_back_to_exact(
    adapter_cls: type[SQLModelAdapter], estimate: int
) -> None:
    """
    Scenario: an estimate of 0 or less falls back to the exact count
      Given a threshold of 1 and a table whose statistics say 0 (or -1) rows
      When  list() is called with no filters
      Then  an exact COUNT(*) is issued
    """
    engine = await _seed_engine()
    counts = _count_statements(engine)
    adapter = _adapter(adapter_cls, engine, threshold=1, estimate=estimate)

    _, total = await adapter.list()

    assert total == ROWS
    assert len(counts) == 1


@pytest.mark.anyio
async def test_exact_count_from_the_adapter_is_not_flagged_as_estimate(
    adapter_cls: type[SQLModelAdapter],
) -> None:
    """
    Scenario: an exact whole-table count is never shown as an estimate
      Given an adapter whose estimate_row_count returned an exact count (not planner statistics)
      When  list() is called with no filters
      Then  an exact COUNT(*) is issued
      And   the total is not flagged as an estimate
    """
    engine = await _seed_engine()
    counts = _count_statements(engine)
    adapter = _adapter(adapter_cls, engine, threshold=1, estimate=500, planner=False)

    _, total = await adapter.list()

    assert total == ROWS
    assert len(counts) == 1
    assert adapter.total_is_estimate() is False


@pytest.mark.anyio
async def test_default_threshold_never_estimates(adapter_cls: type[SQLModelAdapter]) -> None:
    """
    Scenario: without a threshold totals stay exact
      Given count_estimate_threshold is None
      When  list() is called with no filters
      Then  estimate_row_count is not called
      And   an exact COUNT(*) is issued
    """
    engine = await _seed_engine()
    counts = _count_statements(engine)
    adapter = _adapter(adapter_cls, engine, threshold=None, estimate=4_200_000)

    _, total = await adapter.list()

    assert total == ROWS
    assert len(counts) == 1


def test_count_estimate_threshold_option_defaults_to_none_and_rejects_zero() -> None:
    """
    Scenario: the option is off by default and must be positive
      Given AdminOptions()
      Then  count_estimate_threshold is None
      And   a threshold of 0 is rejected
    """
    assert AdminOptions().count_estimate_threshold is None
    with pytest.raises(ValidationError):
        AdminOptions(count_estimate_threshold=0)


def _client(monkeypatch: pytest.MonkeyPatch, **options: Any) -> TestClient:
    async def planner_estimate(self: SQLModelAdapter) -> int:
        self.estimates_row_count = True
        return 4_200_000

    monkeypatch.setattr(SQLModelAdapter, "estimate_row_count", planner_estimate)
    app = FastAPI()
    admin = Admin(
        app=app, engine=_seeded_engine(), settings=HyperAdminSettings(create_tables=False)
    )
    site.register(
        CeItem,
        type(
            "CeItemAdmin",
            (ModelAdmin,),
            {"adapter_class": SQLModelAdapter, "options": AdminOptions(**options)},
        ),
    )
    admin.mount(path="/admin")
    return TestClient(app)


def test_list_page_shows_an_estimated_total_with_a_tilde(monkeypatch: pytest.MonkeyPatch) -> None:
    """
    Scenario: an estimated total is marked as approximate
      Given count_estimate_threshold = 1_000_000 and an estimate of 4_200_000
      When  the unfiltered list page is rendered
      Then  the pager reads "of ~4200000 results"
    """
    body = _client(monkeypatch, count_estimate_threshold=1_000_000).get("/admin/ceitem").text

    assert "~4200000" in body


def test_list_page_shows_the_exact_total_by_default(monkeypatch: pytest.MonkeyPatch) -> None:
    """
    Scenario: without a threshold the pager shows the exact total
      Given no count_estimate_threshold
      When  the list page is rendered
      Then  the pager reads "of 3 results" with no tilde
    """
    body = _client(monkeypatch).get("/admin/ceitem").text

    assert f"of {ROWS} results" in body
    assert "~" not in body.split('data-testid="pagination-info"')[1].split("</div>")[0]
