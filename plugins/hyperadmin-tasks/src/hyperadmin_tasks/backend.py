"""Backend port for the tasks plugin: read models, capabilities and the ``TaskBackend`` contract.

Adapters (in-memory, pgtask, ...) map their native states and rows onto the frozen models here.
The plugin's routes depend only on this module, never on a concrete queue library.
"""

from __future__ import annotations

from datetime import datetime, timedelta  # noqa: TC003 - pydantic resolves annotations at runtime
from enum import StrEnum
from typing import Any, Generic, Protocol, TypeVar, runtime_checkable

from pydantic import BaseModel, ConfigDict

T = TypeVar("T")


class TaskState(StrEnum):
    """Normalised task lifecycle state; each adapter maps its native states onto it."""

    PENDING = "pending"
    SCHEDULED = "scheduled"
    RUNNING = "running"
    SLEEPING = "sleeping"
    WAITING = "waiting"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    CANCELLED = "cancelled"


class Capability(StrEnum):
    """Optional actions and views a backend may support."""

    RETRY = "retry"
    CANCEL = "cancel"
    PAUSE_QUEUE = "pause_queue"
    PAUSE_SCHEDULE = "pause_schedule"
    SCHEDULES = "schedules"
    WORKERS = "workers"


class TasksBackendError(Exception):
    """Raised when a backend cannot satisfy a request (unsupported action, driver, drift)."""


class _Frozen(BaseModel):
    model_config = ConfigDict(frozen=True)


class QueueStats(_Frozen):
    """Per-queue counters shown on the dashboard."""

    name: str
    ready: int
    running: int
    scheduled: int
    failed: int
    succeeded_recent: int
    oldest_ready_age: timedelta | None = None
    paused: bool = False


class TaskRecord(_Frozen):
    """One task as listed or shown in detail."""

    id: str
    queue: str
    name: str
    state: TaskState
    priority: int
    attempt: int
    max_attempts: int
    created_at: datetime
    run_at: datetime | None = None
    finished_at: datetime | None = None
    payload: Any = None
    result: Any = None
    error: str | None = None
    parent_id: str | None = None


class AttemptRecord(_Frozen):
    """One execution attempt of a task."""

    number: int
    worker_id: str | None = None
    started_at: datetime
    finished_at: datetime | None = None
    outcome: str
    error: str | None = None


class WorkerRecord(_Frozen):
    """A worker process consuming one or more queues."""

    id: str
    queues: tuple[str, ...]
    task_names: tuple[str, ...]
    last_seen_at: datetime
    concurrency: int
    healthy: bool


class ScheduleRecord(_Frozen):
    """A recurring (cron) schedule."""

    id: str
    task_name: str
    queue: str
    cron: str
    next_run_at: datetime | None = None
    misfire_policy: str
    paused: bool = False


class TaskFilter(_Frozen):
    """Filter applied to task listings; unset fields match everything."""

    queue: str | None = None
    state: TaskState | None = None
    name: str | None = None
    id_query: str | None = None


class Page(BaseModel, Generic[T]):
    """One page of results; ``total`` is ``None`` when the backend cannot count cheaply."""

    model_config = ConfigDict(frozen=True)

    items: list[T]
    page: int
    per_page: int
    total: int | None = None


@runtime_checkable
class TaskBackend(Protocol):
    """Contract every task backend adapter implements."""

    capabilities: frozenset[Capability]

    async def startup(self) -> None:
        """Open connections or pools."""

    async def shutdown(self) -> None:
        """Release connections or pools."""

    async def list_queues(self) -> list[QueueStats]:
        """Return counters for every queue."""
        raise NotImplementedError

    async def list_tasks(self, flt: TaskFilter, page: int, per_page: int) -> Page[TaskRecord]:
        """Return one page of tasks matching ``flt``."""
        raise NotImplementedError

    async def get_task(self, task_id: str) -> tuple[TaskRecord, list[AttemptRecord]] | None:
        """Return a task with its attempts, or ``None`` when it does not exist."""

    async def list_workers(self) -> list[WorkerRecord]:
        """Return known workers (requires ``Capability.WORKERS``)."""
        raise NotImplementedError

    async def list_schedules(self) -> list[ScheduleRecord]:
        """Return recurring schedules (requires ``Capability.SCHEDULES``)."""
        raise NotImplementedError

    async def retry_task(self, task_id: str, *, actor: str) -> None:
        """Re-enqueue a failed task (requires ``Capability.RETRY``)."""

    async def cancel_task(self, task_id: str, *, actor: str) -> None:
        """Cancel a pending task (requires ``Capability.CANCEL``)."""

    async def set_queue_paused(self, queue: str, paused: bool, *, actor: str) -> None:
        """Pause or resume a queue (requires ``Capability.PAUSE_QUEUE``)."""

    async def set_schedule_paused(self, schedule_id: str, paused: bool, *, actor: str) -> None:
        """Pause or resume a schedule (requires ``Capability.PAUSE_SCHEDULE``)."""


def require_capability(backend: TaskBackend, capability: Capability) -> None:
    """Raise ``TasksBackendError`` naming ``capability`` unless ``backend`` supports it."""
    if capability not in backend.capabilities:
        raise TasksBackendError(
            f"backend {type(backend).__name__} does not support capability '{capability.value}'"
        )
