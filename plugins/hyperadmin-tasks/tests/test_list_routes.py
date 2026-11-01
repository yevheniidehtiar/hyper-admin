"""Route tests for the task list (story #756) over the in-memory backend."""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime, timedelta
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
from hyperadmin_tasks.backend import Page, TaskRecord, TasksBackendError, TaskState
from hyperadmin_tasks.backends.memory import InMemoryTaskBackend
from hyperadmin_tasks.presenters import Pagination, list_url

ClientFactory = Callable[..., TestClient]
TaskFactory = Callable[..., TaskRecord]


class _FailingBackend(InMemoryTaskBackend):
    async def list_tasks(self, flt: Any, page: int, per_page: int) -> Any:
        raise TasksBackendError("connection refused")


class _UncountedBackend(InMemoryTaskBackend):
    """A backend that cannot count cheaply: pages come back with ``total=None``."""

    async def list_tasks(self, flt: Any, page: int, per_page: int) -> Any:
        result = await super().list_tasks(flt, page, per_page)
        return Page[TaskRecord](items=result.items, page=page, per_page=per_page, total=None)


def _seeded(
    make_task: TaskFactory, now: datetime, backend: InMemoryTaskBackend | None = None
) -> InMemoryTaskBackend:
    backend = backend or InMemoryTaskBackend(clock=lambda: now)
    backend.seed(
        [
            make_task("T1", state=TaskState.FAILED, queue="reports", name="app.build"),
            make_task("T2", state=TaskState.SUCCEEDED, queue="emails", name="app.mail"),
            make_task("T3", state=TaskState.FAILED, queue="emails", name="app.mail"),
        ]
    )
    return backend


def _ids(html: str, ids: list[str]) -> list[str]:
    return [
        task_id
        for task_id in ids
        if f'/admin/tasks/t/{task_id}" data-testid="tasks-row-link">{task_id}</a></th>' in html
    ]


def test_filter_by_state_persists_in_url(
    make_client: ClientFactory, make_task: TaskFactory, now: datetime
) -> None:
    """
    Scenario: filter by state
      Given failed and succeeded tasks
      When  the user selects state=failed
      Then  only failed tasks are listed and the filter persists in the URL
    """
    client = make_client(_seeded(make_task, now))

    html = client.get("/admin/tasks/list?state=failed").text

    assert _ids(html, ["T1", "T2", "T3"]) == ["T1", "T3"]
    assert '<option value="failed" selected>failed</option>' in html
    assert '<form method="get"' in html


def test_filter_by_queue_and_name(
    make_client: ClientFactory, make_task: TaskFactory, now: datetime
) -> None:
    """
    Scenario: filter by queue and task name
      Given tasks across queues and names
      When  the user filters queue=emails and name=app.mail
      Then  only matching tasks are listed and the queue option is selected
    """
    client = make_client(_seeded(make_task, now))

    html = client.get("/admin/tasks/list?queue=emails&name=app.mail").text

    assert _ids(html, ["T1", "T2", "T3"]) == ["T2", "T3"]
    assert '<option value="emails" selected>emails</option>' in html
    assert 'value="app.mail"' in html


def test_search_by_id(make_client: ClientFactory, make_task: TaskFactory, now: datetime) -> None:
    """
    Scenario: search by id
      Given a task with id T1
      When  the user searches "T1"
      Then  the row for T1 is shown
    """
    client = make_client(_seeded(make_task, now))

    html = client.get("/admin/tasks/list?q=T1").text

    assert _ids(html, ["T1", "T2", "T3"]) == ["T1"]
    assert html.count('data-testid="tasks-list-row"') == 1


def test_unknown_state_is_ignored(
    make_client: ClientFactory, make_task: TaskFactory, now: datetime
) -> None:
    """
    Scenario: an unknown state does not filter
      Given tasks in several states
      When  the user opens the list with state=bogus
      Then  all tasks are listed and no state option is selected
    """
    client = make_client(_seeded(make_task, now))

    html = client.get("/admin/tasks/list?state=bogus").text

    assert _ids(html, ["T1", "T2", "T3"]) == ["T1", "T2", "T3"]
    assert " selected" not in html


