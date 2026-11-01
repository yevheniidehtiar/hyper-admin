"""Route tests for the workers and schedules pages (story #757) over the in-memory backend."""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest
from fastapi import FastAPI, Header
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import create_async_engine

from hyperadmin import Admin
from hyperadmin.auth.bridge import ExternalAuth
from hyperadmin.core.plugins import PluginRegistry
from hyperadmin.core.settings import HyperAdminSettings
from hyperadmin_tasks.backend import Capability, ScheduleRecord, TasksBackendError, WorkerRecord
from hyperadmin_tasks.backends.memory import InMemoryTaskBackend
from hyperadmin_tasks.plugin import TasksPlugin
from hyperadmin_tasks.presenters import format_utc

ClientFactory = Callable[..., TestClient]


class _FailingBackend(InMemoryTaskBackend):
    async def list_workers(self) -> Any:
        raise TasksBackendError("connection refused")

    async def list_schedules(self) -> Any:
        raise TasksBackendError("connection refused")


def _worker(worker_id: str, now: datetime, *, healthy: bool = True) -> WorkerRecord:
    return WorkerRecord(
        id=worker_id,
        queues=("default", "emails"),
        task_names=("app.job",),
        last_seen_at=now if healthy else now - timedelta(hours=2),
        concurrency=4,
        healthy=healthy,
    )


def test_workers_listed_with_stale_one_unhealthy(make_client: ClientFactory, now: datetime) -> None:
    """
    Scenario: workers listed
      Given two live workers and one stale
      When  the user opens /admin/tasks/workers
      Then  three rows are shown and the stale one is marked unhealthy
    """
    backend = InMemoryTaskBackend(clock=lambda: now)
    backend.seed(
        workers=[_worker("w1", now), _worker("w2", now), _worker("w3", now, healthy=False)]
    )
    client = make_client(backend)

    response = client.get("/admin/tasks/workers")

    assert response.status_code == 200
    assert response.text.count('data-testid="tasks-worker-row"') == 3
    assert response.text.count(">unhealthy</span>") == 1
    assert response.text.count(">healthy</span>") == 2
    assert "2026-11-01 12:00:00 UTC" in response.text
    assert "default, emails" in response.text


def test_workers_page_without_workers_shows_empty_state(
    make_client: ClientFactory, now: datetime
) -> None:
    """
    Scenario: no workers reported
      Given a backend that has seen no workers
      When  the user opens /admin/tasks/workers
      Then  an empty-state message is shown instead of a table
    """
    client = make_client(InMemoryTaskBackend(clock=lambda: now))

    response = client.get("/admin/tasks/workers")

    assert response.status_code == 200
    assert 'data-testid="tasks-workers-empty"' in response.text
    assert 'data-testid="tasks-worker-row"' not in response.text


def test_schedules_listed_with_cron_next_run_and_policy(
    make_client: ClientFactory, now: datetime
) -> None:
    """
    Scenario: schedules listed
      Given a cron schedule "0 0 * * * *" and a paused one without a next run
      When  the user opens /admin/tasks/schedules
      Then  it shows cron, next run (UTC) and misfire policy
    """
    backend = InMemoryTaskBackend(clock=lambda: now)
    backend.seed(
        schedules=[
            ScheduleRecord(
                id="s1",
                task_name="app.hourly",
                queue="default",
                cron="0 0 * * * *",
                next_run_at=datetime(2026, 11, 1, 13, 0, tzinfo=timezone(timedelta(hours=1))),
                misfire_policy="run_once",
            ),
            ScheduleRecord(
                id="s2",
                task_name="app.nightly",
                queue="default",
                cron="0 3 * * * *",
                misfire_policy="skip",
                paused=True,
            ),
        ]
    )
    client = make_client(backend)

    response = client.get("/admin/tasks/schedules")

    assert response.status_code == 200
    assert response.text.count('data-testid="tasks-schedule-row"') == 2
    assert "0 0 * * * *" in response.text
    assert "2026-11-01 12:00:00 UTC" in response.text
    assert "run_once" in response.text
    assert ">paused</span>" in response.text
    assert ">active</span>" in response.text


def test_schedules_page_without_schedules_shows_empty_state(
    make_client: ClientFactory, now: datetime
) -> None:
    """
    Scenario: no schedules defined
      Given a backend without schedules
      When  the user opens /admin/tasks/schedules
      Then  an empty-state message is shown instead of a table
    """
    client = make_client(InMemoryTaskBackend(clock=lambda: now))

    response = client.get("/admin/tasks/schedules")

    assert 'data-testid="tasks-schedules-empty"' in response.text


