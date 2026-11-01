"""Route tests for the retry / cancel / pause / resume actions (story #753)."""

from __future__ import annotations

import re
from collections.abc import Callable
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest
from fastapi import FastAPI, Header
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import create_async_engine

from hyperadmin import Admin
from hyperadmin.auth.bridge import ExternalAuth
from hyperadmin.core.settings import HyperAdminSettings
from hyperadmin_tasks.backend import (
    Capability,
    ScheduleRecord,
    TaskRecord,
    TaskState,
)
from hyperadmin_tasks.backends.memory import InMemoryTaskBackend

ClientFactory = Callable[..., TestClient]
TaskFactory = Callable[..., TaskRecord]

_ACTION_BTN = re.compile(r"tasks-(retry|cancel|queue-pause|queue-resume|schedule-\w+)-btn")
_MANAGER = {"Authorization": "Bearer manager"}
_VIEWER = {"Authorization": "Bearer viewer"}


def _get_user(authorization: str | None = Header(default=None)) -> Any:
    names = {"Bearer manager": "manager", "Bearer viewer": "viewer"}
    return (
        SimpleNamespace(id=names[authorization], username=names[authorization], is_staff=True)
        if authorization in names
        else None
    )


def _has_permission(user: Any, codename: str) -> bool:
    if codename == "view_tasks":
        return True
    return user.username == "manager" and codename == "manage_tasks"


class _ExplodingBackend(InMemoryTaskBackend):
    async def retry_task(self, task_id: str, *, actor: str) -> None:
        raise RuntimeError("pool exhausted")


@pytest.fixture
def backend(now: datetime, make_task: TaskFactory) -> InMemoryTaskBackend:
    store = InMemoryTaskBackend(clock=lambda: now)
    store.seed(
        [
            make_task("F1", queue="reports", state=TaskState.FAILED, error="boom"),
            make_task("P1", queue="reports"),
            make_task("R1", queue="reports", state=TaskState.RUNNING),
        ],
        schedules=[
            ScheduleRecord(
                id="nightly", task_name="app.job", queue="reports", cron="0 3 * * *",
                misfire_policy="skip",
            ),
            ScheduleRecord(
                id="weekly", task_name="app.job", queue="reports", cron="0 4 * * 1",
                misfire_policy="skip", paused=True,
            ),
        ],
    )  # fmt: skip
    return store


@pytest.fixture
def auth_client(tmp_path: Path, backend: InMemoryTaskBackend) -> TestClient:
    """A client for an admin with auth, so CSRF is enforced and permissions are checked."""
    app = FastAPI()
    admin = Admin(
        app,
        engine=create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'auth.db'}"),
        settings=HyperAdminSettings(secret_key="tasks-test-secret"),
        auth=ExternalAuth(get_user=_get_user, has_permission=_has_permission),
    )
    admin.mount("/admin")
    admin.plugins["tasks"].lifecycle.backend = backend  # type: ignore[attr-defined]
    return TestClient(app, follow_redirects=False)


def _csrf(client: TestClient, headers: dict[str, str]) -> dict[str, str]:
    """Headers carrying the CSRF token the admin issued to ``client`` (it keeps the cookie)."""
    page = client.get("/admin/tasks/", headers=headers)
    match = re.search(r'name="csrf-token" content="([^"]+)"', page.text)
    assert match is not None
    return {**headers, "X-CSRF-Token": match.group(1)}


def test_retry_calls_backend_with_username_and_flashes(
    auth_client: TestClient, backend: InMemoryTaskBackend
) -> None:
    """
    Scenario: retry
      Given a failed task and a manage_tasks user
      When  the user clicks Retry and confirms
      Then  retry_task is called with the username as actor and a success flash is shown
    """
    headers = _csrf(auth_client, _MANAGER)
    detail = auth_client.get("/admin/tasks/t/F1", headers=headers).text
    assert 'data-testid="tasks-retry-btn"' in detail
    assert 'hx-confirm="Retry task F1?"' in detail
    assert 'name="csrf_token"' in detail

    response = auth_client.post("/admin/tasks/t/F1/retry", headers=headers)

    assert response.status_code == 303
    assert response.headers["location"] == "/admin/tasks/t/F1?notice=retried"
    assert backend.audit == [("retry_task", "F1", "manager")]
    after = auth_client.get(response.headers["location"], headers=headers).text
    assert 'data-testid="tasks-flash-success"' in after
    assert "queued for retry" in after
    assert 'data-testid="tasks-retry-btn"' not in after


