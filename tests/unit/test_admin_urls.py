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
from starlette.staticfiles import StaticFiles

from hyperadmin.views.urls import (
    admin_base_path,
    admin_prefix_context,
    admin_url_for,
    install_namespaced_url_for,
    request_admin_path,
)


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

    Also pins the nested-Mount case (``static``) that st-v058-byoa-35 will
    depend on when ``/static`` moves under the admin prefix: a Mount is
    named differently from a plain route (no ``name=`` kwarg on the path
    operation) and takes a ``path`` param, so it is pinned separately from
    the plain APIRoute above.
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
        captured["static_namespaced"] = str(request.url_for("hyperadmin:static", path="css/x.css"))
        # admin_url_for needs the namespace on scope to prefer the namespaced
        # name, exactly as the plain-route case above needs it for user-list.
        request.scope["hyperadmin"] = {"namespace": "hyperadmin"}
        captured["static_via_helper"] = str(admin_url_for(request, "static", path="css/x.css"))
        return {}

    sub.mount("/static", StaticFiles(directory=".", check_dir=False), name="static")
    app.mount("/admin", sub, name="hyperadmin")

    response = TestClient(app).get("/admin/user")

    assert response.status_code == 200
    assert captured["namespaced"].endswith("/admin/user")
    assert captured["plain_raised"] is True
    assert captured["static_namespaced"].endswith("/admin/static/css/x.css")
    assert captured["static_via_helper"].endswith("/admin/static/css/x.css")


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


def test_admin_url_for_resolves_a_route_whose_path_param_is_named_name() -> None:
    """``name`` and ``request`` are positional-only on ``admin_url_for``
    (matching Starlette's own ``url_for``), so a route with a path param
    literally called ``name`` goes through ``**path_params`` instead of
    colliding with the function's own ``name`` parameter — both calling
    ``admin_url_for`` directly and through the installed Jinja ``url_for``.
    """
    app = FastAPI()

    @app.get("/tags/{name}", name="tag")
    async def tag_detail(name: str) -> dict[str, str]:
        return {"name": name}

    env = Environment()
    install_namespaced_url_for(env)
    template = env.from_string("{{ url_for('tag', name='x') }}")

    captured: dict[str, Any] = {}

    @app.middleware("http")
    async def _capture(request: Request, call_next: Any) -> Any:
        captured["direct"] = str(admin_url_for(request, "tag", name="x"))
        captured["via_jinja"] = template.render(request=request)
        return await call_next(request)

    response = TestClient(app).get("/tags/x")

    assert response.status_code == 200
    assert captured["direct"].endswith("/tags/x")
    assert captured["via_jinja"].endswith("/tags/x")


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


# ---------------------------------------------------------------------------
# request_admin_path / admin_prefix_context
# ---------------------------------------------------------------------------


def test_request_admin_path_uses_admin_base_path_for_a_mounted_request() -> None:
    """
    Scenario: a mounted admin request resolves its per-request admin path
      Given a request tagged by the isolated mount under root_path "/api/admin"
      When  request_admin_path is called with the static prefix "/admin"
      Then  it returns "/api/admin"
    """
    # Given
    request = _request_with_scope(root_path="/api/admin", hyperadmin={"namespace": "hyperadmin"})

    # When
    path = request_admin_path(request, "/admin")

    # Then
    assert path == "/api/admin"


def test_request_admin_path_keeps_the_default_for_an_untagged_request() -> None:
    """
    Scenario: an untagged request keeps the static mount prefix
      Given a request that no admin mount has tagged, under root_path "/api"
      When  request_admin_path is called with the static prefix "/admin"
      Then  it returns "/admin"
    """
    # Given
    request = _request_with_scope(root_path="/api")

    # When
    path = request_admin_path(request, "/admin")

    # Then
    assert path == "/admin"


def test_admin_prefix_context_exposes_the_per_request_admin_path() -> None:
    """
    Scenario: the template context processor exposes the per-request prefix
      Given a router-mode request tagged with prefix "/admin" under root_path "/api"
      When  admin_prefix_context is called
      Then  it returns admin_prefix "/api/admin"
    """
    # Given
    request = _request_with_scope(
        root_path="/api", hyperadmin={"namespace": None, "prefix": "/admin"}
    )

    # When
    context = admin_prefix_context(request)

    # Then
    assert context == {"admin_prefix": "/api/admin"}


def test_admin_prefix_context_adds_nothing_for_an_untagged_request() -> None:
    """
    Scenario: an untagged request leaves the static admin_prefix global in charge
      Given a request that no admin mount has tagged
      When  admin_prefix_context is called
      Then  it returns an empty mapping
    """
    # Given
    request = _request_with_scope(root_path="/api")

    # When
    context = admin_prefix_context(request)

    # Then
    assert context == {}
