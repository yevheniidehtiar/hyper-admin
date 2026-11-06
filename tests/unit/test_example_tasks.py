"""Unit tests for ``examples/tasks``: the flaky delivery task and the enqueue-in-transaction action.

The example imports pgtask, which only ``uv sync --all-packages`` installs, so the module is
skipped without it. ``examples.tasks.admin`` registers ``Report`` on the global ``site``, so the
``example`` fixture imports it lazily and restores the registry afterwards.
"""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import asynccontextmanager
from types import SimpleNamespace
from typing import Any

import pytest

from hyperadmin.core.registry import site

# ``pgtask.client``, not ``pgtask``: without the extra, the plugin's ``tests/pgtask/`` directory can
# resolve as a ``pgtask`` namespace package once it is on sys.path.
pytest.importorskip("pgtask.client")

pytestmark = pytest.mark.anyio


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


@pytest.fixture(scope="module")
def example() -> Iterator[SimpleNamespace]:
    """Import the example's modules once, then restore the global ``site`` registry."""
    saved = dict(site._registry)
    from examples.tasks import admin, db, models, tasks

    try:
        yield SimpleNamespace(admin=admin, db=db, models=models, tasks=tasks)
    finally:
        site._registry = saved


@pytest.mark.parametrize(
    ("url", "expected"),
    [
        ("postgresql://u:p@db:5432/tasks", "postgresql+psycopg://u:p@db:5432/tasks"),
        ("postgres://u@db/tasks", "postgresql+psycopg://u@db/tasks"),
        ("postgresql+psycopg://u@db/tasks", "postgresql+psycopg://u@db/tasks"),
    ],
)
def test_sqlalchemy_url_uses_the_psycopg_driver(
    example: SimpleNamespace, url: str, expected: str
) -> None:
    """
    Scenario: the engine URL suits enqueue_in_session
      Given a plain postgresql:// DATABASE_URL
      When  the example builds its SQLAlchemy URL
      Then  the URL uses the postgresql+psycopg driver
    """
    assert example.db.sqlalchemy_url(url) == expected


@pytest.fixture
def statuses(example: SimpleNamespace, monkeypatch: pytest.MonkeyPatch) -> list[tuple[Any, ...]]:
    """Record ``set_status`` calls instead of writing to a database."""
    calls: list[tuple[Any, ...]] = []

    async def set_status(report_id: int, status: Any, **fields: Any) -> None:
        calls.append((report_id, status, fields))

    monkeypatch.setattr(example.tasks, "set_status", set_status)
    return calls


@pytest.mark.parametrize("failed_attempts", [0, 1, 2])
async def test_deliver_fails_every_automatic_attempt(
    example: SimpleNamespace, statuses: list[Any], failed_attempts: int
) -> None:
    """
    Scenario: failure demo
      Given the flaky reports.deliver task with max_attempts=3
      When  the worker runs one of its automatic attempts
      Then  the task raises, so pgtask retries it and finally marks it failed
    """
    task = SimpleNamespace(attempt=failed_attempts + 1, failed_attempts=failed_attempts)

    with pytest.raises(example.tasks.WebhookDownError, match="webhook unavailable"):
        await example.tasks.deliver.handler(task, {"report_id": 7})

    assert statuses == []


async def test_deliver_succeeds_when_retried_from_the_dashboard(
    example: SimpleNamespace, statuses: list[Any]
) -> None:
    """
    Scenario: retry from the UI
      Given reports.deliver failed all of its automatic attempts
      When  an operator presses Retry in /admin/tasks
      Then  the next run succeeds and the report is marked delivered
    """
    task = SimpleNamespace(attempt=4, failed_attempts=example.tasks.DELIVER_ATTEMPTS)

    assert await example.tasks.deliver.handler(task, {"report_id": 7}) == "delivered"
    assert statuses == [(7, example.models.ReportStatus.DELIVERED, {})]


class _FakeSession:
    def __init__(self, report: Any) -> None:
        self.report = report

    async def get(self, model: Any, pk: int) -> Any:
        return self.report


@pytest.fixture
def action_session(example: SimpleNamespace, monkeypatch: pytest.MonkeyPatch) -> SimpleNamespace:
    """Replace the example's session factory and ``enqueue_in_session`` with recorders."""
    state = SimpleNamespace(report=None, enqueued=[])

    @asynccontextmanager
    async def begin() -> Any:
        yield _FakeSession(state.report)

    async def enqueue_in_session(session: Any, request: Any) -> str:
        state.enqueued.append((session, request))
        return "task-1"

    monkeypatch.setattr(example.admin, "Session", SimpleNamespace(begin=begin))
    monkeypatch.setattr(example.admin, "enqueue_in_session", enqueue_in_session)
    return state


async def test_generate_report_queues_the_task_and_marks_the_report(
    example: SimpleNamespace, action_session: SimpleNamespace
) -> None:
    """
    Scenario: example app end-to-end (enqueue half)
      Given a draft report
      When  the operator runs "Generate report" on it
      Then  reports.generate is enqueued on the action's session
      And   the report is marked queued in the same transaction
    """
    report = SimpleNamespace(status=example.models.ReportStatus.DRAFT)
    action_session.report = report
    request = example.tasks.generate.request({"report_id": 1})

    await example.admin.enqueue_for(1, request, status=example.models.ReportStatus.QUEUED)

    [(session, enqueued)] = action_session.enqueued
    assert session.report is report
    assert (enqueued.task_name, enqueued.payload) == ("reports.generate", {"report_id": 1})
    assert report.status is example.models.ReportStatus.QUEUED


async def test_enqueue_for_a_missing_report_enqueues_nothing(
    example: SimpleNamespace, action_session: SimpleNamespace
) -> None:
    """
    Scenario: the report was deleted
      Given no report with the action's id
      When  an action calls enqueue_for
      Then  no task is enqueued
    """
    request = example.tasks.deliver.request({"report_id": 99})

    await example.admin.enqueue_for(99, request)

    assert action_session.enqueued == []