def test_cancel_pending_task(auth_client: TestClient, backend: InMemoryTaskBackend) -> None:
    """
    Scenario: cancel
      Given a pending task and a manage_tasks user
      When  the user cancels it
      Then  cancel_task is called with the username and the success flash is shown
    """
    headers = _csrf(auth_client, _MANAGER)
    detail = auth_client.get("/admin/tasks/t/P1", headers=headers).text
    assert 'data-testid="tasks-cancel-btn"' in detail

    response = auth_client.post("/admin/tasks/t/P1/cancel", headers=headers)

    assert response.headers["location"] == "/admin/tasks/t/P1?notice=cancelled"
    assert backend.audit == [("cancel_task", "P1", "manager")]
    assert "was cancelled" in auth_client.get(response.headers["location"], headers=headers).text


def test_post_without_manage_tasks_is_forbidden(
    auth_client: TestClient, backend: InMemoryTaskBackend
) -> None:
    """
    Scenario: forbidden
      Given a view_tasks-only user
      When  they POST /admin/tasks/t/T1/retry
      Then  403 is returned and nothing changes
    """
    headers = _csrf(auth_client, _VIEWER)

    response = auth_client.post("/admin/tasks/t/F1/retry", headers=headers)

    assert response.status_code == 403
    assert 'data-testid="tasks-forbidden"' in response.text
    assert ">manage_tasks</code>" in response.text
    assert backend.audit == []


def test_post_without_csrf_token_is_rejected(
    auth_client: TestClient, backend: InMemoryTaskBackend
) -> None:
    """
    Scenario: actions are CSRF-protected
      Given a manage_tasks user
      When  they POST an action without the CSRF token
      Then  403 is returned and nothing changes
    """
    response = auth_client.post("/admin/tasks/t/F1/retry", headers=_MANAGER)

    assert response.status_code == 403
    assert backend.audit == []


def test_action_routes_are_post_only(auth_client: TestClient) -> None:
    """
    Scenario: actions cannot be triggered by a link
      Given a manage_tasks user
      When  they GET an action URL
      Then  405 is returned
    """
    assert auth_client.get("/admin/tasks/t/F1/retry", headers=_MANAGER).status_code == 405


def test_backend_refusal_shows_error_flash_not_500(
    auth_client: TestClient, backend: InMemoryTaskBackend
) -> None:
    """
    Scenario: race
      Given the task was already retried
      When  the backend raises TasksBackendError
      Then  an error flash is shown, no 500
    """
    headers = _csrf(auth_client, _MANAGER)

    response = auth_client.post("/admin/tasks/t/P1/retry", headers=headers)

    assert response.status_code == 303
    assert response.headers["location"] == "/admin/tasks/t/P1?notice=failed"
    page = auth_client.get(response.headers["location"], headers=headers)
    assert page.status_code == 200
    assert 'data-testid="tasks-flash-danger"' in page.text
    assert backend.audit == []


def test_unexpected_backend_failure_also_becomes_error_flash(
    make_client: ClientFactory, now: datetime, make_task: TaskFactory
) -> None:
    """
    Scenario: a third-party backend crashes mid-action
      Given a backend whose retry_task raises a non-TasksBackendError
      When  a user retries a task
      Then  the user is redirected back with the error flash instead of a 500
    """
    store = _ExplodingBackend(clock=lambda: now)
    store.seed([make_task("F1", state=TaskState.FAILED)])
    client = make_client(store)

    response = client.post("/admin/tasks/t/F1/retry")

    assert response.headers["location"] == "/admin/tasks/t/F1?notice=failed"


def test_pause_and_resume_queue(auth_client: TestClient, backend: InMemoryTaskBackend) -> None:
    """
    Scenario: pause queue
      Given queue reports running
      When  a manage_tasks user clicks Pause
      Then  the dashboard shows reports as paused
    """
    headers = _csrf(auth_client, _MANAGER)
    before = auth_client.get("/admin/tasks/", headers=headers).text
    assert 'data-testid="tasks-queue-pause-btn"' in before

    paused = auth_client.post("/admin/tasks/queues/reports/pause", headers=headers)

    assert paused.headers["location"] == "/admin/tasks/?notice=queue-paused"
    page = auth_client.get(paused.headers["location"], headers=headers).text
    assert 'data-testid="tasks-queue-paused"' in page
    assert 'data-testid="tasks-queue-resume-btn"' in page
    assert 'data-testid="tasks-queue-pause-btn"' not in page
    assert "queue was paused" in page
    resumed = auth_client.post("/admin/tasks/queues/reports/resume", headers=headers)
    assert resumed.headers["location"] == "/admin/tasks/?notice=queue-resumed"
    assert (
        'data-testid="tasks-queue-paused"'
        not in auth_client.get(resumed.headers["location"], headers=headers).text
    )
    assert backend.audit == [
        ("pause_queue", "reports", "manager"),
        ("resume_queue", "reports", "manager"),
    ]


