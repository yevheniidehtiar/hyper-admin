"""Count cache (SDD adapter-query-performance, A3): scenarios for the cache and both adapters."""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Any

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from sqlalchemy import event
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine
from sqlalchemy.pool import StaticPool
from sqlmodel import Field, SQLModel

from hyperadmin import Admin
from hyperadmin.adapters.sqlalchemy import SQLAlchemyAdapter
from hyperadmin.adapters.sqlmodel import SQLModelAdapter
from hyperadmin.core.cache import CountCache, InMemoryTTLCache
from hyperadmin.core.filtering import FilterCondition
from hyperadmin.core.options import AdminOptions
from hyperadmin.core.registry import site
from hyperadmin.core.settings import HyperAdminSettings

pytestmark = pytest.mark.anyio


class CachedProduct(SQLModel, table=True):
    __tablename__ = "count_cache_product"

    id: int | None = Field(default=None, primary_key=True)
    name: str
    status: str = "active"


class Clock:
    def __init__(self) -> None:
        self.now = 1000.0

    def __call__(self) -> float:
        return self.now


# ---------------------------------------------------------------------------
# InMemoryTTLCache
# ---------------------------------------------------------------------------


async def test_cache_returns_a_value_until_its_ttl_passes() -> None:
    """
    Scenario: an entry expires after its TTL
      Given a value stored for 30 seconds
      When  29 seconds pass the value is returned, and after 30 it is gone
    """
    clock = Clock()
    cache = InMemoryTTLCache(clock=clock)
    key = ("m", "k")
    await cache.set(key, 7, ttl=30)
    clock.now += 29
    assert await cache.get(key) == 7
    clock.now += 1
    assert await cache.get(key) is None
    assert await cache.get(key) is None  # the expired entry was dropped


async def test_cache_drops_the_least_recently_used_entry_when_full() -> None:
    """
    Scenario: the cache is bounded
      Given a cache of two entries holding a and b, with a read last
      When  c is stored
      Then  b (least recently used) is dropped and a, c remain
    """
    cache = InMemoryTTLCache(max_entries=2)
    await cache.set(("m", "a"), 1, ttl=60)
    await cache.set(("m", "b"), 2, ttl=60)
    assert await cache.get(("m", "a")) == 1
    await cache.set(("m", "c"), 3, ttl=60)
    assert await cache.get(("m", "b")) is None
    assert await cache.get(("m", "a")) == 1
    assert await cache.get(("m", "c")) == 3


async def test_invalidate_model_drops_only_that_model() -> None:
    """
    Scenario: a write evicts one model's entries
      Given entries for models A and B
      When  A is invalidated
      Then  A's entries are gone and B's stay
    """
    cache = InMemoryTTLCache()
    await cache.set(("A", 1), 1, ttl=60)
    await cache.set(("A", 2), 2, ttl=60)
    await cache.set(("B", 1), 3, ttl=60)
    await cache.invalidate_model("A")
    assert await cache.get(("A", 1)) is None
    assert await cache.get(("A", 2)) is None
    assert await cache.get(("B", 1)) == 3


def test_cache_rejects_a_non_positive_size() -> None:
    """
    Scenario: a cache must be able to hold an entry
      When  max_entries is 0
      Then  ValueError is raised
    """
    with pytest.raises(ValueError, match="max_entries"):
        InMemoryTTLCache(max_entries=0)


def test_in_memory_cache_satisfies_the_protocol() -> None:
    """
    Scenario: the default cache is a CountCache
      Then  isinstance(InMemoryTTLCache(), CountCache) is True
    """
    assert isinstance(InMemoryTTLCache(), CountCache)


# ---------------------------------------------------------------------------
# Adapters
# ---------------------------------------------------------------------------


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


