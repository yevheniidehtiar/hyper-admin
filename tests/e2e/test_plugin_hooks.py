"""E2E: plugin hooks fire through real HTTP requests and failures stay isolated.

SDD ``docs/specs/plugin-registry.md``. Runs against :mod:`tests.e2e.apps.plugin_hooks`,
whose plugins are discovered through faked ``hyperadmin.plugins`` entry points.
The plugin doubles report what they saw over plugin pages, since the server runs
in a subprocess.
"""

from collections.abc import Iterator

import pytest
from playwright.sync_api import APIRequestContext, Page

from tests.e2e.conftest import _spawn_uvicorn, _terminate


@pytest.fixture
def plugin_hooks_base_url(e2e_port: int) -> Iterator[str]:
    """Start the plugin-hooks app and yield its base URL."""
    proc, base = _spawn_uvicorn("tests.e2e.apps.plugin_hooks", e2e_port, ready_path="/admin/")
    try:
        yield base
    finally:
        _terminate(proc)


def _events(request: APIRequestContext, base: str) -> dict:
    response = request.get(f"{base}/admin/recording/events")
    assert response.status == 200
    return response.json()


def _hooks(request: APIRequestContext, base: str) -> list[str]:
    return [e["hook"] for e in _events(request, base)["events"]]


def test_plugin_discovered_via_entry_point_on_admin_construction(
    page: Page, plugin_hooks_base_url: str
) -> None:
    """Scenario: plugin discovered via entry point on Admin construction."""
    # Given the "recording" package exposes a hyperadmin.plugins entry point
    # When Admin(app, engine=engine) was constructed (the app is running)
    data = _events(page.request, plugin_hooks_base_url)

    # Then its page is served, proving it is registered
    # And on_register ran exactly once
    assert data["register_calls"] == 1


def test_disabled_plugin_is_not_loaded(page: Page, plugin_hooks_base_url: str) -> None:
    """Scenario: disabled plugin is not loaded."""
    # Given the "muted" entry point is listed in disabled_plugins
    # When the admin has started
    # Then only the enabled plugins serve pages
    assert page.request.get(f"{plugin_hooks_base_url}/admin/recording/events").status == 200
    assert page.request.get(f"{plugin_hooks_base_url}/admin/muted/events").status == 404


def test_on_before_create_hook_fires_before_adapter_create(
    page: Page, plugin_hooks_base_url: str
) -> None:
    """Scenario: on_before_create hook fires before adapter create."""
    # Given the recording plugin is registered
    # When a Widget is created through the admin
    response = page.request.post(
        f"{plugin_hooks_base_url}/admin/widget", form={"name": "w"}, max_redirects=0
    )
    assert response.status == 303

    # Then on_before_create fired before the adapter create and on_after_create after it
    hooks = [(e["hook"], e["op"]) for e in _events(page.request, plugin_hooks_base_url)["events"]]
    before = hooks.index(("on_before_create", ""))
    adapter_before = hooks.index(("on_before_adapter_call", "create"))
    adapter_after = hooks.index(("on_after_adapter_call", "create"))
    after = hooks.index(("on_after_create", ""))
    assert before < adapter_before < adapter_after < after


def test_hook_exception_is_logged_and_does_not_break_request(
    page: Page, plugin_hooks_base_url: str
) -> None:
    """Scenario: hook exception is logged and does not break the request."""
    # Given the broken plugin raises from every hook
    # When a Widget is created through the admin
    response = page.request.post(
        f"{plugin_hooks_base_url}/admin/widget", form={"name": "w"}, max_redirects=0
    )

    # Then the request still succeeds
    assert response.status == 303

    # And the failure is logged and the recording plugin still got its hooks
    logs = page.request.get(f"{plugin_hooks_base_url}/admin/broken/logs").json()["messages"]
    assert any("plugin 'broken' hook on_before_create raised" in m for m in logs)
    assert "on_after_create" in _hooks(page.request, plugin_hooks_base_url)


def test_adapter_call_hooks_wrap_every_crud_operation(
    page: Page, plugin_hooks_base_url: str
) -> None:
    """Scenario: adapter call hooks wrap every CRUD operation."""
    # Given the recording plugin is registered
    base = f"{plugin_hooks_base_url}/admin/widget"

    # When the list, create, update and delete views are exercised once each
    assert page.request.get(base).status == 200
    assert page.request.post(base, form={"name": "a"}, max_redirects=0).status == 303
    assert page.request.put(f"{base}/1", form={"name": "b"}, max_redirects=0).status == 303
    assert page.request.delete(f"{base}/1", max_redirects=0).status in (200, 303)

    # Then each operation is bracketed by before/after adapter-call hooks
    events = [
        (e["hook"], e["op"])
        for e in _events(page.request, plugin_hooks_base_url)["events"]
        if e["op"]
    ]
    for op in ("list", "create", "update", "delete"):
        assert ("on_before_adapter_call", op) in events
        assert ("on_after_adapter_call", op) in events
    assert events[::2] == [("on_before_adapter_call", op) for _, op in events[::2]]
    assert events[1::2] == [("on_after_adapter_call", op) for _, op in events[1::2]]
