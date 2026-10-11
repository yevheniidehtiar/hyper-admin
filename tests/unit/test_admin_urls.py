"""Unit tests for ``hyperadmin.views.urls``.

The first test is the spike the story called for: it pins
``request.url_for`` behaviour from inside a *named* mounted sub-app on the
installed fastapi/starlette versions, before any HyperAdmin code is trusted
to rely on it.
"""

from __future__ import annotations

from typing import Any

import pytest
from fastapi import FastAPI, Request
from fastapi.testclient import TestClient
from jinja2 import Environment
from starlette.routing import NoMatchFound

from hyperadmin.views.urls import admin_base_path, admin_url_for, install_namespaced_url_for


def _app_with_sub(*, sub_name: str = "hyperadmin") -> tuple[FastAPI, FastAPI]:
    app = FastAPI()
    sub = FastAPI()

    @sub.get("/user", name="user-list")
    async def user_list() -> dict[str, bool]:
        return {"ok": True}

    app.mount("/admin", sub, name=sub_name)
    return app, sub


# ---------------------------------------------------------------------------
# Spike: pin request.url_for behaviour through a named mounted sub-app
# ---------------------------------------------------------------------------


def test_spike_namespaced_name_resolves_and_plain_name_does_not() -> None:
    """request.url_for('hyperadmin:user-list') resolves inside the sub-app;
    the plain 'user-list' raises NoMatchFound. If this fails on an
    upgraded fastapi/starlette, admin_url_for's fallback story breaks and
    must be re-escalated before anything else here is trusted.
    """
    app = FastAPI()
    sub = FastAPI()
    captured: dict[str, Any] = {}

    @sub.get("/user", name="user-list")
    async def user_list(request: Request) -> dict[str, str]:
        captured["namespaced"] = str(request.url_for("hyperadmin:user-list"))
        try:
            request.url_for("user-list")
            captured["plain_raised"] = False
        except NoMatchFound:
            captured["plain_raised"] = True
        return {}

    app.mount("/admin", sub, name="hyperadmin")

    response = TestClient(app).get("/admin/user")

    assert response.status_code == 200
    assert captured["namespaced"].endswith("/admin/user")
    assert captured["plain_raised"] is True


# ---------------------------------------------------------------------------
# Story scenarios (st-v058-byoa-34)
# ---------------------------------------------------------------------------


def test_namespaced_route_resolves() -> None:
    """
    Scenario: namespaced route resolves
      Given a sub-app mounted with name 'hyperadmin'
      When  admin_url_for(request, 'user-list') runs
      Then  '/admin/user' is returned
    """
    app, sub = _app_with_sub()
    captured: dict[str, Any] = {}

    @sub.middleware("http")
    async def _capture(request: Request, call_next: Any) -> Any:
        # A mount's own middleware (or AuthenticationMiddleware, in the real
        # app) is where scope["hyperadmin"]["namespace"] gets set (-35).
        request.scope["hyperadmin"] = {"namespace": "hyperadmin"}
        captured["url"] = str(admin_url_for(request, "user-list"))
        return await call_next(request)

    response = TestClient(app).get("/admin/user")

    assert response.status_code == 200
    assert captured["url"].endswith("/admin/user")


def test_host_route_names_still_resolve() -> None:
    """
    Scenario: host route names still resolve
      Given a host route named 'reports'
      When  a template calls url_for('reports')
      Then  the host URL is rendered
    """
    app, sub = _app_with_sub()

    @app.get("/reports", name="reports")
    async def reports() -> dict[str, bool]:
        return {"ok": True}

    env = Environment()
    install_namespaced_url_for(env)
    template = env.from_string("{{ url_for('reports') }}")

    captured: dict[str, Any] = {}

    @sub.middleware("http")
    async def _render(request: Request, call_next: Any) -> Any:
        # Exercise the real case: a namespace is set (the admin route
        # "hyperadmin:reports" does not exist), and the host route must
        # still resolve on the plain-name fallback.
        request.scope["hyperadmin"] = {"namespace": "hyperadmin"}
        captured["rendered"] = template.render(request=request)
        return await call_next(request)

    response = TestClient(app).get("/admin/user")

    assert response.status_code == 200
    assert captured["rendered"].endswith("/reports")


def test_admin_url_for_falls_back_to_plain_name_outside_a_namespace() -> None:
    """With no ``hyperadmin`` scope info, ``admin_url_for`` behaves exactly
    like ``request.url_for`` (today's legacy router-mode / un-mounted state).
    """
    app = FastAPI()

    @app.get("/reports", name="reports")
    async def reports() -> dict[str, bool]:
        return {"ok": True}

    captured: dict[str, Any] = {}

    @app.middleware("http")
    async def _capture(request: Request, call_next: Any) -> Any:
        captured["url"] = str(admin_url_for(request, "reports"))
        return await call_next(request)

    response = TestClient(app).get("/reports")

    assert response.status_code == 200
    assert captured["url"].endswith("/reports")


def test_admin_url_for_raises_when_neither_name_resolves() -> None:
    """An unknown name with a namespace set still raises NoMatchFound."""
    app, sub = _app_with_sub()
    captured: dict[str, Any] = {}

    @sub.middleware("http")
    async def _capture(request: Request, call_next: Any) -> Any:
        request.scope["hyperadmin"] = {"namespace": "hyperadmin"}
        try:
            admin_url_for(request, "does-not-exist")
            captured["raised"] = False
        except NoMatchFound:
            captured["raised"] = True
        return await call_next(request)

    response = TestClient(app).get("/admin/user")

    assert response.status_code == 200
    assert captured["raised"] is True


# ---------------------------------------------------------------------------
# admin_base_path
# ---------------------------------------------------------------------------


def _request_with_scope(**scope_extra: Any) -> Request:
    scope: dict[str, Any] = {
        "type": "http",
        "method": "GET",
        "path": "/",
        "headers": [],
        "root_path": "",
    }
    scope.update(scope_extra)
    return Request(scope)


def test_admin_base_path_is_root_path_in_isolated_mode() -> None:
    """Isolated mode: scope['root_path'] already holds the full external
    prefix (Starlette extends it for a named Mount), so it is returned as-is.
    """
    request = _request_with_scope(root_path="/api/admin", hyperadmin={"namespace": "hyperadmin"})

    assert admin_base_path(request) == "/api/admin"


def test_admin_base_path_appends_prefix_in_router_mode() -> None:
    """Router mode (no namespace): the admin prefix is appended to the host's
    own root_path.
    """
    request = _request_with_scope(
        root_path="/api", hyperadmin={"namespace": None, "prefix": "/admin"}
    )

    assert admin_base_path(request) == "/api/admin"


def test_admin_base_path_defaults_to_root_path_before_mount_wires_scope() -> None:
    """Before admin.mount() sets scope['hyperadmin'] at all (today's state),
    admin_base_path is just the host's root_path.
    """
    request = _request_with_scope(root_path="/api")

    assert admin_base_path(request) == "/api"


@pytest.mark.parametrize("value", [None, "", {}])
def test_admin_base_path_treats_empty_namespace_as_router_mode(value: Any) -> None:
    request = _request_with_scope(root_path="", hyperadmin={"namespace": value, "prefix": "/admin"})

    assert admin_base_path(request) == "/admin"
