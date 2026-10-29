# ruff: noqa: S101  (a pytest contract suite is made of assertions)
"""Reusable pytest contract suite for ``TaskBackend`` adapters.

Third-party adapters subclass ``TaskBackendContract`` and provide a ``backend`` fixture that
builds a backend natively holding exactly the data of the ``ContractSeed`` it receives::

    class TestMyBackend(TaskBackendContract):
        @pytest.fixture
        async def backend(self, contract_seed: ContractSeed) -> AsyncIterator[TaskBackend]:
            backend = MyBackend()
            await backend.startup()
            await backend.load(contract_seed)  # adapter-specific seeding
            yield backend
            await backend.shutdown()

Tests run under the ``anyio`` pytest plugin (async fixtures included); override the
``anyio_backend`` fixture to pick an event loop backend.
``pytest`` is a development dependency: this module is never imported by the plugin itself.
Tests for an optional action skip when the backend lacks the capability; a separate gating test
asserts ``TasksBackendError`` when it does.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta

import pytest

from hyperadmin_tasks.backend import (
    AttemptRecord,
    Capability,
    ScheduleRecord,
    TaskBackend,
    TaskFilter,
    TaskRecord,
    TasksBackendError,
    TaskState,
    WorkerRecord,
)

ACTOR = "contract-suite"
SEED_NOW = datetime(2026, 1, 1, 12, 0, tzinfo=UTC)
PENDING_ID = "task-0001"
FAILED_ID = "task-0006"
MISSING_ID = "task-does-not-exist"
SCHEDULE_ID = "sched-nightly"


@dataclass(frozen=True)
class ContractSeed:
    """Data a backend must hold when the contract tests run (task ids are unique)."""

    tasks: list[TaskRecord]
    attempts: dict[str, list[AttemptRecord]] = field(default_factory=dict)
    workers: list[WorkerRecord] = field(default_factory=list)
    schedules: list[ScheduleRecord] = field(default_factory=list)


def _task(
    number: int, queue: str, name: str, state: TaskState, *, error: str | None = None
) -> TaskRecord:
    failed = state is TaskState.FAILED
    return TaskRecord(
        id=f"task-{number:04d}",
        queue=queue,
        name=name,
        state=state,
        priority=0,
        attempt=3 if failed else 0,
        max_attempts=3,
        created_at=SEED_NOW - timedelta(minutes=number),
        error=error,
    )


def build_seed() -> ContractSeed:
    """Return the canonical seed: 5 pending, 1 failed, 1 running in ``default``; 2 in ``mail``."""
    tasks = [_task(n, "default", "app.send", TaskState.PENDING) for n in range(1, 6)]
    tasks.append(_task(6, "default", "app.send", TaskState.FAILED, error="boom"))
    tasks.append(_task(7, "default", "app.report", TaskState.RUNNING))
    tasks.append(_task(8, "mail", "app.mail", TaskState.SUCCEEDED))
    tasks.append(_task(9, "mail", "app.mail", TaskState.SCHEDULED))
    attempts = {
        FAILED_ID: [
            AttemptRecord(
                number=n,
                worker_id="worker-1",
                started_at=SEED_NOW - timedelta(minutes=30 - n),
                finished_at=SEED_NOW - timedelta(minutes=29 - n),
                outcome="failed",
                error="boom",
            )
            for n in (1, 2, 3)
        ]
    }
    workers = [
        WorkerRecord(
            id="worker-1",
            queues=("default", "mail"),
            task_names=("app.send", "app.report", "app.mail"),
            last_seen_at=SEED_NOW,
            concurrency=4,
            healthy=True,
        )
    ]
    schedules = [
        ScheduleRecord(
            id=SCHEDULE_ID,
            task_name="app.report",
            queue="default",
            cron="0 3 * * *",
            next_run_at=SEED_NOW + timedelta(hours=15),
            misfire_policy="skip",
        )
    ]
    return ContractSeed(tasks=tasks, attempts=attempts, workers=workers, schedules=schedules)


class TaskBackendContract:
    """Behavioural contract every ``TaskBackend`` must satisfy; subclass and add ``backend``."""

    pytestmark = pytest.mark.anyio

    @pytest.fixture
    def contract_seed(self) -> ContractSeed:
        """Seed the ``backend`` fixture must load into the backend under test."""
        return build_seed()

    @staticmethod
    def _require(backend: TaskBackend, capability: Capability) -> None:
        if capability not in backend.capabilities:
            pytest.skip(f"backend lacks capability '{capability.value}'")

    @staticmethod
    def _require_lacking(backend: TaskBackend, capability: Capability) -> None:
        if capability in backend.capabilities:
            pytest.skip(f"backend supports capability '{capability.value}'")

    async def test_queue_stats_count_tasks_per_state(
        self, backend: TaskBackend, contract_seed: ContractSeed
    ) -> None:
        """
        Scenario: queue stats reflect the seeded tasks
          Given a backend seeded with tasks in the default and mail queues
          When  list_queues is called
          Then  each queue reports its ready, running, scheduled and failed counts
        """
        stats = {q.name: q for q in await backend.list_queues()}
        assert set(stats) >= {"default", "mail"}
        for name, queue in stats.items():
            owned = [t for t in contract_seed.tasks if t.queue == name]
            assert queue.ready == sum(t.state is TaskState.PENDING for t in owned)
            assert queue.running == sum(t.state is TaskState.RUNNING for t in owned)
            assert queue.scheduled == sum(t.state is TaskState.SCHEDULED for t in owned)
            assert queue.failed == sum(t.state is TaskState.FAILED for t in owned)
            assert queue.succeeded_recent >= 0
            assert queue.paused is False

    async def test_list_tasks_without_filter_returns_everything(
        self, backend: TaskBackend, contract_seed: ContractSeed
    ) -> None:
        """
        Scenario: unfiltered listing returns all tasks
          Given a backend seeded with tasks
          When  list_tasks is called with an empty filter and a large page
          Then  every seeded task is returned
        """
        page = await backend.list_tasks(TaskFilter(), 1, 100)
        assert {t.id for t in page.items} == {t.id for t in contract_seed.tasks}

    async def test_filter_by_queue(self, backend: TaskBackend, contract_seed: ContractSeed) -> None:
        """
        Scenario: filtering by queue
          Given tasks in several queues
          When  list_tasks is filtered by queue "mail"
          Then  only mail tasks are returned
        """
        page = await backend.list_tasks(TaskFilter(queue="mail"), 1, 100)
        expected = {t.id for t in contract_seed.tasks if t.queue == "mail"}
        assert {t.id for t in page.items} == expected

    async def test_filter_by_state(self, backend: TaskBackend, contract_seed: ContractSeed) -> None:
        """
        Scenario: filtering by state
          Given tasks in several states
          When  list_tasks is filtered by state failed
          Then  only failed tasks are returned
        """
        page = await backend.list_tasks(TaskFilter(state=TaskState.FAILED), 1, 100)
        expected = {t.id for t in contract_seed.tasks if t.state is TaskState.FAILED}
        assert {t.id for t in page.items} == expected

    async def test_filter_by_name(self, backend: TaskBackend, contract_seed: ContractSeed) -> None:
        """
        Scenario: filtering by task name
          Given tasks with different names
          When  list_tasks is filtered by name "app.report"
          Then  only tasks with that name are returned
        """
        page = await backend.list_tasks(TaskFilter(name="app.report"), 1, 100)
        expected = {t.id for t in contract_seed.tasks if t.name == "app.report"}
        assert {t.id for t in page.items} == expected

    async def test_filter_by_id_query(self, backend: TaskBackend) -> None:
        """
        Scenario: filtering by id query
          Given tasks with distinct ids
          When  list_tasks is filtered by id_query "task-0003"
          Then  exactly that task is returned
        """
        page = await backend.list_tasks(TaskFilter(id_query="task-0003"), 1, 100)
        assert [t.id for t in page.items] == ["task-0003"]

    async def test_filters_combine(self, backend: TaskBackend, contract_seed: ContractSeed) -> None:
        """
        Scenario: filters are combined with AND
          Given tasks in several queues and states
          When  list_tasks is filtered by queue "default" and state pending
          Then  only pending default tasks are returned
        """
        flt = TaskFilter(queue="default", state=TaskState.PENDING)
        page = await backend.list_tasks(flt, 1, 100)
        expected = {
            t.id
            for t in contract_seed.tasks
            if t.queue == "default" and t.state is TaskState.PENDING
        }
        assert {t.id for t in page.items} == expected

    async def test_pagination_splits_results(
        self, backend: TaskBackend, contract_seed: ContractSeed
    ) -> None:
        """
        Scenario: results are paginated
          Given nine seeded tasks
          When  list_tasks is called with per_page 4 for pages 1 to 3
          Then  pages hold 4, 4 and 1 distinct tasks and report page, per_page and total
        """
        total = len(contract_seed.tasks)
        pages = [await backend.list_tasks(TaskFilter(), n, 4) for n in (1, 2, 3)]
        assert [len(p.items) for p in pages] == [4, 4, total - 8]
        assert [(p.page, p.per_page) for p in pages] == [(1, 4), (2, 4), (3, 4)]
        assert all(p.total in (None, total) for p in pages)
        ids = [t.id for p in pages for t in p.items]
        assert len(set(ids)) == total

    async def test_pagination_past_the_end_is_empty(self, backend: TaskBackend) -> None:
        """
        Scenario: a page past the end is empty
          Given nine seeded tasks
          When  list_tasks requests page 99
          Then  no items are returned
        """
        page = await backend.list_tasks(TaskFilter(), 99, 4)
        assert page.items == []

    async def test_get_task_returns_task_with_attempts(self, backend: TaskBackend) -> None:
        """
        Scenario: task detail includes attempts
          Given a failed task with three attempts
          When  get_task is called with its id
          Then  the task and its attempts in order are returned
        """
        found = await backend.get_task(FAILED_ID)
        assert found is not None
        task, attempts = found
        assert task.id == FAILED_ID
        assert task.state is TaskState.FAILED
        assert [a.number for a in attempts] == [1, 2, 3]

    async def test_get_task_without_attempts_returns_empty_list(self, backend: TaskBackend) -> None:
        """
        Scenario: task without attempts
          Given a pending task that never ran
          When  get_task is called with its id
          Then  the task is returned with no attempts
        """
        found = await backend.get_task(PENDING_ID)
        assert found is not None
        assert found[0].id == PENDING_ID
        assert found[1] == []

    async def test_get_task_unknown_id_returns_none(self, backend: TaskBackend) -> None:
        """
        Scenario: unknown task id
          Given no task with a given id
          When  get_task is called with it
          Then  None is returned
        """
        assert await backend.get_task(MISSING_ID) is None

    async def test_list_workers(self, backend: TaskBackend, contract_seed: ContractSeed) -> None:
        """
        Scenario: workers are listed
          Given a backend with the workers capability and a seeded worker
          When  list_workers is called
          Then  the seeded worker ids are returned
        """
        self._require(backend, Capability.WORKERS)
        workers = await backend.list_workers()
        assert {w.id for w in workers} >= {w.id for w in contract_seed.workers}

    async def test_list_workers_without_capability_raises(self, backend: TaskBackend) -> None:
        """
        Scenario: workers without capability
          Given a backend lacking the workers capability
          When  list_workers is called
          Then  TasksBackendError is raised
        """
        self._require_lacking(backend, Capability.WORKERS)
        with pytest.raises(TasksBackendError):
            await backend.list_workers()

    async def test_list_schedules(self, backend: TaskBackend, contract_seed: ContractSeed) -> None:
        """
        Scenario: schedules are listed
          Given a backend with the schedules capability and a seeded schedule
          When  list_schedules is called
          Then  the seeded schedule ids are returned
        """
        self._require(backend, Capability.SCHEDULES)
        schedules = await backend.list_schedules()
        assert {s.id for s in schedules} >= {s.id for s in contract_seed.schedules}

    async def test_list_schedules_without_capability_raises(self, backend: TaskBackend) -> None:
        """
        Scenario: schedules without capability
          Given a backend lacking the schedules capability
          When  list_schedules is called
          Then  TasksBackendError is raised
        """
        self._require_lacking(backend, Capability.SCHEDULES)
        with pytest.raises(TasksBackendError):
            await backend.list_schedules()

    async def test_retry_task_makes_failed_task_pending(self, backend: TaskBackend) -> None:
        """
        Scenario: retry contract
          Given a failed task
          When  retry_task is called with an actor
          Then  the task's state becomes pending
        """
        self._require(backend, Capability.RETRY)
        await backend.retry_task(FAILED_ID, actor=ACTOR)
        found = await backend.get_task(FAILED_ID)
        assert found is not None
        assert found[0].state is TaskState.PENDING

    async def test_retry_without_capability_raises(self, backend: TaskBackend) -> None:
        """
        Scenario: retry without capability
          Given a backend lacking the retry capability
          When  retry_task is called
          Then  TasksBackendError is raised
        """
        self._require_lacking(backend, Capability.RETRY)
        with pytest.raises(TasksBackendError):
            await backend.retry_task(FAILED_ID, actor=ACTOR)

    async def test_cancel_task_makes_pending_task_cancelled(self, backend: TaskBackend) -> None:
        """
        Scenario: cancel contract
          Given a pending task
          When  cancel_task is called with an actor
          Then  the task's state becomes cancelled
        """
        self._require(backend, Capability.CANCEL)
        await backend.cancel_task(PENDING_ID, actor=ACTOR)
        found = await backend.get_task(PENDING_ID)
        assert found is not None
        assert found[0].state is TaskState.CANCELLED

    async def test_cancel_without_capability_raises(self, backend: TaskBackend) -> None:
        """
        Scenario: cancel without capability
          Given a backend lacking the cancel capability
          When  cancel_task is called
          Then  TasksBackendError is raised
        """
        self._require_lacking(backend, Capability.CANCEL)
        with pytest.raises(TasksBackendError):
            await backend.cancel_task(PENDING_ID, actor=ACTOR)

    async def test_pause_and_resume_queue(self, backend: TaskBackend) -> None:
        """
        Scenario: queue pause and resume
          Given a running queue
          When  set_queue_paused is called with True then False
          Then  list_queues reports the queue paused then not paused
        """
        self._require(backend, Capability.PAUSE_QUEUE)
        await backend.set_queue_paused("default", True, actor=ACTOR)
        paused = {q.name: q.paused for q in await backend.list_queues()}
        assert paused["default"] is True
        await backend.set_queue_paused("default", False, actor=ACTOR)
        resumed = {q.name: q.paused for q in await backend.list_queues()}
        assert resumed["default"] is False

    async def test_pause_queue_without_capability_raises(self, backend: TaskBackend) -> None:
        """
        Scenario: queue pause without capability
          Given a backend lacking the pause_queue capability
          When  set_queue_paused is called
          Then  TasksBackendError is raised
        """
        self._require_lacking(backend, Capability.PAUSE_QUEUE)
        with pytest.raises(TasksBackendError):
            await backend.set_queue_paused("default", True, actor=ACTOR)

    async def test_pause_and_resume_schedule(self, backend: TaskBackend) -> None:
        """
        Scenario: schedule pause and resume
          Given an active schedule
          When  set_schedule_paused is called with True then False
          Then  list_schedules reports the schedule paused then not paused
        """
        self._require(backend, Capability.PAUSE_SCHEDULE)
        await backend.set_schedule_paused(SCHEDULE_ID, True, actor=ACTOR)
        paused = {s.id: s.paused for s in await backend.list_schedules()}
        assert paused[SCHEDULE_ID] is True
        await backend.set_schedule_paused(SCHEDULE_ID, False, actor=ACTOR)
        resumed = {s.id: s.paused for s in await backend.list_schedules()}
        assert resumed[SCHEDULE_ID] is False

    async def test_pause_schedule_without_capability_raises(self, backend: TaskBackend) -> None:
        """
        Scenario: schedule pause without capability
          Given a backend lacking the pause_schedule capability
          When  set_schedule_paused is called
          Then  TasksBackendError is raised
        """
        self._require_lacking(backend, Capability.PAUSE_SCHEDULE)
        with pytest.raises(TasksBackendError):
            await backend.set_schedule_paused(SCHEDULE_ID, True, actor=ACTOR)
