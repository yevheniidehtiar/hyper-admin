"""Unit tests for the dashboard layout table and ``LayoutStore`` (#456).

The first eight tests map 1:1 to the scenarios of
``.meta/epics/epicdashboard-dashboard-builder-with-widgets/stories/featdashboard-create-dashboard-data-models.md``.
"""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest
from sqlalchemy import func, inspect, select
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.sql.dml import Update
from sqlmodel import SQLModel

from hyperadmin_reports.dashboard import (
    LayoutStore,
    LayoutUnavailableError,
    create_layout_table,
    dashboard_metadata,
)
from hyperadmin_reports.dashboard.layout import LAYOUT_TABLE_NAME, layout_table

pytestmark = pytest.mark.anyio


@pytest.fixture
async def engine(tmp_path: Path) -> AsyncEngine:
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'layout.db'}")
    await create_layout_table(engine)
    return engine


@pytest.fixture
def store(engine: AsyncEngine) -> LayoutStore:
    return LayoutStore(engine)


async def _rows(engine: AsyncEngine) -> list[Any]:
    async with AsyncSession(engine) as session:
        return list((await session.execute(select(layout_table))).all())


async def test_saved_order_is_loaded_back_for_the_same_user(store: LayoutStore) -> None:
    """
    Scenario: saved order is loaded back for the same user
      Given an empty hyperadmin_reports_dashboard_layout table
      And   LayoutStore.save("alice", ["chart-a", "stat-b"]) was called
      When  LayoutStore.load("alice") is called
      Then  the result is ["chart-a", "stat-b"]
    """
    await store.save("alice", ["chart-a", "stat-b"])

    assert await store.load("alice") == ["chart-a", "stat-b"]


async def test_a_user_without_a_saved_order_gets_none(store: LayoutStore) -> None:
    """
    Scenario: a user without a saved order gets None
      Given alice saved ["chart-a", "stat-b"]
      When  LayoutStore.load("bob") is called
      Then  the result is None
    """
    await store.save("alice", ["chart-a", "stat-b"])

    assert await store.load("bob") is None


async def test_saving_again_replaces_the_order(store: LayoutStore, engine: AsyncEngine) -> None:
    """
    Scenario: saving again replaces the order
      Given alice saved ["chart-a", "stat-b"]
      When  LayoutStore.save("alice", ["stat-b", "chart-a"]) is called
      Then  load("alice") returns ["stat-b", "chart-a"]
      And   the table holds one row for alice
    """
    await store.save("alice", ["chart-a", "stat-b"])

    await store.save("alice", ["stat-b", "chart-a"])

    assert await store.load("alice") == ["stat-b", "chart-a"]
    (row,) = await _rows(engine)
    assert row.user_key == "alice"
    assert row.dashboard == "home"
    assert row.updated_at.tzinfo is None


async def test_reset_deletes_the_users_row(store: LayoutStore) -> None:
    """
    Scenario: reset deletes the user's row
      Given alice saved ["chart-a", "stat-b"]
      When  LayoutStore.reset("alice") is called
      Then  the result is True
      And   load("alice") returns None
    """
    await store.save("alice", ["chart-a", "stat-b"])

    assert await store.reset("alice") is True
    assert await store.load("alice") is None


async def test_reset_without_a_saved_row_is_a_no_op(store: LayoutStore) -> None:
    """
    Scenario: reset without a saved row is a no-op
      Given bob has no saved order
      When  LayoutStore.reset("bob") is called
      Then  the result is False
    """
    assert await store.reset("bob") is False


