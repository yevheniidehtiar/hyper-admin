"""PgTaskBackend actions on a real Postgres + pgtask: effects and the audited actor."""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from datetime import UTC, datetime, timedelta
from typing import Any

import psycopg
import pytest

from hyperadmin_tasks.backend import Capability, TasksBackendError, TaskState

pytest.importorskip("pgtask")

pytestmark = [pytest.mark.anyio, pytest.mark.pgtask]

ACTOR = "alice"


def _audit(owner_dsn: str) -> list[tuple[str, str]]:
    """Return ``(actor, action)`` of every audit row, oldest first, read as the owner."""
    with psycopg.connect(owner_dsn) as conn:
        rows = conn.execute(
            "SELECT actor, action FROM pgtask.administrator_audit_view ORDER BY id"
        ).fetchall()
    return [(actor, action) for actor, action in rows]


async def _failed_task(owner_dsn: str) -> str:
    from pgtask import Client, EnqueueRequest, TaskRegistry, Worker

    registry = TaskRegistry("default")

    @registry.task("app.fail", retry_delay=0.05)
    async def _fail(task: Any, payload: dict[str, object]) -> None:
        raise RuntimeError("boom")

    client = await Client.connect(owner_dsn)
    handle = await client.enqueue(
        EnqueueRequest("app.fail", {}, queue_name="default", max_attempts=1)
    )
    worker = Worker(owner_dsn, [registry], poll_interval=0.1, retention_enabled=False)
    runner = asyncio.create_task(worker.run())
    try:
        await handle.result(timeout=30)
    finally:
        worker.shutdown()
        await asyncio.gather(runner, return_exceptions=True)
    return handle.id


async def _pending_task(owner_dsn: str, *, queue: str = "default") -> str:
    from pgtask import Client, EnqueueRequest

    client = await Client.connect(owner_dsn)
    handle = await client.enqueue(
        EnqueueRequest(
            "app.noop", {}, queue_name=queue, run_at=datetime.now(UTC) + timedelta(days=1)
        )
    )
    return handle.id


async def _schedule(owner_dsn: str) -> str:
    import uuid

    schedule_id = uuid.uuid4()
    async with await psycopg.AsyncConnection.connect(owner_dsn, autocommit=True) as conn:
        await conn.execute(
            "SELECT pgtask.put_schedule(%s, 'nightly', 'cron', NULL, '0 3 * * *', 'skip', NULL, "
            "'default', 'app.report', 1, '{}'::jsonb, '{}'::jsonb, 0::smallint, 3, "
            "now() + interval '15 hours')",
            (schedule_id,),
        )
    return str(schedule_id)


@pytest.fixture
async def backend(pgtask_database: Any) -> AsyncIterator[Any]:
    from hyperadmin_tasks.backends.pgtask import PgTaskBackend

    backend = PgTaskBackend(
        pgtask_database.observer_dsn, admin_dsn=pgtask_database.administrator_dsn
    )
    await backend.startup()
    yield backend
    await backend.shutdown()


async def test_retry_failed_task_is_audited_with_the_actor(
    backend: Any, pgtask_database: Any
) -> None:
    """
    Scenario: retry failed task
      Given a failed task
      When  retry_task(id, actor="alice")
      Then  the task is pending and administrator_audit_view has an entry with actor alice
    """
    task_id = await _failed_task(pgtask_database.owner_dsn)
    found = await backend.get_task(task_id)
    assert found is not None
    assert found[0].state is TaskState.FAILED

    await backend.retry_task(task_id, actor=ACTOR)

    found = await backend.get_task(task_id)
    assert found is not None
    assert found[0].state is TaskState.PENDING
    assert _audit(pgtask_database.owner_dsn) == [(ACTOR, "task.retry")]


async def test_cancel_pending_task_is_audited_with_the_actor(
    backend: Any, pgtask_database: Any
) -> None:
    """
    Scenario: cancel a pending task
      Given a pending task
      When  cancel_task(id, actor="alice")
      Then  the task is cancelled and the audit entry names alice
    """
    task_id = await _pending_task(pgtask_database.owner_dsn)

    await backend.cancel_task(task_id, actor=ACTOR)

    found = await backend.get_task(task_id)
    assert found is not None
    assert found[0].state is TaskState.CANCELLED
    assert _audit(pgtask_database.owner_dsn) == [(ACTOR, "task.cancel")]


async def test_schedule_pause_and_resume_are_audited(backend: Any, pgtask_database: Any) -> None:
    """
    Scenario: pause and resume a schedule
      Given an active schedule
      When  set_schedule_paused is called with True then False as alice
      Then  list_schedules reports paused then active and both actions are audited
    """
    schedule_id = await _schedule(pgtask_database.owner_dsn)

    await backend.set_schedule_paused(schedule_id, True, actor=ACTOR)
    assert [s.paused for s in await backend.list_schedules()] == [True]
    await backend.set_schedule_paused(schedule_id, False, actor=ACTOR)
    assert [s.paused for s in await backend.list_schedules()] == [False]

    assert _audit(pgtask_database.owner_dsn) == [
        (ACTOR, "schedule.pause"),
        (ACTOR, "schedule.resume"),
    ]


async def test_actions_that_change_nothing_leave_no_audit_row(
    backend: Any, pgtask_database: Any
) -> None:
    """
    Scenario: retrying a pending task is refused
      Given a pending task
      When  retry_task is called
      Then  TasksBackendError is raised and nothing is audited
    """
    task_id = await _pending_task(pgtask_database.owner_dsn)
    with pytest.raises(TasksBackendError, match="cannot be retried"):
        await backend.retry_task(task_id, actor=ACTOR)
    assert _audit(pgtask_database.owner_dsn) == []


async def test_empty_actor_is_rejected_by_pgtask(backend: Any, pgtask_database: Any) -> None:
    """
    Scenario: an anonymous actor is refused
      Given a failed task
      When  retry_task is called with an empty actor
      Then  TasksBackendError reports pgtask's rejection and the task is unchanged
    """
    task_id = await _failed_task(pgtask_database.owner_dsn)
    with pytest.raises(TasksBackendError, match="invalid administrator actor"):
        await backend.retry_task(task_id, actor="")
    found = await backend.get_task(task_id)
    assert found is not None
    assert found[0].state is TaskState.FAILED


async def test_observer_only_backend_cannot_act(pgtask_database: Any) -> None:
    """
    Scenario: no administrator DSN, no actions
      Given a backend built on the observer DSN only
      When  retry_task is called
      Then  TasksBackendError names the retry capability
    """
    from hyperadmin_tasks.backends.pgtask import PgTaskBackend

    backend = PgTaskBackend(pgtask_database.observer_dsn)
    assert Capability.RETRY not in backend.capabilities
    with pytest.raises(TasksBackendError, match="retry"):
        await backend.retry_task("00000000-0000-0000-0000-000000000000", actor=ACTOR)
