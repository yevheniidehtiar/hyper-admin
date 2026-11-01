# ruff: noqa: S608  (SQL is assembled from module constants; user values are bind parameters)
"""Everything the pgtask adapter knows about pgtask's observer views, in one place.

pgtask documents the observer view columns as *not* a stability contract (only its SQL function
signatures are), so view names, column names, native state names and the row-to-model mapping
live here and nowhere else (CONSTITUTION section 6). Targets ``pgtask>=0.4,<0.5``.

This module imports neither ``pgtask`` nor ``psycopg``: it holds SQL text (constants and
parameterised fragments; user values only ever travel as bind parameters) and pure functions
over plain ``dict`` rows, which keeps the mapping unit-testable without a database.
"""

from __future__ import annotations

import json
from collections import defaultdict
from datetime import timedelta  # noqa: TC003 - used in annotations of runtime-checked callables
from typing import Any

from hyperadmin_tasks.backend import (
    AttemptRecord,
    QueueStats,
    ScheduleRecord,
    TaskFilter,
    TaskRecord,
    TasksBackendError,
    TaskState,
    WorkerRecord,
)

Row = dict[str, Any]

QUEUE_VIEW = "pgtask.queue_overview"
TASK_VIEW = "pgtask.task_view"
ATTEMPT_VIEW = "pgtask.attempt_view"
WORKER_VIEW = "pgtask.worker_view"
WORKER_CAPABILITY_VIEW = "pgtask.worker_capability_view"
SCHEDULE_VIEW = "pgtask.schedule_view"

#: pgtask native task state -> normalised state. ``scheduled`` is derived by ``TASK_STATE_SQL``.
NATIVE_STATES: dict[str, TaskState] = {
    "pending": TaskState.PENDING,
    "scheduled": TaskState.SCHEDULED,
    "running": TaskState.RUNNING,
    "waiting": TaskState.WAITING,
    "succeeded": TaskState.SUCCEEDED,
    "failed": TaskState.FAILED,
    "cancelled": TaskState.CANCELLED,
}

#: A pending task whose ``run_at`` lies in the future is reported as ``scheduled``.
TASK_STATE_SQL = (
    "CASE WHEN state = 'pending' AND run_at > now() THEN 'scheduled' ELSE state END AS state"
)

#: SQL predicate per normalised state. pgtask has no ``sleeping`` state (durable sleeps are
#: ``waiting``), so that filter matches nothing.
STATE_PREDICATES: dict[TaskState, str] = {
    TaskState.PENDING: "(state = 'pending' AND run_at <= now())",
    TaskState.SCHEDULED: "(state = 'pending' AND run_at > now())",
    TaskState.RUNNING: "state = 'running'",
    TaskState.SLEEPING: "FALSE",
    TaskState.WAITING: "state = 'waiting'",
    TaskState.SUCCEEDED: "state = 'succeeded'",
    TaskState.FAILED: "state = 'failed'",
    TaskState.CANCELLED: "state = 'cancelled'",
}

TASK_COLUMNS = (
    "id::text AS id, queue_name, task_name, " + TASK_STATE_SQL + ", priority, attempt, "
    "max_attempts, created_at, run_at, completed_at, payload, result, error, "
    "parent_task_id::text AS parent_id"
)

QUEUES_SQL = (
    "SELECT name, paused_at, running_count, ready_count FROM " + QUEUE_VIEW + " ORDER BY name"
)

#: ``queue_overview`` lacks failed / succeeded / scheduled counters; they come from ``task_view``.
QUEUE_TASK_COUNTS_SQL = (
    "SELECT queue_name, "
    "count(*) FILTER (WHERE state = 'failed') AS failed_count, "
    "count(*) FILTER (WHERE state = 'succeeded') AS succeeded_count, "
    "count(*) FILTER (WHERE state = 'pending' AND run_at > now()) AS scheduled_count, "
    "now() - min(run_at) FILTER (WHERE state = 'pending' AND run_at <= now()) AS oldest_ready "
    "FROM " + TASK_VIEW + " GROUP BY queue_name"
)

TASK_BY_ID_SQL = "SELECT " + TASK_COLUMNS + " FROM " + TASK_VIEW + " WHERE id = %s"

ATTEMPTS_SQL = (
    "SELECT attempt, worker_id::text AS worker_id, state, started_at, finished_at, error "
    "FROM " + ATTEMPT_VIEW + " WHERE task_id = %s ORDER BY attempt"
)

WORKERS_SQL = (
    "SELECT id::text AS id, queue_name, heartbeat_at, live FROM "
    + WORKER_VIEW
    + " ORDER BY heartbeat_at DESC, id"
)

WORKER_TASK_NAMES_SQL = (
    "SELECT worker_id::text AS worker_id, task_name FROM "
    + WORKER_CAPABILITY_VIEW
    + " ORDER BY task_name"
)

SCHEDULES_SQL = (
    "SELECT id::text AS id, kind, cron_expression, interval_milliseconds, misfire_policy, "
    "queue_name, task_name, next_run_at, paused_at FROM " + SCHEDULE_VIEW + " ORDER BY name"
)


