"""Route tests for the task detail page (story #755) over the in-memory backend."""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime, timedelta
from pathlib import Path
from types import SimpleNamespace
from typing import Any

from fastapi import FastAPI, Header
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import create_async_engine

from hyperadmin import Admin
from hyperadmin.auth.bridge import ExternalAuth
from hyperadmin.core.settings import HyperAdminSettings
from hyperadmin_tasks.backend import AttemptRecord, TaskRecord, TasksBackendError, TaskState
from hyperadmin_tasks.backends.memory import InMemoryTaskBackend
from hyperadmin_tasks.presenters import PREVIEW_LIMIT, render_json

ClientFactory = Callable[..., TestClient]
TaskFactory = Callable[..., TaskRecord]


class _FailingBackend(InMemoryTaskBackend):
    async def get_task(self, task_id: str) -> Any:
        raise TasksBackendError("connection refused")


def test_failed_task_shows_error_attempts_and_payload(
    make_client: ClientFactory, make_task: TaskFactory, now: datetime
) -> None:
    """
    Scenario: failed task detail
      Given a task failed after 3 attempts
      When  the user opens it
      Then  the error, 3 attempts with worker ids and timestamps, and payload are shown
    """
    backend = InMemoryTaskBackend(clock=lambda: now)
    backend.seed(
        [
            make_task(
                "T1",
                state=TaskState.FAILED,
                attempt=3,
                error="ValueError: boom",
                payload={"to": "a@example.com"},
                finished_at=now,
            )
        ],
        attempts={
            "T1": [
                AttemptRecord(
                    number=n,
                    worker_id=f"worker-{n}",
                    started_at=now + timedelta(minutes=n),
                    finished_at=now + timedelta(minutes=n, seconds=5),
                    outcome="failed",
                    error="ValueError: boom",
                )
                for n in (1, 2, 3)
            ]
        },
    )
    client = make_client(backend)

    response = client.get("/admin/tasks/t/T1")

    assert response.status_code == 200
    html = response.text
    assert 'data-testid="tasks-detail"' in html
    assert html.count('data-testid="tasks-attempt-row"') == 3
    assert "worker-1" in html
    assert "worker-3" in html
    assert "2026-11-01 12:03:00 UTC" in html
    assert 'data-testid="tasks-error"' in html
    assert "ValueError: boom" in html
    assert 'data-testid="tasks-payload"' in html
    assert "a@example.com" in html
    assert "Finished" in html


def test_task_without_optionals_renders_placeholders(
    make_client: ClientFactory, make_task: TaskFactory, now: datetime
) -> None:
    """
    Scenario: sparse task detail
      Given a pending task with no payload, result, error or attempts
      When  the user opens it
      Then  no error card is shown and the empty attempts state is rendered
    """
    backend = InMemoryTaskBackend(clock=lambda: now)
    backend.seed([make_task("T1")])
    client = make_client(backend)

    html = client.get("/admin/tasks/t/T1").text

    assert 'data-testid="tasks-error"' not in html
    assert 'data-testid="tasks-attempts-empty"' in html
    assert 'data-testid="tasks-parent-link"' not in html


def test_scheduled_task_with_parent_and_attempt_gaps(
    make_client: ClientFactory, make_task: TaskFactory, now: datetime
) -> None:
    """
    Scenario: child task links to its parent
      Given a scheduled task with a parent and an attempt that has no worker or end time
      When  the user opens it
      Then  the parent link points at the parent's detail page and gaps show a dash
    """
    backend = InMemoryTaskBackend(clock=lambda: now)
    backend.seed(
        [make_task("C1", state=TaskState.SCHEDULED, parent_id="P1", run_at=now, result={"ok": 1})],
        attempts={"C1": [AttemptRecord(number=1, started_at=now, outcome="running")]},
    )
    client = make_client(backend)

    html = client.get("/admin/tasks/t/C1").text

    assert '/admin/tasks/t/P1" data-testid="tasks-parent-link">P1</a>' in html
    assert "Run at" in html
    assert "&#34;ok&#34;: 1" in html
    assert '<td class="ha-table-cell ha-mono">-</td>' in html


def test_large_payload_is_truncated_with_expand_control(
    make_client: ClientFactory, make_task: TaskFactory, now: datetime
) -> None:
    """
    Scenario: large payload
      Given a 1 MiB payload
      When  the user opens the task
      Then  a truncated preview (64 KiB cap) with an expand control is shown
      And   following the expand control shows the whole payload
    """
    backend = InMemoryTaskBackend(clock=lambda: now)
    backend.seed([make_task("T1", payload={"blob": "x" * (1024 * 1024)})])
    client = make_client(backend)

    preview = client.get("/admin/tasks/t/T1").text
    expanded = client.get("/admin/tasks/t/T1?full=payload").text

    assert 'data-testid="tasks-payload-truncated"' in preview
    assert '/admin/tasks/t/T1?full=payload" data-testid="tasks-payload-expand"' in preview
    assert len(preview) < PREVIEW_LIMIT + 20_000
    assert 'data-testid="tasks-payload-truncated"' not in expanded
    assert len(expanded) > 1024 * 1024


