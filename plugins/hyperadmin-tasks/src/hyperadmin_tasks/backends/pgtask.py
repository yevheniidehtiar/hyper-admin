# ruff: noqa: ARG002  (set_queue_paused keeps the TaskBackend signature; it only gates)
"""``TaskBackend`` over pgtask: observer views for reads, administrator functions for actions.

Only this module and ``_pgtask_columns`` know pgtask's storage layout. Reads run on the
observer-role DSN through one autocommit psycopg connection. Actions (retry, cancel, schedule
pause) run on a second connection opened with the administrator-role DSN and call pgtask's public
``admin_*`` SQL functions, which write ``pgtask.administrator_audit`` with the HyperAdmin actor.
Queue pause is not offered: pgtask's ``set_queue_paused`` takes no actor and leaves no audit row.
Every query is parameterised.
"""

from __future__ import annotations

import asyncio
import logging
import uuid
from collections.abc import Awaitable, Callable, Sequence
from typing import TYPE_CHECKING, Any, Protocol, cast

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


#: Capabilities that need the administrator DSN (audited ``admin_*`` functions only).
ACTION_CAPABILITIES = frozenset({Capability.RETRY, Capability.CANCEL, Capability.PAUSE_SCHEDULE})


class PgTaskBackend:
    """Monitor a pgtask database through its observer views and act through its admin role."""

    capabilities: frozenset[Capability]

    def __init__(
        self,
        observer_dsn: str,
        *,
        admin_dsn: str | None = None,
        connector: Connector | None = None,
        admin_connector: Connector | None = None,
    ) -> None:
        self._connector: Connector = connector or (lambda: _open(observer_dsn))
        self._connection: _Connection | None = None
        self._lock = asyncio.Lock()
        self._admin_connector: Connector | None = admin_connector
        if admin_connector is None and admin_dsn is not None:
            self._admin_connector = lambda: _open(admin_dsn)
        self._admin_connection: _Connection | None = None
        self._admin_lock = asyncio.Lock()
        self.capabilities = frozenset({Capability.WORKERS, Capability.SCHEDULES}) | (
            ACTION_CAPABILITIES if self._admin_connector is not None else frozenset()
        )

    async def startup(self) -> None:
        """Open the observer connection and probe the pgtask schema once.

        Fails fast with ``TasksBackendError`` on a bad DSN, an unreachable server, an unmigrated
        database, an incompatible storage protocol or drifted observer-view columns.
        """
        async with self._lock:
            connection = await self._ensure_connection()
            try:
                await self._probe(connection)
            except TasksBackendError:
                self._connection = None
                await connection.close()
                raise
        if self._admin_connector is not None:
            async with self._admin_lock:
                await self._ensure_admin_connection(self._admin_connector)

    async def shutdown(self) -> None:
        """Close the observer and administrator connections."""
        async with self._lock:
            connection, self._connection = self._connection, None
            if connection is not None and not connection.closed:
                await connection.close()
        async with self._admin_lock:
            admin, self._admin_connection = self._admin_connection, None
            if admin is not None and not admin.closed:
                await admin.close()

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
        """Re-enqueue a failed or cancelled task (``admin_retry_task``, audited as ``actor``)."""
        require_capability(self, Capability.RETRY)
        key = _parse_id(task_id, "task")
        if not await self._admin_call(columns.ADMIN_RETRY_SQL, [key, actor]):
            raise TasksBackendError(
                f"task '{task_id}' cannot be retried: it is unknown or neither failed nor cancelled"
            )

    async def cancel_task(self, task_id: str, *, actor: str) -> None:
        """Cancel a pending, running or waiting task (``admin_cancel_task``, audited)."""
        require_capability(self, Capability.CANCEL)
        key = _parse_id(task_id, "task")
        if not await self._admin_call(columns.ADMIN_CANCEL_SQL, [key, actor]):
            raise TasksBackendError(
                f"task '{task_id}' cannot be cancelled: it is unknown or already finished"
            )

    async def set_queue_paused(self, queue: str, paused: bool, *, actor: str) -> None:
        """Always unsupported: pgtask has no audited queue pause (see the module docstring)."""
        require_capability(self, Capability.PAUSE_QUEUE)

    async def set_schedule_paused(self, schedule_id: str, paused: bool, *, actor: str) -> None:
        """Pause or resume a schedule (``admin_set_schedule_paused``, audited as ``actor``)."""
        require_capability(self, Capability.PAUSE_SCHEDULE)
        key = _parse_id(schedule_id, "schedule")
        if not await self._admin_call(columns.ADMIN_SCHEDULE_PAUSED_SQL, [key, paused, actor]):
            raise TasksBackendError(f"unknown schedule '{schedule_id}'")

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

    async def _ensure_admin_connection(self, connector: Connector) -> _Connection:
        if self._admin_connection is None or self._admin_connection.closed:
            try:
                self._admin_connection = await connector()
            except psycopg.Error as exc:
                raise TasksBackendError(
                    f"cannot connect to the pgtask database as administrator: {exc}"
                ) from exc
        return self._admin_connection

    async def _admin_call(self, query: str, params: Sequence[Any]) -> bool:
        """Run one ``admin_*`` function on the administrator connection; return its result."""
        connector = cast("Connector", self._admin_connector)  # the capability gate ran first
        async with self._admin_lock:
            connection = await self._ensure_admin_connection(connector)
            try:
                cursor = await connection.execute(query, params)
                rows = await cursor.fetchall()
            except psycopg.Error as exc:
                raise TasksBackendError(f"pgtask admin action failed: {exc}") from exc
        return bool(rows[0]["changed"])

    async def _probe(self, connection: _Connection) -> None:
        """Check the storage protocol range and the observer-view columns (startup only)."""
        try:
            cursor = await connection.execute(columns.PROTOCOL_RANGE_SQL)
            protocol = await cursor.fetchall()
        except (psycopg.errors.InvalidSchemaName, psycopg.errors.UndefinedFunction) as exc:
            raise TasksBackendError(columns.NOT_MIGRATED_MESSAGE) from exc
        except psycopg.Error as exc:
            raise TasksBackendError(f"pgtask compatibility probe failed: {exc}") from exc
        problem = columns.protocol_error(protocol)
        if problem is not None:
            raise TasksBackendError(problem)
        try:
            cursor = await connection.execute(
                columns.VIEW_COLUMNS_SQL, [list(columns.REQUIRED_COLUMNS)]
            )
            present = await cursor.fetchall()
        except psycopg.Error as exc:
            raise TasksBackendError(f"pgtask compatibility probe failed: {exc}") from exc
        missing = columns.missing_columns(present)
        if missing:
            raise TasksBackendError(columns.column_drift_error(missing))


def _parse_id(value: str, kind: str) -> uuid.UUID:
    try:
        return uuid.UUID(value)
    except ValueError:
        raise TasksBackendError(f"unknown {kind} '{value}'") from None


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
    return PgTaskBackend(dsn, admin_dsn=settings.dsn)