def tasks_page_sql(flt: TaskFilter, page: int, per_page: int) -> tuple[str, list[Any]]:
    """Return the SQL and bind parameters of one page of tasks matching ``flt``."""
    where, params = task_where(flt)
    sql = (
        f"SELECT {TASK_COLUMNS} FROM {TASK_VIEW}{where} "
        "ORDER BY created_at DESC, id LIMIT %s OFFSET %s"
    )
    return sql, [*params, per_page, (page - 1) * per_page]


def tasks_count_sql(flt: TaskFilter) -> tuple[str, list[Any]]:
    """Return the SQL and bind parameters counting the tasks matching ``flt``."""
    where, params = task_where(flt)
    return f"SELECT count(*) AS total FROM {TASK_VIEW}{where}", params


def task_where(flt: TaskFilter) -> tuple[str, list[Any]]:
    """Return a ``WHERE`` clause (empty without filters) and its bind parameters."""
    clauses: list[str] = []
    params: list[Any] = []
    if flt.queue is not None:
        clauses.append("queue_name = %s")
        params.append(flt.queue)
    if flt.state is not None:
        clauses.append(STATE_PREDICATES[flt.state])
    if flt.name is not None:
        clauses.append("task_name = %s")
        params.append(flt.name)
    if flt.id_query is not None:
        clauses.append("id::text ILIKE %s")
        params.append(like_pattern(flt.id_query))
    return (" WHERE " + " AND ".join(clauses) if clauses else ""), params


def like_pattern(text: str) -> str:
    """Return a contains-pattern for ``ILIKE`` with LIKE wildcards in ``text`` escaped."""
    escaped = text.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
    return f"%{escaped}%"


def error_text(value: Any) -> str | None:
    """Render pgtask's JSON error (``{"type", "message", "retryable"}``) as one line of text."""
    if value is None:
        return None
    if isinstance(value, dict) and isinstance(value.get("message"), str):
        return str(value["message"])
    if isinstance(value, str):
        return value
    return json.dumps(value, sort_keys=True)


def task_from_row(row: Row) -> TaskRecord:
    """Map one ``task_view`` row (selected with ``TASK_COLUMNS``) to a ``TaskRecord``."""
    return TaskRecord(
        id=row["id"],
        queue=row["queue_name"],
        name=row["task_name"],
        state=_task_state(row["state"]),
        priority=row["priority"],
        attempt=row["attempt"],
        max_attempts=row["max_attempts"],
        created_at=row["created_at"],
        run_at=row["run_at"],
        finished_at=row["completed_at"],
        payload=row["payload"],
        result=row["result"],
        error=error_text(row["error"]),
        parent_id=row["parent_id"],
    )


def _task_state(native: str) -> TaskState:
    try:
        return NATIVE_STATES[native]
    except KeyError:
        raise TasksBackendError(f"unknown pgtask task state '{native}'") from None


def attempt_from_row(row: Row) -> AttemptRecord:
    """Map one ``attempt_view`` row to an ``AttemptRecord`` (outcome is the native state)."""
    return AttemptRecord(
        number=row["attempt"],
        worker_id=row["worker_id"],
        started_at=row["started_at"],
        finished_at=row["finished_at"],
        outcome=row["state"],
        error=error_text(row["error"]),
    )


def queue_stats_from_rows(overview: list[Row], counts: list[Row]) -> list[QueueStats]:
    """Combine ``queue_overview`` rows with the per-queue ``task_view`` aggregates."""
    by_queue = {row["queue_name"]: row for row in counts}
    stats: list[QueueStats] = []
    for row in overview:
        extra = by_queue.get(row["name"])
        oldest: timedelta | None = extra["oldest_ready"] if extra else None
        stats.append(
            QueueStats(
                name=row["name"],
                ready=row["ready_count"],
                running=row["running_count"],
                scheduled=extra["scheduled_count"] if extra else 0,
                failed=extra["failed_count"] if extra else 0,
                succeeded_recent=extra["succeeded_count"] if extra else 0,
                oldest_ready_age=oldest,
                paused=row["paused_at"] is not None,
            )
        )
    return stats


def workers_from_rows(workers: list[Row], capabilities: list[Row]) -> list[WorkerRecord]:
    """Combine ``worker_view`` rows with ``worker_capability_view`` task names.

    pgtask does not record a worker's concurrency, so it is reported as ``0`` (unknown).
    """
    names: dict[str, list[str]] = defaultdict(list)
    for capability in capabilities:
        if capability["task_name"] not in names[capability["worker_id"]]:
            names[capability["worker_id"]].append(capability["task_name"])
    return [
        WorkerRecord(
            id=row["id"],
            queues=(row["queue_name"],),
            task_names=tuple(names[row["id"]]),
            last_seen_at=row["heartbeat_at"],
            concurrency=0,
            healthy=row["live"],
        )
        for row in workers
    ]


def schedule_from_row(row: Row) -> ScheduleRecord:
    """Map one ``schedule_view`` row; interval schedules are rendered as ``every <n>s``."""
    cron = row["cron_expression"]
    if cron is None:
        cron = f"every {row['interval_milliseconds'] / 1000:g}s"
    return ScheduleRecord(
        id=row["id"],
        task_name=row["task_name"],
        queue=row["queue_name"],
        cron=cron,
        next_run_at=row["next_run_at"],
        misfire_policy=row["misfire_policy"],
        paused=row["paused_at"] is not None,
    )