def test_payload_markup_is_escaped(
    make_client: ClientFactory, make_task: TaskFactory, now: datetime
) -> None:
    """
    Scenario: untrusted payload cannot inject markup
      Given a payload, result and error containing a script tag
      When  the user opens the task
      Then  the markup appears escaped and no script element is rendered from it
    """
    backend = InMemoryTaskBackend(clock=lambda: now)
    backend.seed(
        [
            make_task(
                "T1",
                payload={"x": "<script>alert(1)</script>"},
                result="<img src=x onerror=alert(2)>",
                error="<b>bad</b>",
            )
        ]
    )
    client = make_client(backend)

    html = client.get("/admin/tasks/t/T1").text

    assert "<script>alert(1)</script>" not in html
    assert "&lt;script&gt;alert(1)&lt;/script&gt;" in html
    assert "<img src=x" not in html
    assert "<b>bad</b>" not in html


def test_unknown_task_id_renders_404_linking_back(
    make_client: ClientFactory, now: datetime
) -> None:
    """
    Scenario: deleted by retention
      Given a task id that no longer exists
      When  the user opens it
      Then  a 404 page links back to the list
    """
    client = make_client(InMemoryTaskBackend(clock=lambda: now))

    response = client.get("/admin/tasks/t/gone")

    assert response.status_code == 404
    assert 'data-testid="tasks-not-found"' in response.text
    assert '/admin/tasks/list" data-testid="tasks-back-to-list"' in response.text


def test_backend_failure_shows_inline_banner(make_client: ClientFactory, now: datetime) -> None:
    """
    Scenario: backend outage
      Given a backend whose get_task raises
      When  the user opens a task
      Then  the page renders an inline error banner instead of a 500
    """
    client = make_client(_FailingBackend(clock=lambda: now))

    response = client.get("/admin/tasks/t/T1")

    assert response.status_code == 200
    assert 'data-testid="tasks-backend-error"' in response.text
    assert 'data-testid="tasks-detail"' not in response.text


def test_list_rows_link_to_detail(
    make_client: ClientFactory, make_task: TaskFactory, now: datetime
) -> None:
    """
    Scenario: list rows open the detail page
      Given a listed task
      When  the user views the list
      Then  its id links to /admin/tasks/t/{id}
    """
    backend = InMemoryTaskBackend(clock=lambda: now)
    backend.seed([make_task("T1")])
    client = make_client(backend)

    html = client.get("/admin/tasks/list").text

    assert '/admin/tasks/t/T1" data-testid="tasks-row-link"' in html


def test_detail_requires_view_permission(tmp_path: Path) -> None:
    """
    Scenario: user without view_tasks is denied the detail page
      Given an admin with auth where the user lacks view_tasks
      When  GET /admin/tasks/t/{id}
      Then  response is 403 with the plugin's card
      And   a user holding it gets 404 for an unknown id (past the gate)
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

    denied = client.get("/admin/tasks/t/T1", headers={"Authorization": "Bearer denied"})
    allowed = client.get("/admin/tasks/t/T1", headers={"Authorization": "Bearer allowed"})

    assert denied.status_code == 403
    assert 'data-testid="tasks-forbidden"' in denied.text
    assert allowed.status_code == 404


def test_render_json_handles_none_small_large_and_unserialisable_values() -> None:
    """
    Scenario: JSON rendering for display
      Given None, a small value, an oversized multibyte value and a non-JSON value
      When  render_json is called
      Then  None stays None, small values are whole, large ones are cut on a character
            boundary at the byte cap unless full is requested, and others fall back to str()
    """
    big = {"k": "é" * PREVIEW_LIMIT}

    small = render_json({"a": 1})
    cut = render_json(big)
    whole = render_json(big, full=True)
    odd = render_json({"when": datetime(2026, 11, 1)})

    assert render_json(None) is None
    assert small is not None
    assert (small.truncated, small.text) == (False, '{\n  "a": 1\n}')
    assert cut is not None
    assert cut.truncated is True
    assert len(cut.text.encode()) <= PREVIEW_LIMIT
    assert cut.size > PREVIEW_LIMIT
    assert whole is not None
    assert whole.truncated is False
    assert len(whole.text.encode()) == cut.size
    assert odd is not None
    assert "2026-11-01 00:00:00" in odd.text
