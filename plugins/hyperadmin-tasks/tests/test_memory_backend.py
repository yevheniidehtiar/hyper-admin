"""Runs the reusable contract suite against ``InMemoryTaskBackend`` and covers its extras."""

from __future__ import annotations

from collections.abc import AsyncIterator
from datetime import UTC, datetime, timedelta

import pytest

from hyperadmin_tasks.backend import (
    Capability,
    TaskBackend,
    TaskFilter,
    TasksBackendError,
    TaskState,
)
from hyperadmin_tasks.backends import InMemoryTaskBackend
from hyperadmin_tasks.contract import (
    FAILED_ID,
    PENDING_ID,
    SCHEDULE_ID,
    SEED_NOW,
    ContractSeed,
    TaskBackendContract,
    build_seed,
)

pytestmark = pytest.mark.anyio


def _loaded(capabilities: frozenset[Capability] | None = None) -> InMemoryTaskBackend:
    seed = build_seed()
    backend = InMemoryTaskBackend(capabilities, clock=lambda: SEED_NOW)
    backend.seed(seed.tasks, attempts=seed.attempts, workers=seed.workers, schedules=seed.schedules)
    return backend


class TestInMemoryBackendContract(TaskBackendContract):
    """
    Scenario: in-memory backend passes the contract
      Given InMemoryTaskBackend seeded with tasks across queues and states
      When  the contract suite runs
      Then  all tests pass
    """

    @pytest.fixture
    async def backend(self, contract_seed: ContractSeed) -> AsyncIterator[TaskBackend]:
        backend = InMemoryTaskBackend(clock=lambda: SEED_NOW)
        await backend.startup()
        backend.seed(
            contract_seed.tasks,
            attempts=contract_seed.attempts,
            workers=contract_seed.workers,
            schedules=contract_seed.schedules,
        )
        yield backend
        await backend.shutdown()


class TestInMemoryBackendWithoutCapabilities(TaskBackendContract):
    """
    Scenario: reduced capabilities are rejected
      Given an InMemoryTaskBackend constructed with no capabilities
      When  the contract suite runs
      Then  action tests skip and gating tests see TasksBackendError
    """

    @pytest.fixture
    def backend(self, contract_seed: ContractSeed) -> TaskBackend:
        backend = InMemoryTaskBackend([])
        backend.seed(
            contract_seed.tasks,
            attempts=contract_seed.attempts,
            workers=contract_seed.workers,
            schedules=contract_seed.schedules,
        )
        return backend


async def test_queue_pause_is_reflected_and_audited() -> None:
    """
    Scenario: queue pause is reflected
      Given an unpaused queue "reports"
      When  set_queue_paused("reports", True, actor="alice") is called
      Then  list_queues reports paused=True and the actor is recorded
    """
    backend = InMemoryTaskBackend.demo()
    before = {q.name: q.paused for q in await backend.list_queues()}
    assert before["reports"] is False

    await backend.set_queue_paused("reports", True, actor="alice")

    after = {q.name: q.paused for q in await backend.list_queues()}
    assert after["reports"] is True
    assert backend.audit == [("pause_queue", "reports", "alice")]


async def test_paused_queue_without_tasks_is_still_listed() -> None:
    """
    Scenario: pausing an empty queue
      Given a backend with no tasks
      When  set_queue_paused("ghost", True) then False is called
      Then  the queue is listed as paused, then disappears, and both actions are audited
    """
    backend = InMemoryTaskBackend()
    await backend.set_queue_paused("ghost", True, actor="bob")
    assert [(q.name, q.paused) for q in await backend.list_queues()] == [("ghost", True)]
    await backend.set_queue_paused("ghost", False, actor="bob")
    assert await backend.list_queues() == []
    assert backend.audit == [("pause_queue", "ghost", "bob"), ("resume_queue", "ghost", "bob")]


async def test_audit_records_every_action_in_order_and_is_a_copy() -> None:
    """
    Scenario: audit trail
      Given a seeded backend
      When  retry, cancel and schedule pause/resume actions run
      Then  audit lists (action, target, actor) entries in order, and mutating the copy is inert
    """
    backend = _loaded()
    await backend.retry_task(FAILED_ID, actor="a")
    await backend.cancel_task(PENDING_ID, actor="b")
    await backend.set_schedule_paused(SCHEDULE_ID, True, actor="c")
    await backend.set_schedule_paused(SCHEDULE_ID, False, actor="d")
    expected = [
        ("retry_task", FAILED_ID, "a"),
        ("cancel_task", PENDING_ID, "b"),
        ("pause_schedule", SCHEDULE_ID, "c"),
        ("resume_schedule", SCHEDULE_ID, "d"),
    ]
    assert backend.audit == expected
    backend.audit.clear()
    assert backend.audit == expected


async def test_oldest_ready_age_uses_the_clock() -> None:
    """
    Scenario: oldest ready age
      Given pending tasks created 1..5 minutes before the clock
      When  list_queues is called
      Then  the default queue reports five minutes and the empty-ready mail queue None
    """
    stats = {q.name: q for q in await _loaded().list_queues()}
    assert stats["default"].oldest_ready_age == timedelta(minutes=5)
    assert stats["mail"].oldest_ready_age is None


async def test_ordering_is_newest_first_with_id_tiebreak() -> None:
    """
    Scenario: deterministic ordering
      Given tasks seeded out of order, two sharing a timestamp
      When  list_tasks is called
      Then  results are newest first and ties are ordered by id
    """
    backend = _loaded()
    twin = build_seed().tasks[0].model_copy(update={"id": "task-0000"})
    backend.seed([twin])
    page = await backend.list_tasks(TaskFilter(queue="default"), 1, 100)
    ids = [t.id for t in page.items]
    assert ids[:2] == ["task-0000", "task-0001"]
    assert ids[2:] == ["task-0002", "task-0003", "task-0004", "task-0005", "task-0006", "task-0007"]


