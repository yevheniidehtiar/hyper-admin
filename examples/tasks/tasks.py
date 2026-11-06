"""The example's pgtask task handlers and its cron schedule.

``registry`` is what the in-process worker runs (``HYPERADMIN_TASKS_REGISTRIES`` or
``hyperadmin_tasks.lifespan(admin, registries=[registry])``):

- ``reports.generate`` builds a report and marks it ready.
- ``reports.deliver`` posts it to a webhook that is down for every automatic attempt, so the
  task retries, fails, and then succeeds when you press Retry in ``/admin/tasks``.
- ``reports.digest`` runs once a minute from the ``reports-digest`` cron schedule.
"""

from __future__ import annotations

import asyncio
import uuid
from typing import TYPE_CHECKING, Any

from pgtask import TaskRegistry
from sqlalchemy import func, select

from examples.tasks.db import Session
from examples.tasks.models import Report, ReportStatus

if TYPE_CHECKING:
    from pgtask import Task
    from psycopg import AsyncConnection

QUEUE = "default"
#: Seconds ``reports.generate`` pretends to work, long enough to see the task running.
GENERATE_SECONDS = 2.0
#: Automatic attempts of ``reports.deliver``; every one of them fails.
DELIVER_ATTEMPTS = 3
DIGEST_SCHEDULE_ID = uuid.UUID("5f0c3a52-7d2e-4c41-9a43-3b7f5d1e0a01")
DIGEST_SCHEDULE_NAME = "reports-digest"
#: pgtask cron expressions have six fields, seconds first. A five-field expression is stored but
#: never fires.
DIGEST_CRON = "0 * * * * *"

registry = TaskRegistry(QUEUE)


class WebhookDownError(RuntimeError):
    """The pretend delivery endpoint refused the report."""


async def set_status(report_id: int, status: ReportStatus, **fields: Any) -> None:
    """Commit ``status`` (and any other ``fields``) on report ``report_id``."""
    async with Session.begin() as session:
        report = await session.get(Report, report_id)
        if report is not None:
            report.status = status
            for name, value in fields.items():
                setattr(report, name, value)


@registry.task("reports.generate")
async def generate(task: Task, payload: dict[str, int]) -> dict[str, int]:
    """Build the report: count the rows it covers and mark it ready."""
    await asyncio.sleep(GENERATE_SECONDS)
    async with Session() as session:
        rows = await session.scalar(select(func.count()).select_from(Report)) or 0
    await set_status(payload["report_id"], ReportStatus.READY, row_count=rows)
    return {"report_id": payload["report_id"], "row_count": rows}


@registry.task("reports.deliver", retry_delay=2.0)
async def deliver(task: Task, payload: dict[str, int]) -> str:
    """Post the report to a webhook that only comes back after the automatic attempts.

    A retry from the dashboard runs after ``DELIVER_ATTEMPTS`` failures, so it succeeds.
    """
    if task.failed_attempts < DELIVER_ATTEMPTS:
        raise WebhookDownError(f"webhook unavailable (attempt {task.attempt})")
    await set_status(payload["report_id"], ReportStatus.DELIVERED)
    return "delivered"


@registry.task("reports.digest")
async def digest(task: Task, payload: dict[str, Any]) -> dict[str, int]:
    """Count reports by status; the cron schedule runs this once a minute."""
    async with Session() as session:
        rows = await session.execute(select(Report.status, func.count()).group_by(Report.status))
        return {status.value: count for status, count in rows.tuples()}


async def put_digest_schedule(connection: AsyncConnection[Any]) -> None:
    """Create the ``reports-digest`` cron schedule (pgtask has no Python API for it).

    ``put_schedule`` upserts by name and leaves an unchanged schedule alone, so a restart keeps
    it (and a pause set from the dashboard). The first run is the next minute boundary.
    """
    await connection.execute(
        "SELECT pgtask.put_schedule(%s, %s, 'cron', NULL, %s, 'skip', NULL, %s, 'reports.digest', "
        "1, '{}'::jsonb, '{}'::jsonb, 0::smallint, 1, "
        "date_trunc('minute', now()) + interval '1 minute')",
        (DIGEST_SCHEDULE_ID, DIGEST_SCHEDULE_NAME, DIGEST_CRON, QUEUE),
    )