class CountLog:
    """Counts the ``count(*)`` statements an engine runs."""

    def __init__(self, engine: AsyncEngine) -> None:
        self.statements = 0
        event.listen(engine.sync_engine, "before_cursor_execute", self._on_execute)

    def _on_execute(self, conn: Any, cursor: Any, statement: str, *rest: Any) -> None:
        if "count(" in statement.lower():
            self.statements += 1


def _make(adapter_cls: type, ttl: int, engine: AsyncEngine) -> Any:
    adapter = adapter_cls(model=CachedProduct, engine=engine)
    adapter.count_cache = InMemoryTTLCache()
    adapter.count_cache_ttl = ttl
    return adapter


adapters = pytest.mark.parametrize("adapter_cls", [SQLModelAdapter, SQLAlchemyAdapter])


@adapters
async def test_ttl_zero_counts_on_every_request(engine: AsyncEngine, adapter_cls: type) -> None:
    """
    Scenario: count_cache_ttl=0 disables caching (BC default)
      Given an adapter with a cache but ttl 0
      When  two identical list requests arrive
      Then  the database receives two count queries
    """
    adapter = _make(adapter_cls, 0, engine)
    log = CountLog(engine)
    await adapter.list()
    await adapter.list()
    assert log.statements == 2


@adapters
async def test_a_fresh_cache_entry_skips_the_count(engine: AsyncEngine, adapter_cls: type) -> None:
    """
    Scenario: a cache hit within the TTL serves the total without a round trip
      Given a populated cache
      When  list() runs again with identical arguments and another page
      Then  no count query is issued and the same total is returned
    """
    adapter = _make(adapter_cls, 30, engine)
    for i in range(3):
        await adapter.create({"name": f"p{i}"})
    log = CountLog(engine)
    _, first = await adapter.list(page=1, page_size=2)
    _, second = await adapter.list(page=2, page_size=2)
    assert (first, second) == (3, 3)
    assert log.statements == 1


@adapters
async def test_different_filters_or_search_miss_the_cache(
    engine: AsyncEngine, adapter_cls: type
) -> None:
    """
    Scenario: a cache miss on differing filters issues a fresh count
      Given a cached total for no filters
      When  list() runs with a filter, then with a search
      Then  each issues its own count with its own total
    """
    adapter = _make(adapter_cls, 30, engine)
    await adapter.create({"name": "apple", "status": "active"})
    await adapter.create({"name": "pear", "status": "archived"})
    log = CountLog(engine)
    assert (await adapter.list())[1] == 2
    assert (await adapter.list(filters=[FilterCondition("status", "exact", "archived")]))[1] == 1
    assert (await adapter.list(filters={"status": "active"}))[1] == 1
    assert (await adapter.list(search="apple", search_fields=["name"]))[1] == 1
    assert (await adapter.list(search="apple", search_fields=["status"]))[1] == 0
    assert log.statements == 5


@adapters
async def test_writes_evict_the_models_cached_total(engine: AsyncEngine, adapter_cls: type) -> None:
    """
    Scenario: create, update and delete invalidate the model's count cache
      Given a cached total
      When  a row is created, then updated out of the filter, then deleted
      Then  the next list() issues a fresh count each time
    """
    adapter = _make(adapter_cls, 30, engine)
    active = {"status": "active"}
    first = await adapter.create({"name": "a"})
    assert (await adapter.list(filters=active))[1] == 1
    await adapter.create({"name": "b"})
    assert (await adapter.list(filters=active))[1] == 2
    await adapter.update(first.id, {"status": "archived"})
    assert (await adapter.list(filters=active))[1] == 1
    await adapter.delete(first.id)
    assert (await adapter.list())[1] == 1


@adapters
async def test_unhashable_filter_values_bypass_the_cache(
    engine: AsyncEngine, adapter_cls: type
) -> None:
    """
    Scenario: a query that cannot be keyed is counted every time
      Given a filter whose value is a list
      When  the same list() runs twice
      Then  two count queries are issued
    """
    adapter = _make(adapter_cls, 30, engine)
    await adapter.create({"name": "a"})
    log = CountLog(engine)
    cond = [FilterCondition("status", "in", ["active"])]
    await adapter.list(filters=cond)
    await adapter.list(filters=cond)
    assert log.statements == 2


