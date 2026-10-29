"""Unit tests for the ``hyperadmin-tasks`` plugin scaffold (entry point, seams, page gating)."""

from __future__ import annotations

from importlib.metadata import entry_points
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest
from fastapi import FastAPI, Header
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine

from hyperadmin import Admin
from hyperadmin.auth.bridge import ExternalAuth
from hyperadmin.core.plugins import Plugin, PluginRegistry
from hyperadmin.core.settings import HyperAdminSettings
from hyperadmin_tasks.plugin import TasksPlugin

_ALLOWED = {"Authorization": "Bearer allowed"}
_DENIED = {"Authorization": "Bearer denied"}


def _get_user(authorization: str | None = Header(default=None)) -> Any:
    tokens = {"Bearer allowed": "allowed", "Bearer denied": "denied"}
    return (
        SimpleNamespace(id=tokens[authorization], name=tokens[authorization], is_staff=True)
        if authorization in tokens
        else None
    )


def _has_permission(user: Any, codename: str) -> bool:
    return user.name == "allowed" and codename == "view_tasks"


@pytest.fixture
def engine(tmp_path: Path) -> AsyncEngine:
    return create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'tasks.db'}")


def _client(engine: AsyncEngine, *, bridge: bool = False, **admin_kwargs: Any) -> TestClient:
    app = FastAPI()
    if bridge:
        admin_kwargs["auth"] = ExternalAuth(get_user=_get_user, has_permission=_has_permission)
    Admin(
        app,
        engine=engine,
        settings=HyperAdminSettings(secret_key="tasks-test-secret"),
        **admin_kwargs,
    ).mount("/admin")
    return TestClient(app, follow_redirects=False)


def test_tasks_entry_point_resolves_to_tasks_plugin() -> None:
    """
    Scenario: the core plugin loader discovers the tasks plugin
      Given hyperadmin-tasks is installed
      When  the ``hyperadmin.plugins`` entry points are loaded
      Then  the ``tasks`` entry point resolves to TasksPlugin
    """
    (entry_point,) = entry_points(group="hyperadmin.plugins", name="tasks")

    assert entry_point.load() is TasksPlugin


def test_tasks_plugin_registers_seams() -> None:
    """
    Scenario: registering the tasks plugin fills every seam
      Given a PluginRegistry used as admin.plugins
      When  TasksPlugin is registered
      Then  its template dir holds the dashboard template
      And   the /tasks page and a "Tasks" nav entry gated on view_tasks are contributed
      And   the view_tasks and manage_tasks permissions are declared
    """
    registry = PluginRegistry()

    assert registry.register(TasksPlugin(), admin=SimpleNamespace(plugins=registry))

    (template_dir,) = registry.template_dirs
    assert (template_dir.path / "tasks/dashboard.html").is_file()
    (page,) = registry.pages
    assert page.prefix == "/tasks"
    (nav,) = registry.nav_entries
    assert (nav.section, nav.url_name, nav.permission) == ("Tasks", "tasks-dashboard", "view_tasks")
    assert [p.codename for p in registry.permissions] == ["view_tasks", "manage_tasks"]


def test_plugin_registry_discovers_and_registers_tasks_plugin() -> None:
    """
    Scenario: PluginRegistry discovery registers the installed tasks plugin
      Given hyperadmin-tasks is installed in the workspace environment
      When  entry points are loaded into the registry an admin exposes as admin.plugins
      Then  the ``tasks`` plugin is registered from its entry point
      And   it satisfies the core Plugin protocol
    """
    registry = PluginRegistry()
    registry.load_entry_points(admin=SimpleNamespace(plugins=registry))

    assert "tasks" in registry
    assert isinstance(registry["tasks"], Plugin)
    assert registry.origin("tasks") == "hyperadmin_tasks.plugin:TasksPlugin"
    assert "tasks" not in registry.skipped


def test_dashboard_renders_with_nav_entry(engine: AsyncEngine) -> None:
    """
    Scenario: the placeholder dashboard is served
      Given an admin without auth
      When  GET /admin/tasks/
      Then  response is 200 with the tasks dashboard
      And   the sidebar has the Tasks section and its dashboard link
    """
    response = _client(engine).get("/admin/tasks/")

    assert response.status_code == 200
    assert 'data-testid="tasks-dashboard"' in response.text
    assert ">Tasks</h3>" in response.text
    assert 'data-testid="nav-tasks-dashboard"' in response.text


def test_disabled_plugin_has_no_route_or_nav_entry(engine: AsyncEngine) -> None:
    """
    Scenario: disabling the tasks plugin removes its page and nav entry
      Given an admin built with disabled_plugins=["tasks"]
      When  GET /admin/tasks/
      Then  response is 404
      And   the sidebar has no Tasks entry
    """
    client = _client(engine, disabled_plugins=["tasks"])

    assert client.get("/admin/tasks/").status_code == 404
    assert 'data-testid="nav-tasks-dashboard"' not in client.get("/admin/").text


def test_dashboard_requires_view_tasks(engine: AsyncEngine) -> None:
    """
    Scenario: user without view_tasks is denied
      Given the user lacks view_tasks
      When  GET /admin/tasks/
      Then  response is 403 with the plugin's card naming the permission
      And   a user holding it gets 200
    """
    client = _client(engine, bridge=True)

    denied = client.get("/admin/tasks/", headers=_DENIED)

    assert denied.status_code == 403
    assert 'data-testid="tasks-forbidden"' in denied.text
    assert ">view_tasks</code>" in denied.text
    assert client.get("/admin/tasks/", headers=_ALLOWED).status_code == 200


def test_dashboard_without_user_is_unauthorized(engine: AsyncEngine) -> None:
    """
    Scenario: an anonymous request is rejected by the auth layer
      Given an admin with auth configured
      When  GET /admin/tasks/ carries no credentials
      Then  response is 401
    """
    assert _client(engine, bridge=True).get("/admin/tasks/").status_code == 401


def test_dashboard_starts_backend_lazily(engine: AsyncEngine) -> None:
    """
    Scenario: the dashboard route starts the backend on first use
      Given an admin whose tasks backend has not started
      When  GET /admin/tasks/ is served
      Then  the lifecycle reports the backend started
    """
    app = FastAPI()
    admin = Admin(app, engine=engine, settings=HyperAdminSettings(secret_key="tasks-test-secret"))
    admin.mount("/admin")
    lifecycle = admin.plugins["tasks"].lifecycle  # type: ignore[attr-defined]
    client = TestClient(app, follow_redirects=False)

    assert not lifecycle.started
    assert client.get("/admin/tasks/").status_code == 200
    assert lifecycle.started
