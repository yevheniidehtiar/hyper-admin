"""``enqueue_in_session`` on a real Postgres + pgtask: the task shares the session's transaction."""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Any

import psycopg
import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, create_async_engine

from hyperadmin_tasks import enqueue_in_session
from hyperadmin_tasks.backend import TasksBackendError

pytest.importorskip("pgtask")

pytestmark = [pytest.mark.anyio, pytest.mark.pgtask]


def _engine_url(dsn: str, driver: str) -> str:
    return dsn.replace("postgresql://", f"postgresql+{driver}://", 1)


@pytest.fixture
async def engine(pgtask_database: Any) -> AsyncIterator[AsyncEngine]:
    """A psycopg engine on the pgtask database, with an ``orders`` business table."""
    with psycopg.connect(pgtask_database.owner_dsn, autocommit=True) as conn:
        conn.execute("CREATE TABLE orders (id serial PRIMARY KEY, note text NOT NULL)")
    engine = create_async_engine(_engine_url(pgtask_database.owner_dsn, "psycopg"))
    yield engine
    await engine.dispose()


def _request() -> Any:
    from pgtask import EnqueueRequest

    return EnqueueRequest("app.invoice", {"order": 1}, queue_name="default")


def _counts(owner_dsn: str, task_id: str) -> tuple[int, int]:
    """Return ``(orders, tasks with task_id)`` as committed, read on a fresh connection."""
    with psycopg.connect(owner_dsn) as conn:
        orders = conn.execute("SELECT count(*) FROM orders").fetchone()
        tasks = conn.execute(
            "SELECT count(*) FROM pgtask.tasks WHERE id = %s::uuid", (task_id,)
        ).fetchone()
    assert orders is not None
    assert tasks is not None
    return orders[0], tasks[0]


async def test_enqueue_commits_with_the_business_write(
    engine: AsyncEngine, pgtask_database: Any
) -> None:
    """
    Scenario: commit
      Given an AsyncSession on psycopg
      When  a row is inserted, enqueue_in_session is called, and the session commits
      Then  both the row and the task exist
    """
    async with AsyncSession(engine) as session:
        await session.execute(text("INSERT INTO orders (note) VALUES ('paid')"))
        task_id = await enqueue_in_session(session, _request())
        await session.commit()

    assert _counts(pgtask_database.owner_dsn, task_id) == (1, 1)


async def test_enqueue_rolls_back_with_the_business_write(
    engine: AsyncEngine, pgtask_database: Any
) -> None:
    """
    Scenario: rollback
      Given an AsyncSession on psycopg
      When  a row is inserted, enqueue_in_session is called, and the transaction rolls back
      Then  neither the row nor the task exists
    """
    async with AsyncSession(engine) as session:
        await session.execute(text("INSERT INTO orders (note) VALUES ('paid')"))
        task_id = await enqueue_in_session(session, _request())
        await session.rollback()

    assert _counts(pgtask_database.owner_dsn, task_id) == (0, 0)


async def test_enqueue_rejects_an_asyncpg_engine(pgtask_database: Any) -> None:
    """
    Scenario: asyncpg
      Given an engine using asyncpg
      When  enqueue_in_session is called
      Then  TasksBackendError says the psycopg driver is required
    """
    engine = create_async_engine(_engine_url(pgtask_database.owner_dsn, "asyncpg"))
    try:
        async with AsyncSession(engine) as session:
            with pytest.raises(TasksBackendError, match="needs the psycopg driver"):
                await enqueue_in_session(session, _request())
    finally:
        await engine.dispose()
