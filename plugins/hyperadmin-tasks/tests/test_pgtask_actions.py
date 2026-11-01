"""PgTaskBackend actions against scripted fake connections (no database needed)."""

from __future__ import annotations

from typing import Any

import psycopg
import pytest
from test_pgtask_backend import TASK_ID, _FakeConnection

from hyperadmin_tasks.backend import Capability, TasksBackendError
from hyperadmin_tasks.backends import pgtask as pgtask_module
from hyperadmin_tasks.backends.pgtask import ACTION_CAPABILITIES, PgTaskBackend, create_backend
from hyperadmin_tasks.settings import TasksSettings

pytestmark = pytest.mark.anyio

SCHEDULE_ID = "0b8f2c1e-52de-4d0e-8a43-6a1f9c3b7e55"


def _with_admin(
    admin: _FakeConnection, observer: _FakeConnection | None = None
) -> tuple[PgTaskBackend, _FakeConnection]:
    observer = observer or _FakeConnection()

    async def observe() -> _FakeConnection:
        return observer

    async def administer() -> _FakeConnection:
        return admin

    backend = PgTaskBackend("observer-dsn", connector=observe, admin_connector=administer)
    return backend, observer


def _changed(value: bool) -> _FakeConnection:
    return _FakeConnection({"pgtask.admin_": [{"changed": value}]})


async def test_capabilities_cover_actions_but_not_queue_pause() -> None:
    """
    Scenario: administrator DSN unlocks the audited actions only
      Given a PgTaskBackend with an administrator connector
      When  its capabilities are inspected
      Then  retry, cancel and schedule pause are present and queue pause is not
    """
    backend, _ = _with_admin(_changed(True))
    assert backend.capabilities == {
        Capability.WORKERS,
        Capability.SCHEDULES,
        Capability.RETRY,
        Capability.CANCEL,
        Capability.PAUSE_SCHEDULE,
    }
    assert backend.capabilities >= ACTION_CAPABILITIES
    assert Capability.PAUSE_QUEUE not in backend.capabilities


async def test_retry_task_passes_the_actor_to_admin_retry_task() -> None:
    """
    Scenario: retry failed task
      Given a failed task
      When  retry_task(id, actor="alice")
      Then  admin_retry_task runs on the administrator connection with the task id and "alice"
      And   the observer connection is not used for the write
    """
    admin = _changed(True)
    backend, observer = _with_admin(admin)
    await backend.retry_task(TASK_ID, actor="alice")
    query, params = admin.calls[0]
    assert "pgtask.admin_retry_task(%s, %s)" in query
    assert params is not None
    assert str(params[0]) == TASK_ID
    assert params[1] == "alice"
    assert observer.calls == []


async def test_cancel_task_passes_the_actor_to_admin_cancel_task() -> None:
    """
    Scenario: cancel a task
      Given a pending task
      When  cancel_task(id, actor="alice")
      Then  admin_cancel_task runs with the task id and "alice"
    """
    admin = _changed(True)
    backend, _ = _with_admin(admin)
    await backend.cancel_task(TASK_ID, actor="alice")
    query, params = admin.calls[0]
    assert "pgtask.admin_cancel_task(%s, %s)" in query
    assert params is not None
    assert (str(params[0]), params[1]) == (TASK_ID, "alice")


@pytest.mark.parametrize("paused", [True, False])
async def test_set_schedule_paused_passes_flag_and_actor(paused: bool) -> None:
    """
    Scenario: pause and resume a schedule
      Given a schedule
      When  set_schedule_paused(id, paused, actor="alice")
      Then  admin_set_schedule_paused runs with the id, the flag and "alice"
    """
    admin = _changed(True)
    backend, _ = _with_admin(admin)
    await backend.set_schedule_paused(SCHEDULE_ID, paused, actor="alice")
    query, params = admin.calls[0]
    assert "pgtask.admin_set_schedule_paused(%s, %s, %s)" in query
    assert params is not None
    assert (str(params[0]), params[1], params[2]) == (SCHEDULE_ID, paused, "alice")


async def test_noop_actions_raise_a_descriptive_error() -> None:
    """
    Scenario: an action that changes nothing is reported
      Given admin functions that return false (unknown or wrong-state target)
      When  retry, cancel and schedule pause are called
      Then  each raises TasksBackendError naming the target
    """
    backend, _ = _with_admin(_changed(False))
    with pytest.raises(TasksBackendError, match=f"task '{TASK_ID}' cannot be retried"):
        await backend.retry_task(TASK_ID, actor="a")
    with pytest.raises(TasksBackendError, match=f"task '{TASK_ID}' cannot be cancelled"):
        await backend.cancel_task(TASK_ID, actor="a")
    with pytest.raises(TasksBackendError, match=f"unknown schedule '{SCHEDULE_ID}'"):
        await backend.set_schedule_paused(SCHEDULE_ID, True, actor="a")