def test_pause_and_resume_schedule(auth_client: TestClient, backend: InMemoryTaskBackend) -> None:
    """
    Scenario: pause and resume a schedule
      Given an active and a paused schedule
      When  a manage_tasks user pauses the active one and resumes the paused one
      Then  the schedules page flashes each result and swaps the buttons
    """
    headers = _csrf(auth_client, _MANAGER)
    before = auth_client.get("/admin/tasks/schedules", headers=headers).text
    assert before.count('data-testid="tasks-schedule-pause-btn"') == 1
    assert before.count('data-testid="tasks-schedule-resume-btn"') == 1

    paused = auth_client.post("/admin/tasks/schedules/nightly/pause", headers=headers)
    resumed = auth_client.post("/admin/tasks/schedules/weekly/resume", headers=headers)

    assert paused.headers["location"] == "/admin/tasks/schedules?notice=schedule-paused"
    assert resumed.headers["location"] == "/admin/tasks/schedules?notice=schedule-resumed"
    after = auth_client.get(resumed.headers["location"], headers=headers).text
    assert "schedule was resumed" in after
    assert after.count('data-testid="tasks-schedule-pause-btn"') == 1
    assert backend.audit == [
        ("pause_schedule", "nightly", "manager"),
        ("resume_schedule", "weekly", "manager"),
    ]


def test_viewer_sees_no_action_controls(auth_client: TestClient) -> None:
    """
    Scenario: buttons hidden without permission
      Given a view_tasks-only user
      When  they open the dashboard, a failed task, a pending task and the schedules
      Then  no action button is rendered
    """
    pages = ("/admin/tasks/", "/admin/tasks/t/F1", "/admin/tasks/t/P1", "/admin/tasks/schedules")

    for url in pages:
        html = auth_client.get(url, headers=_VIEWER).text
        assert not _ACTION_BTN.search(html)


def test_buttons_follow_task_state(auth_client: TestClient) -> None:
    """
    Scenario: only applicable task actions are offered
      Given a failed, a pending and a running task
      When  a manage_tasks user opens each
      Then  failed offers Retry only, pending offers Cancel only, running offers neither
    """
    seen = {
        task_id: auth_client.get(f"/admin/tasks/t/{task_id}", headers=_MANAGER).text
        for task_id in ("F1", "P1", "R1")
    }

    assert 'tasks-retry-btn"' in seen["F1"]
    assert 'tasks-cancel-btn"' not in seen["F1"]
    assert 'tasks-cancel-btn"' in seen["P1"]
    assert 'tasks-retry-btn"' not in seen["P1"]
    assert 'tasks-retry-btn"' not in seen["R1"]
    assert 'tasks-cancel-btn"' not in seen["R1"]


def test_buttons_hidden_when_backend_lacks_capability(
    make_client: ClientFactory, now: datetime, make_task: TaskFactory
) -> None:
    """
    Scenario: actions are hidden when the backend lacks the capability
      Given a backend whose capabilities exclude every action
      When  a manage_tasks user opens a failed task, a pending task, the dashboard, the schedules
      Then  no action button is rendered
    """
    store = InMemoryTaskBackend({Capability.SCHEDULES}, clock=lambda: now)
    store.seed(
        [make_task("F1", state=TaskState.FAILED), make_task("P1")],
        schedules=[
            ScheduleRecord(
                id="nightly", task_name="app.job", queue="default", cron="0 3 * * *",
                misfire_policy="skip",
            )
        ],
    )  # fmt: skip
    client = make_client(store)

    for url in (
        "/admin/tasks/t/F1",
        "/admin/tasks/t/P1",
        "/admin/tasks/",
        "/admin/tasks/schedules",
    ):
        assert not _ACTION_BTN.search(client.get(url).text)


def test_flash_ignores_unknown_notice_codes(make_client: ClientFactory, now: datetime) -> None:
    """
    Scenario: a crafted notice cannot inject text
      Given the dashboard
      When  it is opened with an unknown notice code
      Then  no flash is rendered and the code is not echoed
    """
    client = make_client(InMemoryTaskBackend(clock=lambda: now))

    html = client.get("/admin/tasks/?notice=<b>pwned</b>").text

    assert "tasks-flash" not in html
    assert "pwned" not in html


def test_unknown_task_action_flashes_error(make_client: ClientFactory, now: datetime) -> None:
    """
    Scenario: acting on a vanished task
      Given a task id the backend does not know
      When  a user cancels it
      Then  the redirect carries the error notice
    """
    client = make_client(InMemoryTaskBackend(clock=lambda: now))

    response = client.post("/admin/tasks/t/gone/cancel")

    assert response.headers["location"] == "/admin/tasks/t/gone?notice=failed"