def test_paginates_with_page_size(
    make_client: ClientFactory,
    make_task: TaskFactory,
    now: datetime,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """
    Scenario: paginate
      Given 120 tasks and page_size 50
      When  the user clicks next
      Then  rows 51-100 are shown and pagination info reads page 2
    """
    monkeypatch.setenv("HYPERADMIN_TASKS_PAGE_SIZE", "50")
    backend = InMemoryTaskBackend(clock=lambda: now)
    backend.seed(
        make_task(f"t{n:03d}", created_at=now - timedelta(minutes=n)) for n in range(1, 121)
    )
    client = make_client(backend)

    first = client.get("/admin/tasks/list").text
    second = client.get("/admin/tasks/list?page=2").text
    last = client.get("/admin/tasks/list?page=3").text

    assert first.count('data-testid="tasks-list-row"') == 50
    assert 'data-testid="pagination-prev"' not in first
    assert 'href="/admin/tasks/list?page=2"' in first
    assert second.count('data-testid="tasks-list-row"') == 50
    assert "t051</a></th>" in second
    assert "t100</a></th>" in second
    assert "Showing 51 to 100 of 120 results" in second
    assert "Page 2 of 3" in second
    assert 'href="/admin/tasks/list"' in second
    assert 'href="/admin/tasks/list?page=3"' in second
    assert last.count('data-testid="tasks-list-row"') == 20
    assert 'data-testid="pagination-next"' not in last


def test_pagination_links_keep_filters(
    make_client: ClientFactory,
    make_task: TaskFactory,
    now: datetime,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """
    Scenario: pagination keeps the active filters
      Given 3 failed tasks and page_size 2
      When  the user opens the list with state=failed
      Then  the next link carries state=failed and page=2
    """
    monkeypatch.setenv("HYPERADMIN_TASKS_PAGE_SIZE", "2")
    backend = InMemoryTaskBackend(clock=lambda: now)
    backend.seed(make_task(f"f{n}", state=TaskState.FAILED) for n in range(3))
    client = make_client(backend)

    html = client.get("/admin/tasks/list?state=failed").text

    assert 'href="/admin/tasks/list?state=failed&amp;page=2"' in html


@pytest.mark.parametrize("raw", ["0", "-3", "abc", ""])
def test_bad_page_falls_back_to_first(
    make_client: ClientFactory, make_task: TaskFactory, now: datetime, raw: str
) -> None:
    """
    Scenario: a malformed page number shows page one
      Given tasks
      When  the user opens the list with page=<raw>
      Then  the first page is shown
    """
    client = make_client(_seeded(make_task, now))

    html = client.get(f"/admin/tasks/list?page={raw}").text

    assert "Page 1 of 1" in html


def test_unknown_total_paginates_by_full_page(
    make_client: ClientFactory,
    make_task: TaskFactory,
    now: datetime,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """
    Scenario: pagination without a total
      Given a backend that cannot count and page_size 2 with 3 tasks
      When  the user opens the list
      Then  info and page omit the total and a next link is offered
      And   the short second page offers none
    """
    monkeypatch.setenv("HYPERADMIN_TASKS_PAGE_SIZE", "2")
    client = make_client(_seeded(make_task, now, _UncountedBackend(clock=lambda: now)))

    first = client.get("/admin/tasks/list").text
    second = client.get("/admin/tasks/list?page=2").text

    assert "Showing 1 to 2</div>" in first
    assert "Page 1</div>" in first
    assert 'data-testid="pagination-next"' in first
    assert 'data-testid="pagination-next"' not in second


def test_empty_result_shows_empty_state(
    make_client: ClientFactory, make_task: TaskFactory, now: datetime
) -> None:
    """
    Scenario: no matches
      Given tasks
      When  the user searches an id that matches none
      Then  an empty message replaces the table and pagination
    """
    client = make_client(_seeded(make_task, now))

    html = client.get("/admin/tasks/list?q=zzz").text

    assert 'data-testid="tasks-list-empty"' in html
    assert "tasks-list-table" not in html
    assert 'data-testid="pagination-info"' not in html


def test_filter_inputs_have_labels(make_client: ClientFactory) -> None:
    """
    Scenario: filters are reachable by label
      Given the task list
      When  it is rendered
      Then  every filter input has a matching label
    """
    html = make_client(InMemoryTaskBackend()).get("/admin/tasks/list").text

    for field, label in (
        ("tasks-queue-filter", "Queue"),
        ("tasks-state-filter", "State"),
        ("tasks-name-filter", "Task name"),
        ("tasks-search-input", "Task ID"),
    ):
        assert f'<label for="{field}">{label}</label>' in html
        assert f'id="{field}"' in html


def test_backend_down_shows_banner(make_client: ClientFactory) -> None:
    """
    Scenario: backend down on the list
      Given the backend raises on list_tasks
      When  the user opens /admin/tasks/list
      Then  an error banner (tasks-backend-error) is shown instead of a 500
    """
    response = make_client(_FailingBackend()).get("/admin/tasks/list")

    assert response.status_code == 200
    assert 'data-testid="tasks-backend-error"' in response.text
    assert "tasks-list-table" not in response.text


def test_dashboard_queue_name_links_to_filtered_list(
    make_client: ClientFactory, make_task: TaskFactory, now: datetime
) -> None:
    """
    Scenario: queue name links to the filtered list
      Given queues reports and emails
      When  the user opens /admin/tasks
      Then  each queue name links to the list filtered on it
      And   an "All tasks" link points to the unfiltered list
    """
    html = make_client(_seeded(make_task, now)).get("/admin/tasks/").text

    assert 'tasks/list?queue=reports" data-testid="tasks-queue-link">reports</a>' in html
    assert 'tasks/list?queue=emails" data-testid="tasks-queue-link">emails</a>' in html
    assert 'data-testid="tasks-all-link"' in html


def test_list_url_drops_empty_filters() -> None:
    """
    Scenario: list URLs carry only set filters
      Given filters where some are empty
      When  list_url is built for page 1 and page 3
      Then  empty filters are dropped and page appears only past page 1
    """
    assert list_url("/l", {"queue": "", "q": ""}, 1) == "/l"
    assert list_url("/l", {"queue": "a b", "q": ""}, 3) == "/l?queue=a+b&page=3"


def test_pagination_indices_for_empty_page() -> None:
    """
    Scenario: an empty page has zeroed indices
      Given a page with no rows
      When  the pagination is read
      Then  start and end are 0, there is one page and no next
    """
    pagination = Pagination(page=1, per_page=50, shown=0, total=0)

    assert (pagination.start_index, pagination.end_index) == (0, 0)
    assert pagination.total_pages == 1
    assert not pagination.has_next


def test_list_requires_view_tasks(tmp_path: Path) -> None:
    """
    Scenario: user without view_tasks is denied the list
      Given an admin with auth where the user lacks view_tasks
      When  GET /admin/tasks/list
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

    denied = client.get("/admin/tasks/list", headers={"Authorization": "Bearer denied"})
    allowed = client.get("/admin/tasks/list", headers={"Authorization": "Bearer allowed"})

    assert denied.status_code == 403
    assert 'data-testid="tasks-forbidden"' in denied.text
    assert allowed.status_code == 200