async def test_malformed_ids_are_rejected_without_querying() -> None:
    """
    Scenario: malformed ids never reach the database
      Given an administrator connection
      When  actions receive ids that are not UUIDs
      Then  TasksBackendError says unknown task / schedule and nothing is executed
    """
    admin = _changed(True)
    backend, _ = _with_admin(admin)
    with pytest.raises(TasksBackendError, match="unknown task 'nope'"):
        await backend.retry_task("nope", actor="a")
    with pytest.raises(TasksBackendError, match="unknown task 'nope'"):
        await backend.cancel_task("nope", actor="a")
    with pytest.raises(TasksBackendError, match="unknown schedule 'nope'"):
        await backend.set_schedule_paused("nope", True, actor="a")
    assert admin.calls == []


async def test_queue_pause_stays_unsupported_with_an_admin_connection() -> None:
    """
    Scenario: queue pause is refused because pgtask cannot audit it
      Given a backend with administrator access
      When  set_queue_paused is called
      Then  TasksBackendError names the pause_queue capability
    """
    admin = _changed(True)
    backend, _ = _with_admin(admin)
    with pytest.raises(TasksBackendError, match="pause_queue"):
        await backend.set_queue_paused("default", True, actor="a")
    assert admin.calls == []


async def test_database_errors_are_wrapped() -> None:
    """
    Scenario: pgtask rejects the call
      Given an administrator connection that fails with an invalid actor
      When  retry_task is called with an empty actor
      Then  TasksBackendError reports the admin action failure with the driver error chained
    """
    admin = _changed(True)
    admin.error = psycopg.errors.InvalidParameterValue("invalid administrator actor")
    backend, _ = _with_admin(admin)
    with pytest.raises(TasksBackendError, match="admin action failed") as info:
        await backend.retry_task(TASK_ID, actor="")
    assert isinstance(info.value.__cause__, psycopg.errors.InvalidParameterValue)


async def test_startup_opens_the_admin_connection_and_shutdown_closes_both() -> None:
    """
    Scenario: connection lifecycle with administrator access
      Given a backend with observer and administrator connectors
      When  it starts, acts, is shut down twice
      Then  both connections were opened once, are reused and end up closed
    """
    admin = _changed(True)
    backend, observer = _with_admin(admin)
    await backend.startup()
    await backend.retry_task(TASK_ID, actor="alice")
    await backend.shutdown()
    await backend.shutdown()
    assert observer.closed is True
    assert admin.closed is True
    assert len(admin.calls) == 1


async def test_closed_admin_connection_is_reopened_and_unopened_one_is_skipped() -> None:
    """
    Scenario: a dropped administrator connection is replaced
      Given a started backend whose administrator connection was closed
      When  an action runs
      Then  a new administrator connection is opened for it
    """
    opened: list[_FakeConnection] = []

    async def administer() -> _FakeConnection:
        opened.append(_changed(True))
        return opened[-1]

    backend = PgTaskBackend(
        "observer-dsn", connector=lambda: _async(_FakeConnection()), admin_connector=administer
    )
    await backend.startup()
    opened[0].closed = True
    await backend.cancel_task(TASK_ID, actor="a")
    assert len(opened) == 2
    opened[1].closed = True
    await backend.shutdown()


async def test_admin_connect_failure_fails_startup() -> None:
    """
    Scenario: an unreachable administrator role fails fast
      Given an administrator connector that cannot connect
      When  startup is called
      Then  TasksBackendError says the administrator connection failed
      And   the observer connection is closed, not leaked
    """

    async def administer() -> _FakeConnection:
        raise psycopg.OperationalError("refused")

    observer = _FakeConnection()
    backend = PgTaskBackend(
        "observer-dsn", connector=lambda: _async(observer), admin_connector=administer
    )
    with pytest.raises(TasksBackendError, match="as administrator"):
        await backend.startup()
    assert observer.closed is True


async def test_admin_dsn_uses_the_default_autocommit_connector(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """
    Scenario: the administrator DSN is opened in autocommit mode
      Given a backend built with an observer DSN and an administrator DSN
      When  it starts
      Then  psycopg connects to both DSNs with autocommit and dict rows
    """
    seen: list[dict[str, Any]] = []

    async def fake_connect(dsn: str, **kwargs: Any) -> _FakeConnection:
        seen.append({"dsn": dsn, **kwargs})
        return _FakeConnection()

    monkeypatch.setattr(psycopg.AsyncConnection, "connect", fake_connect)
    backend = PgTaskBackend("postgresql://o/db", admin_dsn="postgresql://a/db")
    await backend.startup()
    assert [call["dsn"] for call in seen] == ["postgresql://o/db", "postgresql://a/db"]
    assert all(call["autocommit"] is True for call in seen)
    assert all(call["row_factory"] is pgtask_module.dict_row for call in seen)


def test_create_backend_enables_actions_only_with_a_dsn() -> None:
    """
    Scenario: settings decide whether actions are offered
      Given settings with and without the administrator DSN
      When  create_backend runs
      Then  actions are available only when dsn is set
    """
    with_admin = create_backend(TasksSettings(backend="pgtask", dsn="a", observer_dsn="o"))
    read_only = create_backend(TasksSettings(backend="pgtask", observer_dsn="o"))
    assert Capability.RETRY in with_admin.capabilities
    assert Capability.RETRY not in read_only.capabilities


async def _async(value: _FakeConnection) -> _FakeConnection:
    return value
