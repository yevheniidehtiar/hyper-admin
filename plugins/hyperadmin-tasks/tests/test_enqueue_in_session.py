"""Unit tests for ``enqueue_in_session``: driver checks and the hand-off to pgtask."""

from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

from hyperadmin_tasks import enqueue_in_session
from hyperadmin_tasks.backend import TasksBackendError
from hyperadmin_tasks.selection import PGTASK_MODULE

REQUEST = object()


class _FakeConnection:
    """The slice of SQLAlchemy's ``AsyncConnection`` that ``enqueue_in_session`` touches."""

    def __init__(self, driver: str) -> None:
        self.dialect = SimpleNamespace(name="postgresql", driver=driver)
        self.driver_connection = object()

    async def get_raw_connection(self) -> SimpleNamespace:
        return SimpleNamespace(driver_connection=self.driver_connection)


class _FakeSession:
    def __init__(self, driver: str) -> None:
        self.bound = _FakeConnection(driver)

    async def connection(self) -> _FakeConnection:
        return self.bound


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


@pytest.fixture
def enqueued(monkeypatch: pytest.MonkeyPatch) -> list[tuple[Any, Any]]:
    """Install a fake ``pgtask`` whose ``Client.enqueue_on`` records its calls."""
    calls: list[tuple[Any, Any]] = []

    async def enqueue_on(connection: Any, request: Any) -> tuple[str, bool]:
        calls.append((connection, request))
        return "task-1", True

    module = SimpleNamespace(Client=SimpleNamespace(enqueue_on=enqueue_on))
    monkeypatch.setitem(sys.modules, "pgtask", module)
    return calls


@pytest.mark.anyio
async def test_enqueue_uses_the_sessions_psycopg_connection(enqueued: list[Any]) -> None:
    """
    Scenario: the task is written on the session's own connection
      Given a session whose engine uses the psycopg driver
      When  enqueue_in_session is called
      Then  pgtask enqueues on the session's psycopg connection
      And   the task id is returned
    """
    session = _FakeSession("psycopg")

    task_id = await enqueue_in_session(session, REQUEST)  # type: ignore[arg-type]

    assert task_id == "task-1"
    assert enqueued == [(session.bound.driver_connection, REQUEST)]


@pytest.mark.anyio
async def test_enqueue_rejects_asyncpg(enqueued: list[Any]) -> None:
    """
    Scenario: asyncpg
      Given an engine using asyncpg
      When  enqueue_in_session is called
      Then  TasksBackendError says the psycopg driver is required
    """
    with pytest.raises(TasksBackendError, match=r"needs the psycopg driver.*postgresql\+asyncpg"):
        await enqueue_in_session(_FakeSession("asyncpg"), REQUEST)  # type: ignore[arg-type]

    assert enqueued == []


@pytest.mark.anyio
async def test_enqueue_rejects_a_non_postgres_session(tmp_path: Path) -> None:
    """
    Scenario: a SQLite session cannot enqueue
      Given a real AsyncSession on sqlite+aiosqlite
      When  enqueue_in_session is called
      Then  TasksBackendError names the session's dialect and driver
    """
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'app.db'}")
    try:
        async with AsyncSession(engine) as session:
            with pytest.raises(TasksBackendError, match=r"sqlite\+aiosqlite"):
                await enqueue_in_session(session, REQUEST)
    finally:
        await engine.dispose()


@pytest.mark.anyio
@pytest.mark.parametrize("missing", ["pgtask", PGTASK_MODULE])
async def test_enqueue_needs_the_pgtask_extra(
    monkeypatch: pytest.MonkeyPatch, missing: str
) -> None:
    """
    Scenario: enqueue_in_session without the [pgtask] extra
      Given pgtask (or the pgtask adapter) cannot be imported
      When  enqueue_in_session is called on a psycopg session
      Then  TasksBackendError says to install hyperadmin-tasks[pgtask]
    """
    monkeypatch.setitem(sys.modules, missing, None)

    with pytest.raises(TasksBackendError, match=r"install hyperadmin-tasks\[pgtask\]"):
        await enqueue_in_session(_FakeSession("psycopg"), REQUEST)  # type: ignore[arg-type]