async def test_workers_and_schedules_sorted_by_id() -> None:
    """
    Scenario: workers and schedules are sorted
      Given two workers and two schedules seeded in reverse order
      When  they are listed
      Then  they come back sorted by id
    """
    seed = build_seed()
    backend = InMemoryTaskBackend()
    backend.seed(
        workers=[
            seed.workers[0].model_copy(update={"id": "w-b"}),
            seed.workers[0].model_copy(update={"id": "w-a"}),
        ],
        schedules=[
            seed.schedules[0].model_copy(update={"id": "s-b"}),
            seed.schedules[0].model_copy(update={"id": "s-a"}),
        ],
    )
    assert [w.id for w in await backend.list_workers()] == ["w-a", "w-b"]
    assert [s.id for s in await backend.list_schedules()] == ["s-a", "s-b"]


async def test_attempts_are_ordered_by_number() -> None:
    """
    Scenario: attempts ordering
      Given attempts seeded out of order
      When  get_task is called
      Then  attempts are returned by number
    """
    seed = build_seed()
    backend = InMemoryTaskBackend()
    backend.seed(seed.tasks, attempts={FAILED_ID: reversed(seed.attempts[FAILED_ID])})
    found = await backend.get_task(FAILED_ID)
    assert found is not None
    assert [a.number for a in found[1]] == [1, 2, 3]


async def test_retry_clears_error_and_cancel_sets_finished_time() -> None:
    """
    Scenario: state transitions update the record
      Given a failed task and a pending task
      When  the failed one is retried and the pending one cancelled
      Then  the error is cleared and the cancelled task has a finished time from the clock
    """
    backend = _loaded()
    await backend.retry_task(FAILED_ID, actor="a")
    await backend.cancel_task(PENDING_ID, actor="a")
    retried = await backend.get_task(FAILED_ID)
    cancelled = await backend.get_task(PENDING_ID)
    assert retried is not None
    assert cancelled is not None
    assert retried[0].error is None
    assert cancelled[0].finished_at == SEED_NOW


@pytest.mark.parametrize("task_id", [PENDING_ID, "task-0007", "task-0008"])
async def test_retry_rejects_tasks_that_did_not_fail(task_id: str) -> None:
    """
    Scenario: retry of a non-failed task
      Given a pending, running or succeeded task
      When  retry_task is called
      Then  TasksBackendError is raised and nothing is audited
    """
    backend = _loaded()
    with pytest.raises(TasksBackendError, match="cannot retry"):
        await backend.retry_task(task_id, actor="a")
    assert backend.audit == []


@pytest.mark.parametrize("task_id", [FAILED_ID, "task-0007", "task-0008"])
async def test_cancel_rejects_tasks_that_cannot_be_cancelled(task_id: str) -> None:
    """
    Scenario: cancel of a non-cancellable task
      Given a failed, running or succeeded task
      When  cancel_task is called
      Then  TasksBackendError is raised and nothing is audited
    """
    backend = _loaded()
    with pytest.raises(TasksBackendError, match="cannot cancel"):
        await backend.cancel_task(task_id, actor="a")
    assert backend.audit == []


async def test_unknown_ids_are_rejected() -> None:
    """
    Scenario: unknown task or schedule
      Given a seeded backend
      When  retry_task, cancel_task or set_schedule_paused get an unknown id
      Then  TasksBackendError is raised
    """
    backend = _loaded()
    with pytest.raises(TasksBackendError, match="unknown task"):
        await backend.retry_task("nope", actor="a")
    with pytest.raises(TasksBackendError, match="unknown task"):
        await backend.cancel_task("nope", actor="a")
    with pytest.raises(TasksBackendError, match="unknown schedule"):
        await backend.set_schedule_paused("nope", True, actor="a")


async def test_default_capabilities_are_all_and_reduced_set_is_respected() -> None:
    """
    Scenario: capability constructor argument
      Given backends built with and without a capabilities argument
      When  capabilities are inspected and a missing one is used
      Then  the default holds every Capability and the reduced one rejects the gated call
    """
    assert InMemoryTaskBackend().capabilities == frozenset(Capability)
    reduced = _loaded(frozenset({Capability.RETRY}))
    assert reduced.capabilities == frozenset({Capability.RETRY})
    with pytest.raises(TasksBackendError, match="'cancel'"):
        await reduced.cancel_task(PENDING_ID, actor="a")
    await reduced.retry_task(FAILED_ID, actor="a")
    assert reduced.audit == [("retry_task", FAILED_ID, "a")]


async def test_demo_backend_is_populated_and_deterministic() -> None:
    """
    Scenario: demo seed
      Given a demo backend built at a fixed moment
      When  its contents are listed
      Then  it has two queues, a worker, a schedule and a failed task with an attempt
    """
    moment = datetime(2026, 5, 1, tzinfo=UTC)
    backend = InMemoryTaskBackend.demo(now=moment)
    assert [q.name for q in await backend.list_queues()] == ["default", "reports"]
    assert len(await backend.list_workers()) == 1
    assert [s.id for s in await backend.list_schedules()] == ["demo-nightly"]
    failed = await backend.list_tasks(TaskFilter(state=TaskState.FAILED), 1, 10)
    found = await backend.get_task(failed.items[0].id)
    assert found is not None
    assert len(found[1]) == 1
    assert InMemoryTaskBackend.demo().capabilities == frozenset(Capability)
