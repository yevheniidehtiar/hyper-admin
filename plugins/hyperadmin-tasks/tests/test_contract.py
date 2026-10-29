"""Proves the reusable contract suite collects and passes against a minimal stub backend.

The in-memory backend story runs the same suite against the real adapter; this stub only keeps
the suite itself exercised (and covered) until then.
"""

from __future__ import annotations

from collections.abc import AsyncIterator

import pytest

from hyperadmin_tasks.backend import (
    AttemptRecord,
    Capability,
    Page,
    QueueStats,
    ScheduleRecord,
    TaskFilter,
    TaskRecord,
    TasksBackendError,
    TaskState,
    WorkerRecord,
    require_capability,
)
from hyperadmin_tasks.contract import ContractSeed, TaskBackendContract


class _StubBackend:
    """Smallest backend that satisfies the contract; not a product adapter."""

    def __init__(self, seed: ContractSeed, capabilities: frozenset[Capability]) -> None:
        self.capabilities = capabilities
        self._tasks = {t.id: t for t in seed.tasks}
        self._attempts = seed.attempts
        self._workers = seed.workers
        self._schedules = {s.id: s for s in seed.schedules}
        self._paused_queues: set[str] = set()

    async def startup(self) -> None:
        return None

    async def shutdown(self) -> None:
        return None

    async def list_queues(self) -> list[QueueStats]:
        names = sorted({t.queue for t in self._tasks.values()})

        def count(queue: str, state: TaskState) -> int:
            return sum(t.queue == queue and t.state is state for t in self._tasks.values())

        return [
            QueueStats(
                name=n,
                ready=count(n, TaskState.PENDING),
                running=count(n, TaskState.RUNNING),
                scheduled=count(n, TaskState.SCHEDULED),
                failed=count(n, TaskState.FAILED),
                succeeded_recent=count(n, TaskState.SUCCEEDED),
                paused=n in self._paused_queues,
            )
            for n in names
        ]

    async def list_tasks(self, flt: TaskFilter, page: int, per_page: int) -> Page[TaskRecord]:
        if page < 1 or per_page < 1:
            raise TasksBackendError("page and per_page must be >= 1")
        matching = [
            t
            for t in self._tasks.values()
            if (flt.queue is None or t.queue == flt.queue)
            and (flt.state is None or t.state is flt.state)
            and (flt.name is None or t.name == flt.name)
            and (flt.id_query is None or flt.id_query in t.id)
        ]
        start = (page - 1) * per_page
        return Page[TaskRecord](
            items=matching[start : start + per_page],
            page=page,
            per_page=per_page,
            total=len(matching),
        )

    async def get_task(self, task_id: str) -> tuple[TaskRecord, list[AttemptRecord]] | None:
        task = self._tasks.get(task_id)
        return None if task is None else (task, self._attempts.get(task_id, []))

    async def list_workers(self) -> list[WorkerRecord]:
        require_capability(self, Capability.WORKERS)
        return list(self._workers)

    async def list_schedules(self) -> list[ScheduleRecord]:
        require_capability(self, Capability.SCHEDULES)
        return list(self._schedules.values())

    async def retry_task(self, task_id: str, *, actor: str) -> None:
        require_capability(self, Capability.RETRY)
        self._tasks[task_id] = self._tasks[task_id].model_copy(update={"state": TaskState.PENDING})

    async def cancel_task(self, task_id: str, *, actor: str) -> None:
        require_capability(self, Capability.CANCEL)
        self._tasks[task_id] = self._tasks[task_id].model_copy(
            update={"state": TaskState.CANCELLED}
        )

    async def set_queue_paused(self, queue: str, paused: bool, *, actor: str) -> None:
        require_capability(self, Capability.PAUSE_QUEUE)
        (self._paused_queues.add if paused else self._paused_queues.discard)(queue)

    async def set_schedule_paused(self, schedule_id: str, paused: bool, *, actor: str) -> None:
        require_capability(self, Capability.PAUSE_SCHEDULE)
        schedule = self._schedules[schedule_id]
        self._schedules[schedule_id] = schedule.model_copy(update={"paused": paused})


class TestStubWithAllCapabilities(TaskBackendContract):
    """
    Scenario: adapter authors reuse the suite
      Given a test module subclasses TaskBackendContract with a backend fixture
      When  pytest runs
      Then  all contract tests are collected against that backend
    """

    @pytest.fixture
    async def backend(self, contract_seed: ContractSeed) -> AsyncIterator[_StubBackend]:
        stub = _StubBackend(contract_seed, frozenset(Capability))
        await stub.startup()
        yield stub
        await stub.shutdown()


class TestStubWithoutCapabilities(TaskBackendContract):
    """
    Scenario: capability gating is enforced
      Given a backend declaring no optional capabilities
      When  the contract runs
      Then  action tests skip and gating tests see TasksBackendError
    """

    @pytest.fixture
    async def backend(self, contract_seed: ContractSeed) -> _StubBackend:
        return _StubBackend(contract_seed, frozenset())
