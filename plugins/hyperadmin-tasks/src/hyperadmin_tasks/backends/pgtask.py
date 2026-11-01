# ruff: noqa: ARG002  (action stubs keep the TaskBackend signatures; they only gate on capability)
"""Read-side ``TaskBackend`` over pgtask's security-barrier observer views (experimental).

Only this module and ``_pgtask_columns`` know pgtask's storage layout. Reads run on the
observer-role DSN through one autocommit psycopg connection; every query is parameterised.
Action capabilities (retry, cancel, pauses) are added by the actions adapter story.
"""

from __future__ import annotations

import asyncio
import logging
import uuid
from collections.abc import Awaitable, Callable, Sequence
from typing import TYPE_CHECKING, Any, Protocol

import psycopg
from psycopg.rows import dict_row

from hyperadmin_tasks.backend import (
    AttemptRecord,
    Capability,
    Page,
    QueueStats,
    ScheduleRecord,
    TaskFilter,
    TaskRecord,
    TasksBackendError,
    WorkerRecord,
    require_capability,
)
from hyperadmin_tasks.backends import _pgtask_columns as columns

if TYPE_CHECKING:
    from hyperadmin_tasks.settings import TasksSettings

logger = logging.getLogger(__name__)

Row = dict[str, Any]


class _Cursor(Protocol):
    async def fetchall(self) -> list[Row]: ...


class _Connection(Protocol):
    @property
    def closed(self) -> bool: ...

    async def execute(self, query: str, params: Sequence[Any] | None = None) -> _Cursor: ...

    async def close(self) -> None: ...


Connector = Callable[[], Awaitable[_Connection]]


class PgTaskBackend:
    """Monitor a pgtask database through its observer views."""

    capabilities: frozenset[Capability] = frozenset({Capability.WORKERS, Capability.SCHEDULES})

    def __init__(self, observer_dsn: str, *, connector: Connector | None = None) -> None:
        self._connector: Connector = connector or (lambda: _open(observer_dsn))
        self._connection: _Connection | None = None
        self._lock = asyncio.Lock()

    async def startup(self) -> None:
        """Open the observer connection; fails fast on a bad DSN or an unreachable server."""
        async with self._lock:
            await self._ensure_connection()

    async def shutdown(self) -> None:
        """Close the observer connection."""
        async with self._lock:
            connection, self._connection = self._connection, None
            if connection is not None and not connection.closed:
                await connection.close()

    async def list_queues(self) -> list[QueueStats]:
        """Return counters for every queue (``queue_overview`` plus ``task_view`` aggregates)."""
        overview = await self._rows(columns.QUEUES_SQL)
        counts = await self._rows(columns.QUEUE_TASK_COUNTS_SQL)
        return columns.queue_stats_from_rows(overview, counts)

    async def list_tasks(self, flt: TaskFilter, page: int, per_page: int) -> Page[TaskRecord]:
        """Return one page of tasks matching ``flt``, newest first, with an exact total."""
        if page < 1 or per_page < 1:
            raise TasksBackendError("page and per_page must be >= 1")
        sql, params = columns.tasks_page_sql(flt, page, per_page)
        count_sql, count_params = columns.tasks_count_sql(flt)
        rows = await self._rows(sql, params)
        total = (await self._rows(count_sql, count_params))[0]["total"]
        return Page[TaskRecord](
            items=[columns.task_from_row(row) for row in rows],
            page=page,
            per_page=per_page,
            total=total,
        )

    async def get_task(self, task_id: str) -> tuple[TaskRecord, list[AttemptRecord]] | None:
        """Return a task with its attempts, or ``None`` for an unknown or malformed id."""
        try:
            key = uuid.UUID(task_id)
        except ValueError:
            return None
        rows = await self._rows(columns.TASK_BY_ID_SQL, [key])
        if not rows:
            return None
        attempts = await self._rows(columns.ATTEMPTS_SQL, [key])
        return columns.task_from_row(rows[0]), [columns.attempt_from_row(a) for a in attempts]

    async def list_workers(self) -> list[WorkerRecord]:
        """Return the workers pgtask knows about, most recently seen first."""
        workers = await self._rows(columns.WORKERS_SQL)
        capabilities = await self._rows(columns.WORKER_TASK_NAMES_SQL)
        return columns.workers_from_rows(workers, capabilities)

    async def list_schedules(self) -> list[ScheduleRecord]:
        """Return the recurring schedules."""
        return [columns.schedule_from_row(row) for row in await self._rows(columns.SCHEDULES_SQL)]

    async def retry_task(self, task_id: str, *, actor: str) -> None:
        """Unsupported on the read-side adapter."""
        require_capability(self, Capability.RETRY)

    async def cancel_task(self, task_id: str, *, actor: str) -> None:
        """Unsupported on the read-side adapter."""
        require_capability(self, Capability.CANCEL)

    async def set_queue_paused(self, queue: str, paused: bool, *, actor: str) -> None:
        """Unsupported on the read-side adapter."""
        require_capability(self, Capability.PAUSE_QUEUE)

    async def set_schedule_paused(self, schedule_id: str, paused: bool, *, actor: str) -> None:
        """Unsupported on the read-side adapter."""
        require_capability(self, Capability.PAUSE_SCHEDULE)

    async def _ensure_connection(self) -> _Connection:
        if self._connection is None or self._connection.closed:
            try:
                self._connection = await self._connector()
            except psycopg.Error as exc:
                raise TasksBackendError(f"cannot connect to the pgtask database: {exc}") from exc
        return self._connection

    async def _rows(self, query: str, params: Sequence[Any] | None = None) -> list[Row]:
        async with self._lock:
            connection = await self._ensure_connection()
            try:
                cursor = await connection.execute(query, params)
                return await cursor.fetchall()
            except psycopg.Error as exc:
                raise TasksBackendError(f"pgtask query failed: {exc}") from exc


async def _open(dsn: str) -> _Connection:
    return await psycopg.AsyncConnection.connect(dsn, autocommit=True, row_factory=dict_row)


def create_backend(settings: TasksSettings) -> PgTaskBackend:
    """Build the adapter from settings; ``observer_dsn`` falls back to ``dsn`` with a warning."""
    dsn = settings.observer_dsn
    if dsn is None:
        if settings.dsn is None:
            raise TasksBackendError(
                "the pgtask backend needs HYPERADMIN_TASKS_OBSERVER_DSN (or HYPERADMIN_TASKS_DSN)"
            )
        logger.warning(
            "HYPERADMIN_TASKS_OBSERVER_DSN is not set; reading with HYPERADMIN_TASKS_DSN. "
            "Use a read-only observer role."
        )
        dsn = settings.dsn
    return PgTaskBackend(dsn)