async def test_a_concurrent_first_save_becomes_an_update(engine: AsyncEngine) -> None:
    """
    Scenario: a concurrent first save becomes an update
      Given alice has no row and another session inserts alice's row between the store's
            check and its insert
      When  LayoutStore.save("alice", ["stat-b"]) commits
      Then  no exception is raised
      And   load("alice") returns ["stat-b"]
    """
    # The other session's row is already there, but the store's first UPDATE reports
    # no row, as it would have had it run a moment earlier.
    await LayoutStore(engine).save("alice", ["chart-a"])

    class RacingSession(AsyncSession):
        raced = False

        async def execute(self, statement: Any, *args: Any, **kwargs: Any) -> Any:
            if isinstance(statement, Update) and not RacingSession.raced:
                RacingSession.raced = True
                return SimpleNamespace(rowcount=0)
            return await super().execute(statement, *args, **kwargs)

    store = LayoutStore(session_factory=async_sessionmaker(engine, class_=RacingSession))

    await store.save("alice", ["stat-b"])

    assert RacingSession.raced
    assert await store.load("alice") == ["stat-b"]
    assert len(await _rows(engine)) == 1


async def test_a_missing_table_raises_layout_unavailable_error(tmp_path: Path) -> None:
    """
    Scenario: a missing table raises LayoutUnavailableError
      Given a database without the layout table
      When  LayoutStore.load("alice") is called
      Then  LayoutUnavailableError is raised
    """
    store = LayoutStore(create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'empty.db'}"))

    with pytest.raises(LayoutUnavailableError, match=LAYOUT_TABLE_NAME):
        await store.load("alice")
    with pytest.raises(LayoutUnavailableError):
        await store.save("alice", ["stat-b"])
    with pytest.raises(LayoutUnavailableError):
        await store.reset("alice")


def test_the_layout_table_is_not_part_of_sqlmodel_metadata() -> None:
    """
    Scenario: the layout table is not part of SQLModel.metadata
      Given hyperadmin_reports.dashboard is imported
      When  SQLModel.metadata.tables is inspected
      Then  it has no hyperadmin_reports_dashboard_layout table
      And   dashboard_metadata().tables has it
    """
    assert LAYOUT_TABLE_NAME not in SQLModel.metadata.tables
    assert list(dashboard_metadata().tables) == [LAYOUT_TABLE_NAME]


async def test_layouts_are_kept_per_dashboard_and_user_keys_are_stored_as_text(
    store: LayoutStore, engine: AsyncEngine
) -> None:
    """
    Scenario: a non-string user key and a second dashboard get their own rows
      Given user 7 saved an order for "home" and another for "sales"
      When  both are loaded
      Then  each dashboard returns its own order
      And   the rows are stored under the user key "7"
    """
    await store.save(7, ["a", "b"])
    await store.save(7, ["b", "a"], dashboard="sales")

    assert await store.load("7") == ["a", "b"]
    assert await store.load(7, dashboard="sales") == ["b", "a"]
    assert {row.user_key for row in await _rows(engine)} == {"7"}


async def test_create_layout_table_accepts_a_connection_and_creates_only_its_table(
    tmp_path: Path,
) -> None:
    """
    Scenario: create_layout_table on an open connection creates only the layout table
      Given an empty database and an open async connection
      When  create_layout_table(connection) is awaited twice
      Then  the database holds exactly the layout table with its unique constraint
    """
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'conn.db'}")

    async with engine.begin() as connection:
        await create_layout_table(connection)
        await create_layout_table(connection)
        names = await connection.run_sync(lambda sync: inspect(sync).get_table_names())
        uniques = await connection.run_sync(
            lambda sync: inspect(sync).get_unique_constraints(LAYOUT_TABLE_NAME)
        )
        count = (await connection.execute(select(func.count()).select_from(layout_table))).scalar()

    assert names == [LAYOUT_TABLE_NAME]
    assert [u["name"] for u in uniques] == ["uq_hyperadmin_reports_dashboard_layout"]
    assert count == 0


def test_layout_store_needs_an_engine_or_a_session_factory() -> None:
    """
    Scenario: a store without a database is refused
      When  LayoutStore() is constructed with neither engine nor session_factory
      Then  ValueError is raised
    """
    with pytest.raises(ValueError, match="LayoutStore requires either engine="):
        LayoutStore()
