"""In-memory ``TaskBackend`` for tests, demos and UI development (no database required)."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING

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

if TYPE_CHECKING:
    from collections.abc import Callable, Iterable, Mapping

_RETRYABLE = frozenset({TaskState.FAILED, TaskState.CANCELLED})
_CANCELLABLE = frozenset({TaskState.PENDING, TaskState.SCHEDULED})


def _utcnow() -> datetime:
    return datetime.now(UTC)


class InMemoryTaskBackend:
    """Deterministic, process-local backend; state lives in plain dicts.

    Tasks are listed newest first (``created_at`` descending, ties broken by id) and queues,
    workers and schedules by name/id, so output is stable across runs. Every mutating action
    appends an ``(action, target, actor)`` entry to :attr:`audit`.
    """

    def __init__(
        self,
        capabilities: Iterable[Capability] | None = None,
        *,
        clock: Callable[[], datetime] = _utcnow,
    ) -> None:
        self.capabilities: frozenset[Capability] = (
            frozenset(Capability) if capabilities is None else frozenset(capabilities)
        )
        self._clock = clock
        self._tasks: dict[str, TaskRecord] = {}
        self._attempts: dict[str, list[AttemptRecord]] = {}
        self._workers: dict[str, WorkerRecord] = {}
        self._schedules: dict[str, ScheduleRecord] = {}
        self._paused_queues: set[str] = set()
        self._audit: list[tuple[str, str, str]] = []

    @property
    def audit(self) -> list[tuple[str, str, str]]:
        """Copy of the recorded ``(action, target, actor)`` entries, oldest first."""
        return list(self._audit)

    def seed(
        self,
        tasks: Iterable[TaskRecord] = (),
        *,
        attempts: Mapping[str, Iterable[AttemptRecord]] | None = None,
        workers: Iterable[WorkerRecord] = (),
        schedules: Iterable[ScheduleRecord] = (),
    ) -> None:
        """Add or replace records by id; attempts are keyed by task id."""
        for task in tasks:
            self._tasks[task.id] = task
        for task_id, task_attempts in (attempts or {}).items():
            self._attempts[task_id] = list(task_attempts)
        for worker in workers:
            self._workers[worker.id] = worker
        for schedule in schedules:
            self._schedules[schedule.id] = schedule

    @classmethod
    def demo(cls, *, now: datetime | None = None) -> InMemoryTaskBackend:
        """Return a backend pre-loaded with demo data spanning queues, states and schedules."""
        moment = now or _utcnow()
        backend = cls(clock=lambda: moment)
        states = (
            ("default", "app.send_email", TaskState.PENDING),
            ("default", "app.send_email", TaskState.RUNNING),
            ("default", "app.sync_users", TaskState.FAILED),
            ("reports", "app.build_report", TaskState.PENDING),
            ("reports", "app.build_report", TaskState.SUCCEEDED),
            ("reports", "app.build_report", TaskState.SCHEDULED),
        )
        tasks = [
            TaskRecord(
                id=f"demo-{n:04d}",
                queue=queue,
                name=name,
                state=state,
                priority=0,
                attempt=1 if state is TaskState.FAILED else 0,
                max_attempts=3,
                created_at=moment - timedelta(minutes=n),
                error="connection reset" if state is TaskState.FAILED else None,
            )
            for n, (queue, name, state) in enumerate(states, start=1)
        ]
        backend.seed(
            tasks,
            attempts={
                "demo-0003": [
                    AttemptRecord(
                        number=1,
                        worker_id="demo-worker",
                        started_at=moment - timedelta(minutes=10),
                        finished_at=moment - timedelta(minutes=9),
                        outcome="failed",
                        error="connection reset",
                    )
                ]
            },
            workers=[
                WorkerRecord(
                    id="demo-worker",
                    queues=("default", "reports"),
                    task_names=("app.send_email", "app.sync_users", "app.build_report"),
                    last_seen_at=moment,
                    concurrency=4,
                    healthy=True,
                )
            ],
            schedules=[
                ScheduleRecord(
                    id="demo-nightly",
                    task_name="app.build_report",
                    queue="reports",
                    cron="0 3 * * *",
                    next_run_at=moment + timedelta(hours=12),
                    misfire_policy="skip",
                )
            ],
        )
        return backend

    async def startup(self) -> None:
        """Nothing to open."""

    async def shutdown(self) -> None:
        """Nothing to release."""

    def _ordered_tasks(self) -> list[TaskRecord]:
        return sorted(self._tasks.values(), key=lambda t: (-t.created_at.timestamp(), t.id))

    async def list_queues(self) -> list[QueueStats]:
        """Return counters for every queue seen on a task, sorted by name."""
        now = self._clock()
        stats: list[QueueStats] = []
        for name in sorted({t.queue for t in self._tasks.values()} | self._paused_queues):
            owned = [t for t in self._tasks.values() if t.queue == name]
            ready = [t for t in owned if t.state is TaskState.PENDING]
            stats.append(
                QueueStats(
                    name=name,
                    ready=len(ready),
                    running=sum(t.state is TaskState.RUNNING for t in owned),
                    scheduled=sum(t.state is TaskState.SCHEDULED for t in owned),
                    failed=sum(t.state is TaskState.FAILED for t in owned),
                    succeeded_recent=sum(t.state is TaskState.SUCCEEDED for t in owned),
                    oldest_ready_age=(now - min(t.created_at for t in ready)) if ready else None,
                    paused=name in self._paused_queues,
                )
            )
        return stats

    async def list_tasks(self, flt: TaskFilter, page: int, per_page: int) -> Page[TaskRecord]:
        """Return one page (1-based) of tasks matching ``flt``, newest first."""
        if page < 1 or per_page < 1:
            raise TasksBackendError(f"page and per_page must be >= 1, got {page} and {per_page}")
        matching = [
            t
            for t in self._ordered_tasks()
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
        """Return the task with its attempts ordered by number, or ``None``."""
        task = self._tasks.get(task_id)
        if task is None:
            return None
        return task, sorted(self._attempts.get(task_id, []), key=lambda a: a.number)

    async def list_workers(self) -> list[WorkerRecord]:
        """Return workers sorted by id."""
        require_capability(self, Capability.WORKERS)
        return sorted(self._workers.values(), key=lambda w: w.id)

    async def list_schedules(self) -> list[ScheduleRecord]:
        """Return schedules sorted by id."""
        require_capability(self, Capability.SCHEDULES)
        return sorted(self._schedules.values(), key=lambda s: s.id)

    def _task(self, task_id: str) -> TaskRecord:
        try:
            return self._tasks[task_id]
        except KeyError:
            raise TasksBackendError(f"unknown task '{task_id}'") from None

    async def retry_task(self, task_id: str, *, actor: str) -> None:
        """Move a failed or cancelled task back to pending."""
        require_capability(self, Capability.RETRY)
        task = self._task(task_id)
        if task.state not in _RETRYABLE:
            raise TasksBackendError(f"task '{task_id}' is {task.state.value}, cannot retry")
        self._tasks[task_id] = task.model_copy(
            update={"state": TaskState.PENDING, "error": None, "finished_at": None}
        )
        self._audit.append(("retry_task", task_id, actor))

    async def cancel_task(self, task_id: str, *, actor: str) -> None:
        """Cancel a pending or scheduled task."""
        require_capability(self, Capability.CANCEL)
        task = self._task(task_id)
        if task.state not in _CANCELLABLE:
            raise TasksBackendError(f"task '{task_id}' is {task.state.value}, cannot cancel")
        self._tasks[task_id] = task.model_copy(
            update={"state": TaskState.CANCELLED, "finished_at": self._clock()}
        )
        self._audit.append(("cancel_task", task_id, actor))

    async def set_queue_paused(self, queue: str, paused: bool, *, actor: str) -> None:
        """Pause or resume ``queue``."""
        require_capability(self, Capability.PAUSE_QUEUE)
        if paused:
            self._paused_queues.add(queue)
        else:
            self._paused_queues.discard(queue)
        self._audit.append(("pause_queue" if paused else "resume_queue", queue, actor))

    async def set_schedule_paused(self, schedule_id: str, paused: bool, *, actor: str) -> None:
        """Pause or resume a schedule."""
        require_capability(self, Capability.PAUSE_SCHEDULE)
        try:
            schedule = self._schedules[schedule_id]
        except KeyError:
            raise TasksBackendError(f"unknown schedule '{schedule_id}'") from None
        self._schedules[schedule_id] = schedule.model_copy(update={"paused": paused})
        self._audit.append(("pause_schedule" if paused else "resume_schedule", schedule_id, actor))
