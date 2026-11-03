"""Filter metadata cache (SDD filter-choice-scalability, C2): FK filter choices within a TTL."""

from collections.abc import AsyncIterator
from typing import Any

import pytest
from sqlalchemy import event
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine
from sqlalchemy.pool import StaticPool
from sqlmodel import Field, Relationship, SQLModel

from hyperadmin.adapters.sqlmodel import SQLModelAdapter
from hyperadmin.core.cache import InMemoryTTLCache
from hyperadmin.core.discovery import build_filter_metadata
from hyperadmin.core.options import AdminOptions

pytestmark = pytest.mark.anyio


class Brand(SQLModel, table=True):
    __tablename__ = "filter_cache_brand"

    id: int | None = Field(default=None, primary_key=True)
    name: str


class Gadget(SQLModel, table=True):
    __tablename__ = "filter_cache_gadget"

    id: int | None = Field(default=None, primary_key=True)
    name: str
    brand_id: int | None = Field(default=None, foreign_key="filter_cache_brand.id")
    brand: Brand | None = Relationship(sa_relationship_kwargs={"lazy": "selectin"})


class Clock:
    def __init__(self) -> None:
        self.now = 1000.0

    def __call__(self) -> float:
        return self.now


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


def _gadgets(engine: AsyncEngine, *, ttl: int, cache: InMemoryTTLCache | None) -> SQLModelAdapter:
    adapter = SQLModelAdapter(model=Gadget, engine=engine)
    adapter.count_cache = cache
    adapter.filter_cache_ttl = ttl
    return adapter


def _brand_selects(engine: AsyncEngine) -> list[str]:
    seen: list[str] = []

    @event.listens_for(engine.sync_engine, "before_cursor_execute")
    def _record(conn: Any, cursor: Any, statement: str, *rest: Any) -> None:
        if "FROM filter_cache_brand" in statement and "count(" not in statement.lower():
            seen.append(statement)

    return seen


async def _seed_brands(engine: AsyncEngine, *names: str) -> SQLModelAdapter:
    brands = SQLModelAdapter(model=Brand, engine=engine)
    for name in names:
        await brands.create({"name": name})
    return brands


def _labels(metadata: list[dict[str, Any]]) -> list[str]:
    return [choice["label"] for choice in metadata[0]["choices"]]


async def test_filter_choices_are_fetched_once_within_the_ttl(engine: AsyncEngine) -> None:
    """
    Scenario: filter metadata is cached within the TTL window
      Given filter_cache_ttl = 60 and a Brand foreign-key filter
      When  the metadata is built three times in a row
      Then  the Brand table is queried once
    """
    await _seed_brands(engine, "Acme")
    selects = _brand_selects(engine)
    adapter = _gadgets(engine, ttl=60, cache=InMemoryTTLCache())

    for _ in range(3):
        metadata = await build_filter_metadata(Gadget, ["brand_id"], adapter)

    assert _labels(metadata) == ["Acme"]
    assert len(selects) == 1


async def test_filter_choices_are_refreshed_after_the_ttl(engine: AsyncEngine) -> None:
    """
    Scenario: filter metadata is refreshed after TTL expiry
      Given a cached Brand filter with filter_cache_ttl = 60
      When  61 seconds pass and the metadata is built again
      Then  the Brand table is queried again
    """
    await _seed_brands(engine, "Acme")
    clock = Clock()
    selects = _brand_selects(engine)
    adapter = _gadgets(engine, ttl=60, cache=InMemoryTTLCache(clock=clock))

    await build_filter_metadata(Gadget, ["brand_id"], adapter)
    clock.now += 61
    await build_filter_metadata(Gadget, ["brand_id"], adapter)

    assert len(selects) == 2


