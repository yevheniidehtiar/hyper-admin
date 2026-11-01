"""Startup probe of PgTaskBackend against a scripted fake connection (no database needed)."""

from __future__ import annotations

from typing import Any

import psycopg
import pytest
from test_pgtask_backend import _FakeConnection, healthy_probe_script

from hyperadmin_tasks.backend import TasksBackendError
from hyperadmin_tasks.backends import _pgtask_columns as columns
from hyperadmin_tasks.backends.pgtask import PgTaskBackend

pytestmark = pytest.mark.anyio


def _backend(connection: _FakeConnection) -> PgTaskBackend:
    async def connector() -> _FakeConnection:
        return connection

    return PgTaskBackend("postgresql://observer@localhost/db", connector=connector)


class _RaisingConnection(_FakeConnection):
    """Raises ``error`` for queries containing ``fragment``; answers the rest normally."""

    def __init__(self, fragment: str, error: Exception) -> None:
        super().__init__()
        self.fragment = fragment
        self.fault = error

    async def execute(self, query: str, params: Any = None) -> Any:
        if self.fragment in query:
            raise self.fault
        return await super().execute(query, params)


async def test_probe_passes_for_a_compatible_database() -> None:
    """
    Scenario: a compatible database starts
      Given storage_protocol_range() overlaps the supported range and all columns exist
      When  backend startup() runs
      Then  it succeeds and the connection stays open for queries
    """
    connection = _FakeConnection()
    backend = _backend(connection)
    await backend.startup()
    assert connection.closed is False
    assert [call[0] for call in connection.calls] == [
        columns.PROTOCOL_RANGE_SQL,
        columns.VIEW_COLUMNS_SQL,
    ]
    assert connection.calls[1][1] == [list(columns.REQUIRED_COLUMNS)]


@pytest.mark.parametrize(("minimum", "maximum"), [(1, 1), (2, 2), (2, 9), (0, 1)])
async def test_probe_accepts_any_overlapping_protocol_range(minimum: int, maximum: int) -> None:
    """
    Scenario: overlapping ranges are compatible
      Given a database range that touches the supported range
      When  backend startup() runs
      Then  it succeeds
    """
    connection = _FakeConnection(
        {"storage_protocol_range": [{"minimum": minimum, "maximum": maximum}]}
    )
    await _backend(connection).startup()


@pytest.mark.parametrize(("minimum", "maximum"), [(3, 4), (7, 7)])
async def test_probe_rejects_a_protocol_out_of_range(minimum: int, maximum: int) -> None:
    """
    Scenario: protocol out of range
      Given storage_protocol_range() excludes the supported version
      When  backend startup() runs
      Then  TasksBackendError names both versions and the supported pgtask range
      And   the connection is closed
    """
    connection = _FakeConnection(
        {"storage_protocol_range": [{"minimum": minimum, "maximum": maximum}]}
    )
    with pytest.raises(TasksBackendError) as info:
        await _backend(connection).startup()
    message = str(info.value)
    assert f"{minimum}..{maximum}" in message
    assert "1..2" in message
    assert columns.PGTASK_REQUIREMENT in message
    assert connection.closed is True


@pytest.mark.parametrize(
    "error",
    [psycopg.errors.InvalidSchemaName("no schema"), psycopg.errors.UndefinedFunction("no fn")],
)
async def test_probe_tells_the_user_to_migrate_an_empty_database(error: Exception) -> None:
    """
    Scenario: schema not migrated
      Given an empty database
      When  backend startup() runs
      Then  TasksBackendError tells the user to run `pgtask migrate`
    """
    connection = _RaisingConnection("storage_protocol_range", error)
    with pytest.raises(TasksBackendError, match="pgtask migrate") as info:
        await _backend(connection).startup()
    assert info.value.__cause__ is error
    assert connection.closed is True


