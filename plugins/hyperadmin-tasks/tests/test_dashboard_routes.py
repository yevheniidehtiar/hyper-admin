"""Route tests for the tasks dashboard (story #754) over the in-memory backend."""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime, timedelta

import anyio
import pytest
from fastapi.testclient import TestClient

from hyperadmin_tasks.backend import (
    Capability,
    TaskRecord,
    TasksBackendError,
    TaskState,
    WorkerRecord,
)
from hyperadmin_tasks.backends.memory import InMemoryTaskBackend
from hyperadmin_tasks.presenters import format_age

ClientFactory = Callable[..., TestClient]
BackendFactory = Callable[..., InMemoryTaskBackend]


@pytest.fixture
def seed_backend(now: datetime, make_task: Callable[..., TaskRecord]) -> BackendFactory:
    def factory(capabilities: set[Capability] | None = None) -> InMemoryTaskBackend:
        backend = InMemoryTaskBackend(capabilities, clock=lambda: now)
        backend.seed(
            [
                make_task("r1", queue="reports", created_at=now - timedelta(minutes=12)),
                make_task("r2", queue="reports", state=TaskState.RUNNING),
                make_task("r3", queue="reports", state=TaskState.FAILED),
                make_task("e1", queue="emails", state=TaskState.SCHEDULED),
            ],
            workers=[
                WorkerRecord(
                    id=worker_id,
                    queues=("reports",),
                    task_names=(),
                    last_seen_at=now,
                    concurrency=2,
                    healthy=healthy,
                )
                for worker_id, healthy in (("w1", True), ("w2", False))
            ],
        )
        return backend

    return factory


class _FailingBackend(InMemoryTaskBackend):
    async def list_queues(self):  # type: ignore[no-untyped-def]
        raise TasksBackendError("connection refused")


def test_dashboard_lists_queues(make_client: ClientFactory, seed_backend: BackendFactory) -> None:
    """
    Scenario: dashboard lists queues
      Given queues reports and emails with tasks
      When  the user opens /admin/tasks
      Then  a row per queue shows ready, running, scheduled, failed counts and oldest-ready age
    """
    client = make_client(seed_backend())

    html = client.get("/admin/tasks/").text

    assert html.count('data-testid="tasks-queue-row"') == 2
    assert 'data-testid="tasks-queue-table"' in html
    assert '<td class="ha-num" data-testid="tasks-queue-ready">1</td>' in html
    assert '<td class="ha-num" data-testid="tasks-queue-running">1</td>' in html
    assert '<td class="ha-num" data-testid="tasks-queue-scheduled">1</td>' in html
    assert '<td class="ha-num" data-testid="tasks-queue-failed">1</td>' in html
    assert '<td class="ha-num" data-testid="tasks-queue-oldest">12m</td>' in html
    assert 'data-testid="tasks-queue-oldest">—</td>' in html


def test_dashboard_shows_active_worker_count(
    make_client: ClientFactory, seed_backend: BackendFactory
) -> None:
    """
    Scenario: active workers are counted
      Given a backend with one healthy and one unhealthy worker
      When  the user opens /admin/tasks
      Then  the active workers count reads 1
    """
    html = make_client(seed_backend()).get("/admin/tasks/").text

    assert 'data-testid="tasks-workers-active">Active workers: 1</p>' in html


def test_dashboard_hides_workers_without_capability(
    make_client: ClientFactory, seed_backend: BackendFactory
) -> None:
    """
    Scenario: workers line is hidden when the backend cannot list workers
      Given a backend without the workers capability
      When  the user opens /admin/tasks
      Then  no active workers count is shown
    """
    html = make_client(seed_backend({Capability.RETRY})).get("/admin/tasks/").text

    assert "tasks-workers-active" not in html
    assert 'data-testid="tasks-queue-table"' in html


def test_dashboard_marks_paused_queue(
    make_client: ClientFactory, seed_backend: BackendFactory
) -> None:
    """
    Scenario: a paused queue is flagged
      Given the reports queue is paused
      When  the user opens /admin/tasks
      Then  the reports row carries a paused pill
    """
    backend = seed_backend()
    client = make_client(backend)
    # Given
    anyio.run(lambda: backend.set_queue_paused("reports", True, actor="t"))

    # When
    html = client.get("/admin/tasks/").text

    # Then
    assert html.count('data-testid="tasks-queue-paused"') == 1


