"""The plugin home page seam: ``PluginRegistry.set_home_page`` and the admin index route.

Spec: ``docs/specs/dashboard-builder.md`` ("Core seam"); story
``featcore-add-dashboard-config-to-admin-class.md`` (#468).
"""

from __future__ import annotations

import logging
from collections.abc import Awaitable, Callable
from typing import Any

import pytest
from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import create_async_engine
from starlette.requests import Request
from starlette.responses import Response

from hyperadmin import Admin
from hyperadmin.core import plugins as plugins_mod
from hyperadmin.core.plugins import DISABLED_PLUGINS_ENV, PluginError, PluginHomePage
from hyperadmin.core.registry import site
from hyperadmin.core.settings import HyperAdminSettings
from hyperadmin.routing import HyperAdminRouter

WELCOME = "Welcome to HyperAdmin Dashboard"
Endpoint = Callable[[Request], Awaitable[Response]]


class HomePlugin:
    """Claims the admin home page with ``endpoint`` when it registers."""

    def __init__(self, name: str, endpoint: Endpoint) -> None:
        self.name = name
        self.endpoint = endpoint

    def on_register(self, admin: Any) -> None:
        admin.plugins.set_home_page(self, self.endpoint)


async def _plugin_home(request: Request) -> Response:
    return HTMLResponse("plugin home")


async def _other_home(request: Request) -> Response:
    return HTMLResponse("other home")


async def _broken_home(request: Request) -> Response:
    raise RuntimeError("boom")


async def _forbidden_home(request: Request) -> Response:
    raise HTTPException(status_code=403, detail="not for you")


@pytest.fixture(autouse=True)
def _isolated(monkeypatch: pytest.MonkeyPatch) -> Any:
    """No entry-point plugins and an empty model registry around every test."""
    monkeypatch.setattr(plugins_mod, "entry_points", lambda *, group: [])
    monkeypatch.delenv(DISABLED_PLUGINS_ENV, raising=False)
    saved = dict(site._registry)
    site._registry = {}
    yield
    site._registry = saved


def _admin(*plugins: Any) -> tuple[Admin, TestClient]:
    app = FastAPI()
    admin = Admin(
        app,
        engine=create_async_engine("sqlite+aiosqlite:///:memory:"),
        settings=HyperAdminSettings(secret_key="x" * 40, create_tables=False),
    )
    for plugin in plugins:
        admin.plugins.register(plugin, admin=admin)
    admin.mount("/admin")
    return admin, TestClient(app, raise_server_exceptions=False)


def test_a_plugin_home_page_replaces_the_welcome_page() -> None:
    """
    Scenario: a plugin home page replaces the welcome page
      Given a test plugin calls admin.plugins.set_home_page(self, endpoint) in on_register
      And   endpoint returns an HTML response "plugin home"
      When  a signed-in user requests GET {prefix}/
      Then  the response is 200 with "plugin home"
    """
    admin, client = _admin(HomePlugin("first", _plugin_home))

    response = client.get("/admin/")

    assert response.status_code == 200
    assert response.text == "plugin home"
    assert admin.plugins.home_page == PluginHomePage(plugin="first", endpoint=_plugin_home)


def test_without_a_home_page_the_welcome_page_is_served() -> None:
    """
    Scenario: without a home page the welcome page is served
      Given no plugin set a home page
      When  a signed-in user requests GET {prefix}/
      Then  the response contains "Welcome to HyperAdmin Dashboard"
    """
    admin, client = _admin()

    response = client.get("/admin/")

    assert response.status_code == 200
    assert WELCOME in response.text
    assert admin.plugins.home_page is None


def test_a_second_home_page_claim_is_refused(caplog: pytest.LogCaptureFixture) -> None:
    """
    Scenario: a second home page claim is refused
      Given plugin "first" set the home page
      When  plugin "second" calls set_home_page in its on_register
      Then  PluginError is raised
      And   "second" is skipped with reason register_error
      And   GET {prefix}/ still serves "first"'s endpoint
    """
    with caplog.at_level(logging.ERROR, logger="hyperadmin.core.plugins"):
        admin, client = _admin(HomePlugin("first", _plugin_home), HomePlugin("second", _other_home))

    assert admin.plugins.skipped == {"second": "register_error"}
    (record,) = [r for r in caplog.records if "failed to register" in r.getMessage()]
    assert record.exc_info is not None
    assert isinstance(record.exc_info[1], PluginError)
    assert "already set by plugin 'first'" in str(record.exc_info[1])
    assert client.get("/admin/").text == "plugin home"


def test_a_home_page_endpoint_that_raises_falls_back_to_the_welcome_page(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """
    Scenario: a home page endpoint that raises falls back to the welcome page
      Given a plugin home page endpoint that raises RuntimeError
      When  a signed-in user requests GET {prefix}/
      Then  the response is 200 with the welcome page
      And   the error is logged with the plugin name
    """
    _, client = _admin(HomePlugin("first", _broken_home))

    with caplog.at_level(logging.ERROR, logger="hyperadmin.routing"):
        response = client.get("/admin/")

    assert response.status_code == 200
    assert WELCOME in response.text
    (record,) = [r for r in caplog.records if r.name == "hyperadmin.routing"]
    assert record.getMessage() == "plugin 'first' home page raised"
    assert record.exc_info is not None
    assert isinstance(record.exc_info[1], RuntimeError)


def test_an_http_error_from_the_home_page_endpoint_is_kept() -> None:
    """
    Scenario: an HTTP error from the home page endpoint is kept
      Given a plugin home page endpoint that raises HTTPException(403)
      When  a signed-in user requests GET {prefix}/
      Then  the response is 403
    """
    _, client = _admin(HomePlugin("first", _forbidden_home))

    assert client.get("/admin/").status_code == 403


def test_a_failed_on_register_drops_the_home_page_claim() -> None:
    """
    Scenario: a plugin that fails to register loses its home page claim
      Given a plugin that sets the home page and then raises in on_register
      When  the plugin is registered
      Then  the registry has no home page
      And   another plugin can claim it
    """

    class Failing(HomePlugin):
        def on_register(self, admin: Any) -> None:
            super().on_register(admin)
            raise RuntimeError("late failure")

    admin, client = _admin(Failing("first", _plugin_home), HomePlugin("second", _other_home))

    assert admin.plugins.skipped == {"first": "register_error"}
    assert client.get("/admin/").text == "other home"


def test_set_home_page_is_only_callable_from_the_plugins_own_on_register() -> None:
    """
    Scenario: the home page seam is closed outside on_register
      Given a registered plugin
      When  it calls set_home_page after registration, or with something that is not callable
      Then  PluginError is raised
    """
    plugin = HomePlugin("first", _plugin_home)
    admin, _ = _admin(plugin)

    with pytest.raises(PluginError, match="only register UI seams"):
        admin.plugins.set_home_page(plugin, _other_home)

    class NotCallable(HomePlugin):
        def on_register(self, admin: Any) -> None:
            admin.plugins.set_home_page(self, "nope")

    other, _ = _admin(NotCallable("bad", _plugin_home))
    assert other.plugins.skipped == {"bad": "register_error"}


def test_router_without_a_home_page_lookup_serves_the_welcome_page() -> None:
    """
    Scenario: a router built without the lookup keeps the welcome page
      Given a HyperAdminRouter constructed without home_page
      When  it is inspected
      Then  its home page lookup is None
    """
    admin, _ = _admin()

    assert HyperAdminRouter(engine=admin.engine, templates=admin.templates).home_page is None
