"""PgTaskBackend behaviour against a scripted fake connection (no database needed)."""

from __future__ import annotations

import logging
import uuid
from collections.abc import Sequence
from datetime import UTC, datetime, timedelta
from typing import Any

import psycopg
import pytest

from hyperadmin_tasks.backend import (
    Capability,
    TaskBackend,
    TaskFilter,
    TasksBackendError,
    TaskState,
)
from hyperadmin_tasks.backends import pgtask as pgtask_module
from hyperadmin_tasks.backends.pgtask import PgTaskBackend, create_backend
from hyperadmin_tasks.selection import select_backend
from hyperadmin_tasks.settings import TasksSettings

pytestmark = pytest.mark.anyio

NOW = datetime(2026, 1, 1, 12, 0, tzinfo=UTC)
TASK_ID = "4b1c0f6e-3a7d-4e0a-9a52-0d5a2f1d7c11"


class _Cursor:
    def __init__(self, rows: list[dict[str, Any]]) -> None:
        self._rows = rows

    async def fetchall(self) -> list[dict[str, Any]]:
        return self._rows


class _FakeConnection:
    """Answers each query with the rows scripted for the first matching SQL fragment."""

    def __init__(self, script: dict[str, list[dict[str, Any]]] | None = None) -> None:
        self.script = script or {}
        self.calls: list[tuple[str, Sequence[Any] | None]] = []
        self.closed = False
        self.error: Exception | None = None

    async def execute(self, query: str, params: Sequence[Any] | None = None) -> _Cursor:
        self.calls.append((query, params))
        if self.error is not None:
            raise self.error
        for fragment, rows in self.script.items():
            if fragment in query:
                return _Cursor(rows)
        return _Cursor([])

    async def close(self) -> None:
        self.closed = True


def _backend(connection: _FakeConnection) -> PgTaskBackend:
    async def connector() -> _FakeConnection:
        return connection

    return PgTaskBackend("postgresql://observer@localhost/db", connector=connector)


def _task_row(task_id: str = TASK_ID, state: str = "failed") -> dict[str, Any]:
    return {
        "id": task_id,
        "queue_name": "reports",
        "task_name": "app.report",
        "state": state,
        "priority": 0,
        "attempt": 3,
        "max_attempts": 3,
        "created_at": NOW,
        "run_at": NOW,
        "completed_at": NOW,
        "payload": None,
        "result": None,
        "error": {"message": "boom"},
        "parent_id": None,
    }


async def test_backend_satisfies_the_port_and_advertises_read_capabilities() -> None:
    """
    Scenario: the adapter is a read-only TaskBackend
      Given a PgTaskBackend
      When  it is checked against the TaskBackend protocol
      Then  it satisfies it and supports only workers and schedules
    """
    backend = _backend(_FakeConnection())
    assert isinstance(backend, TaskBackend)
    assert backend.capabilities == {Capability.WORKERS, Capability.SCHEDULES}


async def test_list_queues_issues_overview_and_aggregate_queries() -> None:
    """
    Scenario: queue overview
      Given queue "reports" with ready, running, failed and scheduled tasks
      When  list_queues is called
      Then  QueueStats for "reports" has the matching counts
    """
    connection = _FakeConnection(
        {
            "FROM pgtask.queue_overview": [
                {"name": "reports", "paused_at": None, "running_count": 1, "ready_count": 2}
            ],
            "GROUP BY queue_name": [
                {
                    "queue_name": "reports",
                    "failed_count": 3,
                    "succeeded_count": 4,
                    "scheduled_count": 5,
                    "oldest_ready": timedelta(seconds=9),
                }
            ],
        }
    )
    backend = _backend(connection)
    (stats,) = await backend.list_queues()
    assert (stats.name, stats.ready, stats.running, stats.scheduled, stats.failed) == (
        "reports",
        2,
        1,
        5,
        3,
    )
    assert stats.succeeded_recent == 4
    assert stats.oldest_ready_age == timedelta(seconds=9)


async def test_list_tasks_filters_paginates_and_reports_total() -> None:
    """
    Scenario: filter and paginate
      Given 120 tasks on two queues
      When  list_tasks(TaskFilter(queue="reports", state=FAILED), page=2, per_page=50) is called
      Then  only failed reports tasks of page 2 are requested and the exact total is reported
    """
    connection = _FakeConnection(
        {"SELECT count(*)": [{"total": 61}], "ORDER BY created_at": [_task_row()]}
    )
    page = await _backend(connection).list_tasks(
        TaskFilter(queue="reports", state=TaskState.FAILED), 2, 50
    )
    assert [t.id for t in page.items] == [TASK_ID]
    assert (page.page, page.per_page, page.total) == (2, 50, 61)
    page_sql, page_params = connection.calls[0]
    assert "queue_name = %s AND state = 'failed'" in page_sql
    assert page_params == ["reports", 50, 50]