async def test_probe_wraps_other_protocol_query_failures() -> None:
    """
    Scenario: the protocol query fails for another reason
      Given the observer role cannot call storage_protocol_range()
      When  backend startup() runs
      Then  TasksBackendError reports the probe failure with the driver error chained
    """
    error = psycopg.errors.InsufficientPrivilege("permission denied")
    connection = _RaisingConnection("storage_protocol_range", error)
    with pytest.raises(TasksBackendError, match="probe failed"):
        await _backend(connection).startup()
    assert connection.closed is True


async def test_probe_lists_missing_columns() -> None:
    """
    Scenario: column drift
      Given task_view lost parent_task_id and schedule_view lost paused_at
      When  backend startup() runs
      Then  TasksBackendError lists the missing columns per view and the supported range
    """
    rows = [
        row
        for row in healthy_probe_script()["information_schema.columns"]
        if (row["table_name"], row["column_name"])
        not in {("task_view", "parent_task_id"), ("schedule_view", "paused_at")}
    ]
    connection = _FakeConnection({"information_schema.columns": rows})
    with pytest.raises(TasksBackendError) as info:
        await _backend(connection).startup()
    message = str(info.value)
    assert "pgtask.task_view: parent_task_id" in message
    assert "pgtask.schedule_view: paused_at" in message
    assert columns.PGTASK_REQUIREMENT in message
    assert connection.closed is True


async def test_probe_reports_a_missing_view_as_all_its_columns() -> None:
    """
    Scenario: a view disappeared
      Given worker_capability_view is not visible
      When  backend startup() runs
      Then  both of its columns are reported missing
    """
    rows = [
        row
        for row in healthy_probe_script()["information_schema.columns"]
        if row["table_name"] != "worker_capability_view"
    ]
    connection = _FakeConnection({"information_schema.columns": rows})
    with pytest.raises(TasksBackendError, match="worker_capability_view: task_name, worker_id"):
        await _backend(connection).startup()


async def test_probe_wraps_column_query_failures() -> None:
    """
    Scenario: the column query fails
      Given information_schema cannot be read
      When  backend startup() runs
      Then  TasksBackendError reports the probe failure
    """
    connection = _RaisingConnection("information_schema", psycopg.errors.InternalError("boom"))
    with pytest.raises(TasksBackendError, match="probe failed"):
        await _backend(connection).startup()
    assert connection.closed is True


async def test_failed_probe_allows_a_clean_retry() -> None:
    """
    Scenario: startup can be retried after a failed probe
      Given a failed startup that closed its connection
      When  the database is fixed and startup runs again
      Then  a fresh connection is opened and the probe passes
    """
    connections = [
        _FakeConnection({"storage_protocol_range": [{"minimum": 5, "maximum": 5}]}),
        _FakeConnection(),
    ]

    async def connector() -> _FakeConnection:
        return connections.pop(0)

    backend = PgTaskBackend("dsn", connector=connector)
    with pytest.raises(TasksBackendError):
        await backend.startup()
    await backend.startup()
    assert connections == []


def test_required_columns_are_all_read_by_the_adapter_sql() -> None:
    """
    Scenario: the probe checks what the adapter reads
      Given the SQL constants of the adapter
      When  each required column is searched in the SQL that targets its view
      Then  every required column appears there (or is the parent_task_id source column)
    """
    sql_by_view = {
        "queue_overview": columns.QUEUES_SQL,
        "task_view": columns.TASK_COLUMNS + columns.QUEUE_TASK_COUNTS_SQL,
        "attempt_view": columns.ATTEMPTS_SQL,
        "worker_view": columns.WORKERS_SQL,
        "worker_capability_view": columns.WORKER_TASK_NAMES_SQL,
        "schedule_view": columns.SCHEDULES_SQL,
    }
    assert set(sql_by_view) == set(columns.REQUIRED_COLUMNS)
    for view, required in columns.REQUIRED_COLUMNS.items():
        for column in required:
            assert column in sql_by_view[view], (view, column)