def test_dashboard_without_queues_shows_empty_state(make_client: ClientFactory) -> None:
    """
    Scenario: an empty backend renders an empty state
      Given a backend with no tasks
      When  the user opens /admin/tasks
      Then  the page says there are no queues and shows no table
    """
    html = make_client(InMemoryTaskBackend()).get("/admin/tasks/").text

    assert 'data-testid="tasks-queues-empty"' in html
    assert "tasks-queue-table" not in html


def test_dashboard_auto_refreshes_via_partial(
    make_client: ClientFactory, seed_backend: BackendFactory
) -> None:
    """
    Scenario: auto refresh
      Given refresh_seconds=5 (the default)
      When  the user opens /admin/tasks
      Then  the stats fragment re-fetches ?partial=1 every 5 seconds without a full reload
    """
    html = make_client(seed_backend()).get("/admin/tasks/").text

    assert 'hx-get="http://testserver/admin/tasks/?partial=1"' in html
    assert 'hx-trigger="every 5s"' in html
    assert 'hx-swap="outerHTML"' in html


def test_partial_returns_fragment_only(
    make_client: ClientFactory, seed_backend: BackendFactory
) -> None:
    """
    Scenario: the partial is a bare fragment
      Given queues with tasks
      When  GET /admin/tasks/?partial=1
      Then  the response holds the stats fragment and no page chrome
    """
    response = make_client(seed_backend()).get("/admin/tasks/?partial=1")

    assert response.status_code == 200
    assert response.text.lstrip().startswith('<div id="tasks-queue-stats"')
    assert "<html" not in response.text
    assert response.text.count('data-testid="tasks-queue-row"') == 2


def test_refresh_disabled_when_zero(
    make_client: ClientFactory, seed_backend: BackendFactory, monkeypatch: pytest.MonkeyPatch
) -> None:
    """
    Scenario: auto refresh disabled
      Given refresh_seconds=0
      When  the user opens /admin/tasks
      Then  the stats fragment carries no hx-trigger
    """
    monkeypatch.setenv("HYPERADMIN_TASKS_REFRESH_SECONDS", "0")

    html = make_client(seed_backend()).get("/admin/tasks/").text

    assert "hx-trigger" not in html
    assert 'data-testid="tasks-queue-table"' in html


def test_backend_down_shows_banner(make_client: ClientFactory) -> None:
    """
    Scenario: backend down
      Given the backend raises on list_queues
      When  the user opens /admin/tasks
      Then  an error banner (tasks-backend-error) is shown instead of a 500
    """
    response = make_client(_FailingBackend()).get("/admin/tasks/")

    assert response.status_code == 200
    assert 'data-testid="tasks-backend-error"' in response.text
    assert "tasks-queue-table" not in response.text


def test_backend_down_partial_keeps_refreshing(make_client: ClientFactory) -> None:
    """
    Scenario: the banner fragment keeps polling so the page recovers
      Given the backend raises on list_queues
      When  GET /admin/tasks/?partial=1
      Then  the fragment holds the banner and still carries the refresh trigger
    """
    response = make_client(_FailingBackend()).get("/admin/tasks/?partial=1")

    assert response.status_code == 200
    assert 'data-testid="tasks-backend-error"' in response.text
    assert 'hx-trigger="every 5s"' in response.text


@pytest.mark.parametrize(
    ("seconds", "expected"),
    [
        (None, None),
        (-5, "0s"),
        (45, "45s"),
        (12 * 60, "12m"),
        (3 * 3600 + 5 * 60, "3h 5m"),
        (2 * 86400 + 4 * 3600, "2d 4h"),
    ],
)
def test_format_age(seconds: int | None, expected: str | None) -> None:
    """
    Scenario: ages are rendered compactly
      Given an age of various magnitudes
      When  format_age is called
      Then  the two largest units are shown, negatives clamp to zero and None stays None
    """
    age = None if seconds is None else timedelta(seconds=seconds)

    assert format_age(age) == expected