@pytest.mark.parametrize(("page", "per_page"), [(0, 5), (1, 0)])
async def test_list_tasks_rejects_invalid_pagination(page: int, per_page: int) -> None:
    """
    Scenario: invalid pagination is rejected before any SQL runs
      Given a backend
      When  list_tasks is called with page or per_page below one
      Then  TasksBackendError is raised and no query is issued
    """
    connection = _FakeConnection()
    with pytest.raises(TasksBackendError):
        await _backend(connection).list_tasks(TaskFilter(), page, per_page)
    assert connection.calls == []


async def test_get_task_returns_task_with_attempts() -> None:
    """
    Scenario: task detail
      Given a failed task with one recorded attempt
      When  get_task is called with its id
      Then  the task and its attempts are returned and both queries bind the id as a UUID
    """
    connection = _FakeConnection(
        {
            "FROM pgtask.task_view": [_task_row()],
            "FROM pgtask.attempt_view": [
                {
                    "attempt": 1,
                    "worker_id": None,
                    "state": "failed",
                    "started_at": NOW,
                    "finished_at": NOW,
                    "error": None,
                }
            ],
        }
    )
    found = await _backend(connection).get_task(TASK_ID)
    assert found is not None
    task, attempts = found
    assert (task.id, task.error) == (TASK_ID, "boom")
    assert [(a.number, a.outcome) for a in attempts] == [(1, "failed")]
    assert [params for _, params in connection.calls] == [[uuid.UUID(TASK_ID)]] * 2


async def test_get_task_unknown_id_returns_none() -> None:
    """
    Scenario: missing task
      Given no task with id X
      When  get_task("X") is called
      Then  None is returned
    """
    assert await _backend(_FakeConnection()).get_task(TASK_ID) is None


async def test_get_task_malformed_id_returns_none_without_querying() -> None:
    """
    Scenario: a non-UUID id cannot exist
      Given a backend
      When  get_task is called with an id that is not a UUID
      Then  None is returned and no query is issued
    """
    connection = _FakeConnection()
    assert await _backend(connection).get_task("task-0001") is None
    assert connection.calls == []


async def test_list_workers_and_schedules() -> None:
    """
    Scenario: workers and schedules are listed
      Given a live worker with a capability and a cron schedule
      When  list_workers and list_schedules are called
      Then  they are mapped to WorkerRecord and ScheduleRecord
    """
    connection = _FakeConnection(
        {
            "FROM pgtask.worker_view": [
                {"id": "w1", "queue_name": "default", "heartbeat_at": NOW, "live": True}
            ],
            "FROM pgtask.worker_capability_view": [{"worker_id": "w1", "task_name": "app.a"}],
            "FROM pgtask.schedule_view": [
                {
                    "id": "s1",
                    "kind": "cron",
                    "cron_expression": "0 3 * * *",
                    "interval_milliseconds": None,
                    "misfire_policy": "skip",
                    "queue_name": "default",
                    "task_name": "app.a",
                    "next_run_at": NOW,
                    "paused_at": None,
                }
            ],
        }
    )
    backend = _backend(connection)
    (worker,) = await backend.list_workers()
    (schedule,) = await backend.list_schedules()
    assert (worker.id, worker.task_names, worker.healthy) == ("w1", ("app.a",), True)
    assert (schedule.id, schedule.cron, schedule.paused) == ("s1", "0 3 * * *", False)


async def test_actions_are_rejected_by_capability_gate() -> None:
    """
    Scenario: the read-side adapter refuses actions
      Given a PgTaskBackend without action capabilities
      When  retry, cancel and both pause actions are called
      Then  each raises TasksBackendError
    """
    backend = _backend(_FakeConnection())
    with pytest.raises(TasksBackendError, match="retry"):
        await backend.retry_task(TASK_ID, actor="a")
    with pytest.raises(TasksBackendError, match="cancel"):
        await backend.cancel_task(TASK_ID, actor="a")
    with pytest.raises(TasksBackendError, match="pause_queue"):
        await backend.set_queue_paused("default", True, actor="a")
    with pytest.raises(TasksBackendError, match="pause_schedule"):
        await backend.set_schedule_paused("s1", True, actor="a")


async def test_startup_connects_once_and_shutdown_closes() -> None:
    """
    Scenario: connection lifecycle
      Given a backend with a connector
      When  it is started, queried and shut down
      Then  one connection is opened, reused and closed, and a second shutdown is harmless
    """
    opened: list[_FakeConnection] = []

    async def connector() -> _FakeConnection:
        opened.append(_FakeConnection())
        return opened[-1]

    backend = PgTaskBackend("dsn", connector=connector)
    await backend.startup()
    await backend.list_workers()
    await backend.shutdown()
    await backend.shutdown()
    assert len(opened) == 1
    assert opened[0].closed is True


