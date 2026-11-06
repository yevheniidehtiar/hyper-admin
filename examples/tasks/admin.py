"""Report admin with two actions that enqueue background tasks in the request's transaction."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, ClassVar

from examples.tasks.db import Session
from examples.tasks.models import Report, ReportStatus
from examples.tasks.tasks import DELIVER_ATTEMPTS, deliver, generate
from hyperadmin.adapters.sqlalchemy import SQLAlchemyAdapter
from hyperadmin.core.actions import action
from hyperadmin.core.model import ModelAdmin
from hyperadmin.core.registry import site
from hyperadmin_tasks import enqueue_in_session

if TYPE_CHECKING:
    from fastapi import Request
    from pgtask import EnqueueRequest


async def enqueue_for(
    report_id: int, request: EnqueueRequest[Any], *, status: ReportStatus | None = None
) -> None:
    """Enqueue ``request`` and, when given, set the report's ``status`` in the same transaction.

    If the commit fails, neither the status change nor the task is stored.
    """
    async with Session.begin() as session:
        report = await session.get(Report, report_id)
        if report is None:
            return
        if status is not None:
            report.status = status
        await enqueue_in_session(session, request)


class ReportAdmin(ModelAdmin):
    adapter_class = SQLAlchemyAdapter
    list_display: ClassVar[list[str]] = ["title", "status", "row_count", "updated_at"]
    list_filter: ClassVar[list[str]] = ["status"]

    @action(label="Generate report")
    async def generate_report(self, request: Request, item_id: int) -> None:  # noqa: ARG002
        """Queue ``reports.generate`` for this report and mark it queued."""
        await enqueue_for(
            item_id, generate.request({"report_id": item_id}), status=ReportStatus.QUEUED
        )

    @action(label="Deliver report")
    async def deliver_report(self, request: Request, item_id: int) -> None:  # noqa: ARG002
        """Queue ``reports.deliver``; it fails every automatic attempt (retry it from Tasks)."""
        await enqueue_for(
            item_id, deliver.request({"report_id": item_id}, max_attempts=DELIVER_ATTEMPTS)
        )


site.register(Report, ReportAdmin)