def test_missing_capability_action_flashes_error(make_client: ClientFactory, now: datetime) -> None:
    """
    Scenario: a forged request for an unsupported action
      Given a backend without PAUSE_QUEUE
      When  a user POSTs a pause
      Then  the backend's TasksBackendError becomes the error flash
    """
    client = make_client(InMemoryTaskBackend(set(), clock=lambda: now))

    response = client.post("/admin/tasks/queues/default/pause")

    assert response.headers["location"] == "/admin/tasks/?notice=failed"


def test_queue_and_schedule_names_with_slashes_route(
    make_client: ClientFactory, now: datetime, make_task: TaskFactory
) -> None:
    """
    Scenario: an odd queue or schedule name does not break the pages
      Given a queue "eu/east" and a schedule "ops/nightly"
      When  a user opens the dashboard and the schedules page and pauses both
      Then  the pages render and each action reaches the backend with the full name
    """
    store = InMemoryTaskBackend(clock=lambda: now)
    store.seed(
        [make_task("T1", queue="eu/east")],
        schedules=[
            ScheduleRecord(
                id="ops/nightly", task_name="app.job", queue="eu/east", cron="0 3 * * *",
                misfire_policy="skip",
            )
        ],
    )  # fmt: skip
    client = make_client(store)

    dashboard = client.get("/admin/tasks/")
    schedules = client.get("/admin/tasks/schedules")
    queue = client.post("/admin/tasks/queues/eu/east/pause")
    schedule = client.post("/admin/tasks/schedules/ops/nightly/pause")

    assert dashboard.status_code == schedules.status_code == 200
    assert queue.headers["location"] == "/admin/tasks/?notice=queue-paused"
    assert schedule.headers["location"] == "/admin/tasks/schedules?notice=schedule-paused"
    assert ("pause_queue", "eu/east", "anonymous") in store.audit
    assert ("pause_schedule", "ops/nightly", "anonymous") in store.audit


def test_forged_action_for_missing_capability_never_reaches_backend(
    make_client: ClientFactory, now: datetime, make_task: TaskFactory
) -> None:
    """
    Scenario: a forged retry against a backend without RETRY
      Given a backend whose capabilities exclude RETRY
      When  a user POSTs a retry for a failed task
      Then  the error flash is shown and the backend was not called
    """
    calls: list[str] = []

    class _Spy(InMemoryTaskBackend):
        async def retry_task(self, task_id: str, *, actor: str) -> None:
            calls.append(task_id)

    store = _Spy({Capability.CANCEL}, clock=lambda: now)
    store.seed([make_task("F1", state=TaskState.FAILED)])
    client = make_client(store)

    response = client.post("/admin/tasks/t/F1/retry")

    assert response.headers["location"] == "/admin/tasks/t/F1?notice=failed"
    assert calls == []


def test_boosted_action_without_permission_redirects_with_flash(
    auth_client: TestClient, backend: InMemoryTaskBackend
) -> None:
    """
    Scenario: a viewer's boosted form post gets visible feedback
      Given a view_tasks-only user
      When  an HTMX request POSTs a retry
      Then  a 303 back to the task carries the forbidden notice and the page shows it
    """
    headers = {**_csrf(auth_client, _VIEWER), "HX-Request": "true"}

    response = auth_client.post("/admin/tasks/t/F1/retry", headers=headers)

    assert response.status_code == 303
    assert response.headers["location"] == "/admin/tasks/t/F1?notice=forbidden"
    page = auth_client.get(response.headers["location"], headers=_VIEWER).text
    assert "not allowed to manage tasks" in page
    assert backend.audit == []


def test_dashboard_poll_without_permission_redirects_the_page(
    tmp_path: Path, backend: InMemoryTaskBackend
) -> None:
    """
    Scenario: the dashboard poll loses its permission
      Given a signed-in user whose view_tasks was revoked
      When  the HTMX poll requests the partial
      Then  an HX-Redirect to the dashboard is returned instead of an unswappable 403
    """
    app = FastAPI()
    admin = Admin(
        app,
        engine=create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'revoked.db'}"),
        settings=HyperAdminSettings(secret_key="tasks-test-secret"),
        auth=ExternalAuth(get_user=_get_user, has_permission=lambda user, codename: False),
    )
    admin.mount("/admin")
    admin.plugins["tasks"].lifecycle.backend = backend  # type: ignore[attr-defined]
    client = TestClient(app, follow_redirects=False)

    response = client.get("/admin/tasks/?partial=1", headers={**_VIEWER, "HX-Request": "true"})

    assert response.status_code == 200
    assert response.headers["HX-Redirect"] == "/admin/tasks/"