async def test_closed_connection_is_reopened_on_next_query() -> None:
    """
    Scenario: a dropped connection is replaced
      Given a started backend whose connection has been closed
      When  a query runs
      Then  a new connection is opened for it
    """
    opened: list[_FakeConnection] = []

    async def connector() -> _FakeConnection:
        opened.append(_FakeConnection())
        return opened[-1]

    backend = PgTaskBackend("dsn", connector=connector)
    await backend.startup()
    opened[0].closed = True
    await backend.list_workers()
    assert len(opened) == 2


async def test_shutdown_skips_an_already_closed_connection() -> None:
    """
    Scenario: shutdown tolerates a dead connection
      Given a started backend whose connection is already closed
      When  shutdown is called
      Then  close is not called again
    """
    connection = _FakeConnection()
    backend = _backend(connection)
    await backend.startup()
    connection.closed = True
    await backend.shutdown()
    assert connection.calls == []


async def test_query_failure_is_wrapped() -> None:
    """
    Scenario: database errors surface as TasksBackendError
      Given a connection whose queries fail
      When  list_workers is called
      Then  TasksBackendError is raised chaining the driver error
    """
    connection = _FakeConnection()
    connection.error = psycopg.errors.UndefinedTable("relation does not exist")
    with pytest.raises(TasksBackendError, match="query failed") as info:
        await _backend(connection).list_workers()
    assert isinstance(info.value.__cause__, psycopg.errors.UndefinedTable)


async def test_connect_failure_is_wrapped() -> None:
    """
    Scenario: an unreachable server fails fast
      Given a connector that cannot reach Postgres
      When  startup is called
      Then  TasksBackendError is raised
    """

    async def connector() -> _FakeConnection:
        raise psycopg.OperationalError("refused")

    with pytest.raises(TasksBackendError, match="cannot connect"):
        await PgTaskBackend("dsn", connector=connector).startup()


async def test_default_connector_opens_an_autocommit_dict_row_connection(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """
    Scenario: the default connector uses the observer DSN
      Given a backend built with only a DSN
      When  it starts
      Then  psycopg connects to that DSN in autocommit mode with dict rows
    """
    seen: dict[str, Any] = {}
    connection = _FakeConnection()

    async def fake_connect(dsn: str, **kwargs: Any) -> _FakeConnection:
        seen.update(dsn=dsn, **kwargs)
        return connection

    monkeypatch.setattr(psycopg.AsyncConnection, "connect", fake_connect)
    backend = PgTaskBackend("postgresql://observer@host/db")
    await backend.startup()
    assert seen["dsn"] == "postgresql://observer@host/db"
    assert seen["autocommit"] is True
    assert seen["row_factory"] is pgtask_module.dict_row


def test_create_backend_prefers_the_observer_dsn(caplog: pytest.LogCaptureFixture) -> None:
    """
    Scenario: observer DSN is used for reads
      Given settings with both dsn and observer_dsn
      When  create_backend runs
      Then  a PgTaskBackend is built and no warning is logged
    """
    settings = TasksSettings(backend="pgtask", dsn="postgresql://admin/db", observer_dsn="o")
    with caplog.at_level(logging.WARNING):
        backend = create_backend(settings)
    assert isinstance(backend, PgTaskBackend)
    assert caplog.records == []


def test_create_backend_falls_back_to_dsn_with_a_warning(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """
    Scenario: missing observer DSN falls back with a warning
      Given settings with only dsn
      When  create_backend runs
      Then  a backend is built and a warning recommends a read-only observer role
    """
    with caplog.at_level(logging.WARNING):
        backend = create_backend(TasksSettings(backend="pgtask", dsn="postgresql://admin/db"))
    assert isinstance(backend, PgTaskBackend)
    assert "observer" in caplog.text


def test_create_backend_without_any_dsn_fails() -> None:
    """
    Scenario: pgtask needs a DSN
      Given settings without dsn or observer_dsn
      When  create_backend runs
      Then  TasksBackendError names the missing setting
    """
    with pytest.raises(TasksBackendError, match="OBSERVER_DSN"):
        create_backend(TasksSettings(backend="pgtask"))


def test_selection_builds_the_pgtask_backend() -> None:
    """
    Scenario: backend selection finds the adapter
      Given settings naming the pgtask backend
      When  select_backend runs
      Then  a PgTaskBackend is returned
    """
    backend = select_backend(TasksSettings(backend="pgtask", observer_dsn="postgresql://o/db"))
    assert isinstance(backend, PgTaskBackend)
