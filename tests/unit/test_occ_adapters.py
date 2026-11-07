"""Adapter-level optimistic concurrency (SDD realtime-occ)."""

from datetime import UTC, datetime
from typing import Any

import pytest
from sqlalchemy.ext.asyncio import create_async_engine
from sqlmodel import Field, SQLModel

from hyperadmin.adapters.sqlalchemy import SQLAlchemyAdapter
from hyperadmin.adapters.sqlmodel import SQLModelAdapter
from hyperadmin.core.concurrency import StaleRecordError
from hyperadmin.realtime.emitting import EventEmittingAdapter


class OccOrder(SQLModel, table=True):
    __tablename__ = "occ_order"
    id: int | None = Field(default=None, primary_key=True)
    name: str
    version: int = 1


class OccStamped(SQLModel, table=True):
    __tablename__ = "occ_stamped"
    id: int | None = Field(default=None, primary_key=True)
    name: str
    updated_at: datetime = Field(default_factory=lambda: datetime(2020, 1, 1, tzinfo=UTC))


@pytest.fixture
async def engine():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.create_all)
    return engine


@pytest.fixture(params=[SQLModelAdapter, SQLAlchemyAdapter], ids=["sqlmodel", "sqlalchemy"])
def adapter_cls(request: pytest.FixtureRequest) -> Any:
    return request.param


async def _order(adapter_cls: Any, engine: Any, version: int = 3) -> Any:
    adapter = adapter_cls(OccOrder, engine=engine)
    adapter.version_field = "version"
    created = await adapter.create({"name": "Bob", "version": version})
    return adapter, created.id


@pytest.mark.anyio
async def test_update_succeeds_when_expected_version_matches(adapter_cls, engine) -> None:
    """
    Scenario: update succeeds when expected_version matches current
      Given order#1 has version=3
      When  adapter.update(1, {"name": "Alice"}, expected_version=3) is called
      Then  the row is updated and the new version is 4
    """
    adapter, pk = await _order(adapter_cls, engine)
    row = await adapter.update(pk, {"name": "Alice"}, expected_version=3)
    assert (row.name, row.version) == ("Alice", 4)
    assert (await adapter.get(pk)).version == 4


@pytest.mark.anyio
async def test_update_coerces_string_expected_version(adapter_cls, engine) -> None:
    """A form posts ``__version`` as text; the adapter coerces it to the column type."""
    adapter, pk = await _order(adapter_cls, engine)
    row = await adapter.update(pk, {"name": "Alice"}, expected_version="3")
    assert row.version == 4


@pytest.mark.anyio
async def test_update_raises_stale_record_error_and_leaves_row(adapter_cls, engine) -> None:
    """
    Scenario: update raises StaleRecordError when expected_version is stale
      Given order#1 has version=3
      When  update is called with expected_version=2
      Then  StaleRecordError is raised with current=3, expected=2 and the row is unchanged
    """
    adapter, pk = await _order(adapter_cls, engine)
    with pytest.raises(StaleRecordError) as caught:
        await adapter.update(pk, {"name": "Alice"}, expected_version=2)
    assert (caught.value.current, caught.value.expected, caught.value.pk) == (3, 2, pk)
    row = await adapter.get(pk)
    assert (row.name, row.version) == ("Bob", 3)


@pytest.mark.anyio
async def test_second_writer_with_same_version_loses(adapter_cls, engine) -> None:
    """Two writers read version 3; the first wins, the second gets a StaleRecordError."""
    adapter, pk = await _order(adapter_cls, engine)
    await adapter.update(pk, {"name": "Alice"}, expected_version=3)
    with pytest.raises(StaleRecordError):
        await adapter.update(pk, {"name": "Carol"}, expected_version=3)


@pytest.mark.anyio
async def test_posted_version_value_is_ignored(adapter_cls, engine) -> None:
    """The adapter owns the version column: a version inside ``data`` cannot overwrite the bump."""
    adapter, pk = await _order(adapter_cls, engine)
    row = await adapter.update(pk, {"name": "Alice", "version": 99}, expected_version=3)
    assert row.version == 4


@pytest.mark.anyio
async def test_update_of_missing_row_returns_none(adapter_cls, engine) -> None:
    adapter, _ = await _order(adapter_cls, engine)
    assert await adapter.update(999, {"name": "x"}, expected_version=1) is None


@pytest.mark.anyio
async def test_without_expected_version_is_last_write_wins(adapter_cls, engine) -> None:
    """
    Scenario: enforce_occ=False preserves legacy behaviour
      When  update is called without expected_version
      Then  the write succeeds and the version column is untouched
    """
    adapter, pk = await _order(adapter_cls, engine)
    row = await adapter.update(pk, {"name": "Alice"})
    assert (row.name, row.version) == ("Alice", 3)


@pytest.mark.anyio
async def test_expected_version_ignored_without_version_field(adapter_cls, engine) -> None:
    """An adapter that was not given a version field never enforces OCC."""
    adapter = adapter_cls(OccOrder, engine=engine)
    created = await adapter.create({"name": "Bob", "version": 3})
    row = await adapter.update(created.id, {"name": "Alice"}, expected_version=1)
    assert (row.name, row.version) == ("Alice", 3)


@pytest.mark.anyio
async def test_updated_at_version_refreshes_timestamp(adapter_cls, engine) -> None:
    """
    Scenario: updated_at fallback rejects stale writes
      Given a row whose updated_at is the version token
      Then  a matching ISO-8601 token succeeds and refreshes updated_at
      And   the old token is then stale
    """
    adapter = adapter_cls(OccStamped, engine=engine)
    adapter.version_field = "updated_at"
    created = await adapter.create({"name": "Bob"})
    token = created.updated_at.isoformat()
    row = await adapter.update(created.id, {"name": "Alice"}, expected_version=token)
    assert row.name == "Alice"
    assert row.updated_at.replace(tzinfo=None) > datetime(2020, 1, 2)
    with pytest.raises(StaleRecordError):
        await adapter.update(created.id, {"name": "Carol"}, expected_version=token)


@pytest.mark.anyio
async def test_event_emitting_adapter_forwards_expected_version(engine) -> None:
    """The realtime proxy passes ``expected_version`` through and stays quiet on a conflict."""
    inner = SQLModelAdapter(OccOrder, engine=engine)
    inner.version_field = "version"
    created = await inner.create({"name": "Bob", "version": 3})
    emitted: list[Any] = []

    class _Emitter:
        def schedule(self, event: Any) -> None:
            emitted.append(event)

    proxy = EventEmittingAdapter(inner, _Emitter())  # type: ignore[arg-type]
    await proxy.update(created.id, {"name": "Alice"}, expected_version=3)
    assert len(emitted) == 1
    with pytest.raises(StaleRecordError):
        await proxy.update(created.id, {"name": "Carol"}, expected_version=3)
    assert len(emitted) == 1
