"""Runs the reusable contract suite against ``PgTaskBackend`` on a real Postgres + pgtask.

Skipped as a whole (reason ``Postgres 16+ unavailable``) when no server is reachable; see
``conftest.py``. Named ``test_pgtask_contract`` because the parent directory already holds a
``test_contract.py`` and the test directories are not packages.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Any

import psycopg
import pytest

from hyperadmin_tasks.backend import Capability, TaskBackend, TaskFilter, TaskState
from hyperadmin_tasks.contract import ContractSeed, TaskBackendContract

pytest.importorskip("pgtask")

pytestmark = [pytest.mark.anyio, pytest.mark.pgtask]


class TestPgTaskBackendContract(TaskBackendContract):
    """
    Scenario: the pgtask adapter passes the contract
      Given a Postgres 16 database migrated with pgtask and seeded through pgtask itself
      When  the contract suite runs against PgTaskBackend on the observer DSN
      Then  every read test passes and action tests skip for missing capabilities
    """

    @pytest.fixture
    def contract_seed(self, seeded_pgtask: tuple[Any, ContractSeed]) -> ContractSeed:
        return seeded_pgtask[1]

    @pytest.fixture
    async def backend(self, seeded_pgtask: tuple[Any, ContractSeed]) -> AsyncIterator[TaskBackend]:
        from hyperadmin_tasks.backends.pgtask import PgTaskBackend

        backend = PgTaskBackend(seeded_pgtask[0].observer_dsn)
        await backend.startup()
        yield backend
        await backend.shutdown()


async def test_pgtask_backend_declares_read_capabilities(
    seeded_pgtask: tuple[Any, ContractSeed],
) -> None:
    """
    Scenario: the read-only adapter advertises workers and schedules
      Given a PgTaskBackend built on the observer DSN
      When  its capabilities are inspected
      Then  workers and schedules are supported and no action capability is
    """
    from hyperadmin_tasks.backends.pgtask import PgTaskBackend

    backend = PgTaskBackend(seeded_pgtask[0].observer_dsn)
    assert backend.capabilities == {Capability.WORKERS, Capability.SCHEDULES}


async def test_failed_task_carries_pgtask_error_message(
    seeded_pgtask: tuple[Any, ContractSeed],
) -> None:
    """
    Scenario: error text of a failed task is shown
      Given a task that failed after three attempts with RuntimeError("boom")
      When  get_task is called
      Then  the task error and every attempt error contain the handler message
    """
    from hyperadmin_tasks.backends.pgtask import PgTaskBackend

    database, seed = seeded_pgtask
    backend = PgTaskBackend(database.observer_dsn)
    await backend.startup()
    try:
        found = await backend.get_task(seed.first_id(TaskState.FAILED))
    finally:
        await backend.shutdown()
    assert found is not None
    task, attempts = found
    assert task.error is not None
    assert "boom" in task.error
    assert [a.outcome for a in attempts] == ["failed"] * 3
    assert all(a.error is not None and "boom" in a.error for a in attempts)


async def test_workers_and_schedules_come_from_observer_views(
    seeded_pgtask: tuple[Any, ContractSeed],
) -> None:
    """
    Scenario: workers and schedules are mapped
      Given a registered worker holding a task and a cron schedule
      When  list_workers and list_schedules are called
      Then  the worker is healthy with its task names and the schedule shows its cron expression
    """
    from hyperadmin_tasks.backends.pgtask import PgTaskBackend

    database, seed = seeded_pgtask
    backend = PgTaskBackend(database.observer_dsn)
    await backend.startup()
    try:
        workers = {w.id: w for w in await backend.list_workers()}
        schedules = {s.id: s for s in await backend.list_schedules()}
    finally:
        await backend.shutdown()
    worker = workers[seed.workers[0].id]
    assert worker.healthy is True
    assert worker.task_names == ("app.report",)
    assert worker.queues == ("default",)
    schedule = schedules[seed.schedules[0].id]
    assert schedule.cron == "0 3 * * *"
    assert schedule.next_run_at is not None


async def test_filtered_page_two_returns_only_matching_rows(
    seeded_pgtask: tuple[Any, ContractSeed],
) -> None:
    """
    Scenario: filter and paginate
      Given five pending tasks on queue default
      When  list_tasks(TaskFilter(queue="default", state=PENDING), page=2, per_page=2) is called
      Then  two pending default tasks are returned and the total is five
    """
    from hyperadmin_tasks.backends.pgtask import PgTaskBackend

    backend = PgTaskBackend(seeded_pgtask[0].observer_dsn)
    await backend.startup()
    try:
        page = await backend.list_tasks(TaskFilter(queue="default", state=TaskState.PENDING), 2, 2)
    finally:
        await backend.shutdown()
    assert len(page.items) == 2
    assert page.total == 5
    assert {t.state for t in page.items} == {TaskState.PENDING}


def test_harness_provisions_observer_and_administrator_roles(
    pgtask_database: Any,
) -> None:
    """
    Scenario: harness provisions roles
      Given a Postgres 16 database migrated with pgtask
      When  the database fixture has run configure_grants
      Then  the observer role can read the views but not write pgtask tables
      And   the administrator role can read the views too
    """
    with psycopg.connect(pgtask_database.observer_dsn) as conn:
        assert conn.execute("SELECT count(*) FROM pgtask.queue_overview").fetchone() == (0,)
        with pytest.raises(psycopg.errors.InsufficientPrivilege):
            conn.execute("DELETE FROM pgtask.tasks")
    with psycopg.connect(pgtask_database.administrator_dsn) as conn:
        assert conn.execute("SELECT count(*) FROM pgtask.task_view").fetchone() == (0,)