@pytest.mark.parametrize(
    ("path", "missing"),
    [
        ("/admin/tasks/workers", Capability.WORKERS),
        ("/admin/tasks/schedules", Capability.SCHEDULES),
    ],
)
def test_page_is_not_found_when_backend_lacks_capability(
    make_client: ClientFactory, now: datetime, path: str, missing: Capability
) -> None:
    """
    Scenario: page hidden without the capability
      Given a backend without WORKERS (resp. SCHEDULES)
      When  the user opens the page directly
      Then  a 404 card links back to the task list
    """
    capabilities = set(Capability) - {missing}
    client = make_client(InMemoryTaskBackend(capabilities, clock=lambda: now))

    response = client.get(path)

    assert response.status_code == 404
    assert 'data-testid="tasks-not-found"' in response.text
    assert 'data-testid="tasks-back-to-list"' in response.text


@pytest.mark.parametrize("path", ["/admin/tasks/workers", "/admin/tasks/schedules"])
def test_backend_failure_shows_inline_banner(
    make_client: ClientFactory, now: datetime, path: str
) -> None:
    """
    Scenario: backend outage
      Given a backend whose queries raise
      When  the user opens the page
      Then  the page renders with an inline error banner and no rows
    """
    client = make_client(_FailingBackend(clock=lambda: now))

    response = client.get(path)

    assert response.status_code == 200
    assert 'data-testid="tasks-backend-error"' in response.text


def test_pages_require_view_permission(tmp_path: Path) -> None:
    """
    Scenario: user without view_tasks is denied both pages
      Given an admin with auth where the user lacks view_tasks
      When  GET /admin/tasks/workers or /admin/tasks/schedules
      Then  response is 403 with the plugin's card
      And   a user holding it gets 200
    """

    def get_user(authorization: str | None = Header(default=None)) -> Any:
        known = {"Bearer allowed": "allowed", "Bearer denied": "denied"}
        return (
            SimpleNamespace(id=known[authorization], name=known[authorization], is_staff=True)
            if authorization in known
            else None
        )

    def has_permission(user: Any, codename: str) -> bool:
        return user.name == "allowed" and codename == "view_tasks"

    app = FastAPI()
    Admin(
        app,
        engine=create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'auth.db'}"),
        settings=HyperAdminSettings(secret_key="tasks-test-secret"),
        auth=ExternalAuth(get_user=get_user, has_permission=has_permission),
    ).mount("/admin")
    client = TestClient(app, follow_redirects=False)

    for path in ("/admin/tasks/workers", "/admin/tasks/schedules"):
        denied = client.get(path, headers={"Authorization": "Bearer denied"})
        allowed = client.get(path, headers={"Authorization": "Bearer allowed"})

        assert denied.status_code == 403
        assert 'data-testid="tasks-forbidden"' in denied.text
        assert allowed.status_code == 200


@pytest.mark.parametrize(
    ("capabilities", "workers_nav", "schedules_nav"),
    [
        (set(Capability), True, True),
        (set(Capability) - {Capability.SCHEDULES}, True, False),
        (set(Capability) - {Capability.WORKERS}, False, True),
    ],
)
def test_nav_entries_follow_backend_capabilities(
    monkeypatch: pytest.MonkeyPatch,
    capabilities: set[Capability],
    workers_nav: bool,
    schedules_nav: bool,
) -> None:
    """
    Scenario: capability hidden
      Given a backend with or without WORKERS and SCHEDULES
      When  the tasks plugin is registered
      Then  a Workers (Schedules) nav entry exists only when the capability is present
    """
    backend = InMemoryTaskBackend(capabilities)
    monkeypatch.setattr("hyperadmin_tasks.plugin.select_backend", lambda settings: backend)
    registry = PluginRegistry()

    assert registry.register(TasksPlugin(), admin=SimpleNamespace(plugins=registry))

    urls = {entry.url_name for entry in registry.nav_entries}
    assert ("tasks-workers" in urls) is workers_nav
    assert ("tasks-schedules" in urls) is schedules_nav
    assert "tasks-dashboard" in urls


def test_format_utc_handles_none_naive_and_offset_values() -> None:
    """
    Scenario: timestamps are rendered in UTC
      Given a missing, a naive and an offset-aware datetime
      When  format_utc is called
      Then  None stays None, naive is taken as UTC and offsets are converted
    """
    offset = datetime(2026, 11, 1, 13, 0, tzinfo=timezone(timedelta(hours=1)))

    assert format_utc(None) is None
    assert format_utc(datetime(2026, 11, 1, 12, 0)) == "2026-11-01 12:00:00 UTC"
    assert format_utc(offset) == "2026-11-01 12:00:00 UTC"
    assert format_utc(datetime(2026, 11, 1, 12, 0, tzinfo=UTC)) == "2026-11-01 12:00:00 UTC"