@adapters
async def test_invalidate_count_cache_clears_the_model(
    engine: AsyncEngine, adapter_cls: type
) -> None:
    """
    Scenario: the application can clear the cache after bulk writes it made itself
      Given a cached total and a row inserted behind the adapter's back
      When  invalidate_count_cache() is awaited
      Then  the next list() sees the new total
    """
    adapter = _make(adapter_cls, 30, engine)
    assert (await adapter.list())[1] == 0
    other = adapter_cls(model=CachedProduct, engine=engine)
    await other.create({"name": "x"})
    assert (await adapter.list())[1] == 0
    await adapter.invalidate_count_cache()
    assert (await adapter.list())[1] == 1


@adapters
async def test_without_a_cache_invalidation_is_a_no_op(
    engine: AsyncEngine, adapter_cls: type
) -> None:
    """
    Scenario: an adapter with no cache still writes
      Given an adapter whose count_cache is None
      When  a row is created and invalidate_count_cache() is awaited
      Then  nothing fails
    """
    adapter = adapter_cls(model=CachedProduct, engine=engine)
    await adapter.create({"name": "x"})
    await adapter.invalidate_count_cache()


# ---------------------------------------------------------------------------
# Wiring: AdminOptions -> router -> adapter
# ---------------------------------------------------------------------------


def test_count_cache_ttl_rejects_negative_values() -> None:
    """
    Scenario: the TTL cannot be negative
      When  AdminOptions(count_cache_ttl=-1) is built
      Then  validation fails
    """
    with pytest.raises(ValueError, match="count_cache_ttl"):
        AdminOptions(count_cache_ttl=-1)


async def test_the_option_reaches_the_list_view(engine: AsyncEngine) -> None:
    """
    Scenario: a model registered with a TTL does not recount on the second page view
      Given a model registered with AdminOptions(count_cache_ttl=30)
      When  its list page is requested twice
      Then  one count query reaches the database
    """
    site._registry = {}
    app = FastAPI()
    admin = Admin(app=app, engine=engine, settings=HyperAdminSettings(create_tables=False))
    site.register(CachedProduct, options=AdminOptions(count_cache_ttl=30))
    admin.mount(path="/admin")
    log = CountLog(engine)
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as client:
            for _ in range(2):
                response = await client.get("/admin/cachedproduct")
                assert response.status_code == 200
    finally:
        site._registry = {}
    assert log.statements == 1


async def test_the_cache_size_comes_from_settings(engine: AsyncEngine) -> None:
    """
    Scenario: count_cache_max_entries bounds the admin's cache
      Given settings with count_cache_max_entries=1
      When  two different list totals are cached for one model
      Then  only the most recent stays, so the first is counted again
    """
    site._registry = {}
    app = FastAPI()
    admin = Admin(
        app=app,
        engine=engine,
        settings=HyperAdminSettings(create_tables=False, count_cache_max_entries=1),
    )
    site.register(CachedProduct, options=AdminOptions(count_cache_ttl=30))
    admin.mount(path="/admin")
    log = CountLog(engine)
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as client:
            await client.get("/admin/cachedproduct")
            await client.get("/admin/cachedproduct?search=zzz")
            await client.get("/admin/cachedproduct")
    finally:
        site._registry = {}
    assert log.statements == 3


def test_cache_size_setting_must_be_positive() -> None:
    """
    Scenario: the cache cannot be sized to zero
      When  count_cache_max_entries=0 is configured
      Then  validation fails
    """
    with pytest.raises(ValueError, match="count_cache_max_entries"):
        HyperAdminSettings(count_cache_max_entries=0)