async def test_ttl_zero_queries_on_every_build(engine: AsyncEngine) -> None:
    """
    Scenario: filter_cache_ttl = 0 restores the uncached behaviour
      Given filter_cache_ttl = 0
      When  the metadata is built twice
      Then  the Brand table is queried twice and nothing is cached
    """
    await _seed_brands(engine, "Acme")
    cache = InMemoryTTLCache()
    selects = _brand_selects(engine)
    adapter = _gadgets(engine, ttl=0, cache=cache)

    await build_filter_metadata(Gadget, ["brand_id"], adapter)
    await build_filter_metadata(Gadget, ["brand_id"], adapter)

    assert len(selects) == 2
    assert not cache._entries


async def test_an_adapter_without_a_cache_queries_every_time(engine: AsyncEngine) -> None:
    """
    Scenario: no cache is wired
      Given a positive TTL but no cache on the adapter
      When  the metadata is built twice
      Then  the Brand table is queried twice
    """
    await _seed_brands(engine, "Acme")
    selects = _brand_selects(engine)
    adapter = _gadgets(engine, ttl=60, cache=None)

    await build_filter_metadata(Gadget, ["brand_id"], adapter)
    await build_filter_metadata(Gadget, ["brand_id"], adapter)

    assert len(selects) == 2


async def test_a_write_through_the_related_adapter_evicts_the_cached_choices(
    engine: AsyncEngine,
) -> None:
    """
    Scenario: creating a related row shows up without waiting for the TTL
      Given Brand choices cached for 60 seconds
      When  a Brand is created through its adapter
      Then  the next build lists the new Brand
    """
    cache = InMemoryTTLCache()
    brands = await _seed_brands(engine, "Acme")
    brands.count_cache = cache
    adapter = _gadgets(engine, ttl=60, cache=cache)
    assert _labels(await build_filter_metadata(Gadget, ["brand_id"], adapter)) == ["Acme"]

    await brands.create({"name": "Globex"})

    assert _labels(await build_filter_metadata(Gadget, ["brand_id"], adapter)) == [
        "Acme",
        "Globex",
    ]


async def test_applied_selections_are_added_without_polluting_the_cache(
    engine: AsyncEngine,
) -> None:
    """
    Scenario: a selected row outside the first page is listed for that request only
      Given 55 brands, 50 of which are listed
      When  the metadata is built with brand 55 selected, then without a selection
      Then  the first build lists 51 choices including brand 55 and the second lists 50
    """
    await _seed_brands(engine, *(f"Brand {n:02d}" for n in range(1, 56)))
    adapter = _gadgets(engine, ttl=60, cache=InMemoryTTLCache())

    with_selection = await build_filter_metadata(
        Gadget, ["brand_id"], adapter, {"brand_id": ["55"]}
    )
    without = await build_filter_metadata(Gadget, ["brand_id"], adapter)

    assert len(with_selection[0]["choices"]) == 51
    assert "Brand 55" in _labels(with_selection)
    assert len(without[0]["choices"]) == 50


async def test_a_caller_cannot_mutate_the_cached_choices(engine: AsyncEngine) -> None:
    """
    Scenario: cached choices are copied out
      Given Brand choices in the cache
      When  a caller edits a returned choice
      Then  the next build still returns the original label
    """
    await _seed_brands(engine, "Acme")
    adapter = _gadgets(engine, ttl=60, cache=InMemoryTTLCache())

    first = await build_filter_metadata(Gadget, ["brand_id"], adapter)
    first[0]["choices"][0]["label"] = "tampered"

    assert _labels(await build_filter_metadata(Gadget, ["brand_id"], adapter)) == ["Acme"]


def test_filter_cache_ttl_defaults_to_sixty_and_rejects_negatives() -> None:
    """
    Scenario: the option has a safe default and bounds
      Given AdminOptions
      When  filter_cache_ttl is left unset or set below zero
      Then  it is 60, and a negative value is rejected
    """
    assert AdminOptions().filter_cache_ttl == 60
    with pytest.raises(ValueError, match="filter_cache_ttl"):
        AdminOptions(filter_cache_ttl=-1)
