"""``Admin`` applies the plugin registry's seams (SDD ``docs/specs/plugin-registry.md``, 1b).

Uses the test-only :mod:`tests.demo_plugin`, installed through a fake
``hyperadmin.plugins`` entry point, plus the real ``reports`` plugin of the workspace.
"""

from __future__ import annotations

import logging
from collections.abc import Callable, Iterator
from dataclasses import dataclass
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import anyio
import pytest
from fastapi import APIRouter, FastAPI, Header, WebSocket
from fastapi.responses import PlainTextResponse
from fastapi.testclient import TestClient
from jinja2 import DictLoader, Environment
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, create_async_engine
from sqlmodel import Field, SQLModel, select

from hyperadmin import Admin, PluginRegistry
from hyperadmin.auth.bridge import ExternalAuth
from hyperadmin.auth.models import Permission
from hyperadmin.auth.permissions import PermissionSyncService
from hyperadmin.core import plugins as plugins_mod
from hyperadmin.core.plugin_wiring import extend_template_loader
from hyperadmin.core.plugins import DISABLED_PLUGINS_ENV
from hyperadmin.core.registry import site
from hyperadmin.core.settings import HyperAdminSettings
from tests.conftest import with_csrf
from tests.demo_plugin import DEMO_PERMISSION, DemoPlugin

_SECRET = "x" * 40
HTML = {"accept": "text/html"}


class PwWidget(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    name: str = ""


@dataclass
class _User:
    id: int = 1
    username: str = "viewer"
    is_superuser: bool = False


class _Backend:
    def __init__(self, user: _User | None) -> None:
        self.user = user

    async def get_current_user(self, request: Any) -> _User | None:
        return self.user

    async def authenticate(self, username: str, password: str) -> None:
        return None


class _Checker:
    """Grants ``granted`` (superusers get everything)."""

    def __init__(self, granted: set[str]) -> None:
        self.granted = granted

    async def has_permission(self, user: Any, codename: str) -> bool:
        return user.is_superuser or codename in self.granted

    async def get_user_permissions(self, user: Any) -> set[str]:
        return set(self.granted)


@dataclass
class _EntryPoint:
    name: str
    value: str
    target: Any

    def load(self) -> Any:
        return self.target


def _install(monkeypatch: pytest.MonkeyPatch, **plugins: Any) -> None:
    """Make ``plugins`` (name -> class or instance) the only installed entry points."""
    eps = [_EntryPoint(name, f"tests.fake:{name}", target) for name, target in plugins.items()]
    monkeypatch.setattr(plugins_mod, "entry_points", lambda *, group: list(eps))
    monkeypatch.delenv(DISABLED_PLUGINS_ENV, raising=False)


@pytest.fixture(autouse=True)
def _clean_registry() -> Iterator[None]:
    saved = dict(site._registry)
    site._registry = {}
    yield
    site._registry = saved


@pytest.fixture
def demo(monkeypatch: pytest.MonkeyPatch) -> None:
    _install(monkeypatch, demo=DemoPlugin)


def _admin(
    *,
    user: _User | None = None,
    granted: set[str] | None = None,
    auth: bool = True,
    **settings: Any,
) -> tuple[Admin, TestClient]:
    app = FastAPI()
    kwargs: dict[str, Any] = {}
    if auth:
        kwargs = {
            "auth_backend": _Backend(user or _User()),
            "permission_checker": _Checker(granted or set()),
        }
    admin = Admin(
        app,
        engine=create_async_engine("sqlite+aiosqlite:///:memory:"),
        settings=HyperAdminSettings(create_tables=False, secret_key=_SECRET, **settings),
        **kwargs,
    )
    admin.mount("/admin")
    return admin, with_csrf(TestClient(app, follow_redirects=False), _SECRET)


# -- discovery ----------------------------------------------------------------------


def test_admin_discovers_plugins_on_construction(demo: None) -> None:
    """
    Scenario: plugin discovered via entry point on Admin construction
      Given a "demo" entry point pointing at DemoPlugin
      When  Admin(app, engine=engine) is constructed
      Then  admin.plugins["demo"] is a DemoPlugin registered with this admin
    """
    admin, _ = _admin(auth=False)

    assert isinstance(admin.plugins, PluginRegistry)
    plugin = admin.plugins["demo"]
    assert isinstance(plugin, DemoPlugin)
    assert plugin.admin is admin


def test_disabled_plugin_is_not_loaded(demo: None) -> None:
    """
    Scenario: disabled plugin is not loaded
      Given the demo plugin is installed
      When  Admin(..., disabled_plugins=["demo"]) is constructed
      Then  "demo" is not in admin.plugins and its page is not served
    """
    app = FastAPI()
    admin = Admin(
        app,
        engine=create_async_engine("sqlite+aiosqlite:///:memory:"),
        settings=HyperAdminSettings(create_tables=False, secret_key=_SECRET),
        disabled_plugins=["demo"],
    )
    admin.mount("/admin")

    assert "demo" not in admin.plugins
    assert admin.plugins.skipped == {"demo": "disabled"}
    assert TestClient(app).get("/admin/demo/").status_code == 404


def test_plugins_enabled_false_skips_discovery(demo: None) -> None:
    """
    Scenario: the opt-out setting turns discovery off
      Given the demo plugin is installed
      When  the admin is built with plugins_enabled=False
      Then  no plugin is loaded and the sidebar has no plugin section
    """
    admin, client = _admin(auth=False, plugins_enabled=False)

    assert len(admin.plugins) == 0
    assert admin.plugins.skipped == {}
    assert "sidebar-plugin-" not in client.get("/admin/", headers=HTML).text


def test_plugin_settings_reach_the_plugin(monkeypatch: pytest.MonkeyPatch) -> None:
    """
    Scenario: operator settings are validated into the plugin's settings_model
      Given a plugin declaring a settings_model with page_size
      When  Admin(..., plugin_settings={"cfg": {"page_size": "5"}}) is built
      Then  admin.plugins.settings("cfg").page_size == 5
    """
    from pydantic import BaseModel

    class _CfgSettings(BaseModel):
        page_size: int = 20

    class _CfgPlugin:
        name = "cfg"
        settings_model = _CfgSettings

        def on_register(self, admin: Any) -> None:
            pass

    _install(monkeypatch, cfg=_CfgPlugin)
    admin = Admin(
        FastAPI(),
        engine=create_async_engine("sqlite+aiosqlite:///:memory:"),
        settings=HyperAdminSettings(create_tables=False, secret_key=_SECRET),
        plugin_settings={"cfg": {"page_size": "5"}},
    )

    assert admin.plugins.settings("cfg").page_size == 5


def test_dispatch_hook_passes_the_admin(monkeypatch: pytest.MonkeyPatch) -> None:
    """
    Scenario: Admin.dispatch_hook fans out to plugin hooks with admin=
      Given a plugin implementing on_after_create
      When  admin.dispatch_hook("on_after_create", model=..., instance=...) is called
      Then  the hook receives admin, model and instance
    """
    calls: list[dict[str, Any]] = []

    class _Hooked:
        name = "hooked"

        def on_register(self, admin: Any) -> None:
            pass

        def on_after_create(self, **kwargs: Any) -> None:
            calls.append(kwargs)

    _install(monkeypatch, hooked=_Hooked)
    admin, _ = _admin(auth=False)

    admin.dispatch_hook("on_after_create", model=PwWidget, instance="w")

    assert calls == [{"admin": admin, "model": PwWidget, "instance": "w"}]


# -- pages --------------------------------------------------------------------------


def test_plugin_page_is_served_inside_the_admin(demo: None) -> None:
    """
    Scenario: plugin page is served inside the admin
      Given the demo plugin adds a page with GET "/" named "demo-index"
      When  a permitted user requests GET /admin/demo/
      Then  the response is 200, rendered with the plugin template in the admin layout
      And   "hyperadmin:demo-index" resolves to /admin/demo/
    """
    admin, client = _admin(granted={DEMO_PERMISSION})

    page = client.get("/admin/demo/", headers=HTML)

    assert page.status_code == 200
    assert 'data-testid="demo-plugin-title"' in page.text
    assert 'data-testid="sidebar"' in page.text
    assert "/admin/static/plugins/demo/demo.css" in page.text
    assert admin.app.url_path_for("hyperadmin:demo-index") == "/admin/demo/"


def test_plugin_page_uses_the_admin_route_class(demo: None) -> None:
    """
    Scenario: plugin routes get HyperAdminRoute (error pages, CSRF)
      Given a user without the demo permission
      When  they open /admin/demo/ in a browser, and POST /admin/demo/ping without a token
      Then  the 403 renders as the admin error page
      And   the POST is refused by the CSRF check
    """
    admin, client = _admin()
    route_class = admin.router.route_class

    page = client.get("/admin/demo/", headers=HTML)
    client.headers.pop("X-CSRF-Token")
    ping = client.post("/admin/demo/ping")

    assert all(
        type(route) is route_class
        for route in admin.router.routes
        if getattr(route, "name", "").startswith("demo-")
    )
    assert page.status_code == 403
    assert 'data-testid="error-page"' in page.text
    assert ping.status_code == 403
    assert "pong" not in ping.text


def test_plugin_post_with_csrf_token_succeeds(demo: None) -> None:
    _, client = _admin(granted={DEMO_PERMISSION})

    assert client.post("/admin/demo/ping").json() == {"pong": "demo"}


def test_plugin_page_in_router_mode(demo: None) -> None:
    """
    Scenario: legacy router mode serves plugin pages and static under the host
      Given mount_mode="router"
      When  GET /admin/demo/ and /static/plugins/demo/demo.css
      Then  both are 200
    """
    with pytest.warns(DeprecationWarning, match="router"):
        _, client = _admin(auth=False, mount_mode="router")

    assert client.get("/admin/demo/", headers=HTML).status_code == 200
    assert client.get("/static/plugins/demo/demo.css").status_code == 200


def test_bridge_mode_guards_plugin_pages(demo: None) -> None:
    """
    Scenario: in bridge mode plugin pages sit behind the host's get_user guard
      Given Admin(auth=ExternalAuth(get_user=...)) and the demo plugin
      When  an anonymous API client and a staff user request /admin/demo/
      Then  the anonymous request is refused and the staff user gets the page
    """

    @dataclass
    class _HostUser:
        id: int
        username: str
        is_staff: bool = True
        is_superuser: bool = True

    def get_user(authorization: str | None = Header(default=None)) -> _HostUser | None:
        return _HostUser(1, "ada") if authorization == "Bearer ok" else None

    app = FastAPI()
    Admin(
        app,
        engine=create_async_engine("sqlite+aiosqlite:///:memory:"),
        settings=HyperAdminSettings(secret_key=_SECRET, csrf_mode="off"),
        auth=ExternalAuth(get_user=get_user),
    ).mount("/admin")
    client = TestClient(app, follow_redirects=False)

    anonymous = client.get("/admin/demo/", headers={"accept": "application/json"})
    staff = client.get("/admin/demo/", headers={**HTML, "Authorization": "Bearer ok"})

    assert anonymous.status_code == 401
    assert staff.status_code == 200


def test_page_colliding_with_a_model_slug_is_not_mounted(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    """
    Scenario: a plugin page prefix equal to a model slug loses to the model
      Given model PwWidget is registered and a plugin adds a page at /pwwidget
      When  the admin mounts
      Then  an ERROR names the plugin and the plugin route is not added
    """

    class _Clash:
        name = "clash"

        def on_register(self, admin: Any) -> None:
            router = APIRouter()
            router.add_api_route("/", lambda: "plugin", name="clash-index")
            admin.plugins.add_page(self, router, prefix="/pwwidget")

    _install(monkeypatch, clash=_Clash)
    site.register(PwWidget)
    with caplog.at_level(logging.ERROR, logger="hyperadmin.core.plugin_wiring"):
        admin, _ = _admin(auth=False)

    assert "registered model" in caplog.text
    assert "clash" in caplog.text
    assert not any(getattr(r, "name", None) == "clash-index" for r in admin.router.routes)


def test_unsupported_plugin_route_skips_the_page(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    """
    Scenario: a page router with a raw Starlette route is not mounted
      Given a plugin page router holding a plain Starlette Route
      When  the admin mounts
      Then  an ERROR is logged and the page's routes are not added
    """

    class _Raw:
        name = "raw"

        def on_register(self, admin: Any) -> None:
            router = APIRouter()
            router.add_api_route("/ok", lambda: "ok", name="raw-ok")
            router.add_route("/raw", lambda request: PlainTextResponse("raw"), name="raw-raw")
            admin.plugins.add_page(self, router)

    _install(monkeypatch, raw=_Raw)
    with caplog.at_level(logging.ERROR, logger="hyperadmin.core.plugin_wiring"):
        admin, _ = _admin(auth=False)

    assert "not mounted" in caplog.text
    assert not any(getattr(r, "name", "").startswith("raw-") for r in admin.router.routes)


def test_plugin_websocket_route_is_rebuilt(monkeypatch: pytest.MonkeyPatch) -> None:
    """
    Scenario: a plugin websocket endpoint is served inside the admin
      Given a plugin page router with a websocket route
      When  a client connects to /admin/live/ws
      Then  it receives the plugin's message
    """

    class _Live:
        name = "live"

        def on_register(self, admin: Any) -> None:
            router = APIRouter()

            @router.websocket("/ws", name="live-ws")
            async def ws(websocket: WebSocket) -> None:
                await websocket.accept()
                await websocket.send_text("hello")
                await websocket.close()

            admin.plugins.add_page(self, router)

    _install(monkeypatch, live=_Live)
    _, client = _admin(auth=False)

    with client.websocket_connect("/admin/live/ws") as websocket:
        assert websocket.receive_text() == "hello"


# -- static & templates -------------------------------------------------------------


def test_plugin_static_file_is_served_under_its_own_path(demo: None) -> None:
    """
    Scenario: plugin static file is served under its own path
      Given the demo plugin sets a static dir containing demo.css
      When  GET /admin/static/plugins/demo/demo.css
      Then  the response is 200, and core static files still resolve
    """
    _, client = _admin(auth=False)

    css = client.get("/admin/static/plugins/demo/demo.css")

    assert css.status_code == 200
    assert ".demo-plugin-page" in css.text
    assert client.get("/admin/static/css/hyperadmin.css").status_code == 200


def test_reports_plugin_assets_resolve_in_the_admin() -> None:
    """
    Scenario: the real reports plugin's templates and CSS are wired in
      Given hyperadmin-reports is installed in the workspace
      When  an Admin is mounted at /admin
      Then  its chart templates resolve in the admin Jinja env
      And   GET /admin/static/plugins/reports/charts.css is 200
    """
    admin, client = _admin(auth=False)

    assert "reports" in admin.plugins
    assert admin.templates.env.get_template("hyperadmin_reports/charts/bar.html")
    assert client.get("/admin/static/plugins/reports/charts.css").status_code == 200


def _shadow_plugin(path: Path) -> Callable[[], Any]:
    class _Shadow:
        name = "shadow"

        def on_register(self, admin: Any) -> None:
            admin.plugins.add_template_dir(self, path)

    return _Shadow


def test_plugin_templates_cannot_override_core_but_hosts_override_plugins(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """
    Scenario: template precedence is host > core > plugins
      Given a plugin template dir with "dashboard.html" and "shadow/page.html"
      And   a host template dir overriding "shadow/page.html"
      When  the admin resolves both names
      Then  "dashboard.html" is the core one and "shadow/page.html" the host one
    """
    plugin_dir = tmp_path / "plugin"
    (plugin_dir / "shadow").mkdir(parents=True)
    (plugin_dir / "dashboard.html").write_text("PLUGIN DASHBOARD")
    (plugin_dir / "shadow" / "page.html").write_text("PLUGIN PAGE")
    (plugin_dir / "shadow" / "only.html").write_text("PLUGIN ONLY")
    host_dir = tmp_path / "host"
    (host_dir / "shadow").mkdir(parents=True)
    (host_dir / "shadow" / "page.html").write_text("HOST PAGE")
    _install(monkeypatch, shadow=_shadow_plugin(plugin_dir))

    admin, _ = _admin(auth=False, template_dirs=[str(host_dir)])
    env = admin.templates.env

    assert not env.get_template("dashboard.html").filename.startswith(str(plugin_dir))
    assert env.get_template("shadow/page.html").render() == "HOST PAGE"
    assert env.get_template("shadow/only.html").render() == "PLUGIN ONLY"


def test_extend_template_loader_chains_a_custom_loader(tmp_path: Path) -> None:
    """
    Scenario: a host replaced the Jinja loader with a non-filesystem one
      Given an env whose loader is a DictLoader
      When  plugin template dirs are added
      Then  the DictLoader is searched first and plugin templates still resolve
    """
    (tmp_path / "p.html").write_text("PLUGIN")
    (tmp_path / "both.html").write_text("PLUGIN BOTH")
    registry = PluginRegistry()
    registry.register(_shadow_plugin(tmp_path)(), admin=SimpleNamespace(plugins=registry))
    env = Environment(loader=DictLoader({"both.html": "HOST BOTH"}))

    extend_template_loader(env, registry)

    assert env.get_template("both.html").render() == "HOST BOTH"
    assert env.get_template("p.html").render() == "PLUGIN"


def test_extend_template_loader_without_plugin_dirs_keeps_the_loader() -> None:
    env = _admin(auth=False, plugins_enabled=False)[0].templates.env
    loader = env.loader

    extend_template_loader(env, PluginRegistry())

    assert env.loader is loader


# -- sidebar ------------------------------------------------------------------------


def test_plugin_nav_entry_shows_for_permitted_users_only(demo: None) -> None:
    """
    Scenario: plugin nav entry appears in the sidebar for permitted users only
      Given the demo plugin adds "Demo report" gated on view_demo_report
      When  a user with that permission opens the dashboard
      Then  the sidebar shows the link under a "Reports" heading
      And   a user without it does not see the link or the heading
    """
    _, allowed = _admin(granted={DEMO_PERMISSION})
    _, denied = _admin(granted=set())

    page = allowed.get("/admin/", headers=HTML).text
    hidden = denied.get("/admin/", headers=HTML).text

    assert 'data-testid="sidebar-plugin-demo-demo-index"' in page
    assert 'href="/admin/demo/"' in page
    assert ">Reports</h3>" in page
    assert "sidebar-plugin-demo" not in hidden
    assert ">Reports</h3>" not in hidden


def test_plugin_nav_marks_the_current_page(demo: None) -> None:
    _, client = _admin(user=_User(is_superuser=True))

    page = client.get("/admin/demo/", headers=HTML).text

    link = page.split('data-testid="sidebar-plugin-demo-demo-index"')[1].split(">")[0]
    assert 'aria-current="page"' in link


def test_unresolvable_nav_entry_is_skipped(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    """
    Scenario: a nav entry naming no route cannot break the admin
      Given a plugin nav entry with url_name "nope" and one without section or permission
      When  the dashboard renders
      Then  the bad entry is logged at ERROR and left out
      And   the good entry renders under the default "Plugins" heading
    """

    class _Nav:
        name = "nav"

        def on_register(self, admin: Any) -> None:
            admin.plugins.add_nav_entry(self, label="Broken", url_name="nope")
            admin.plugins.add_nav_entry(
                self, label="Home", url_name="admin-dashboard", icon="fa fa-home"
            )

    _install(monkeypatch, nav=_Nav)
    with caplog.at_level(logging.ERROR, logger="hyperadmin.core.plugin_wiring"):
        admin, client = _admin(auth=False)

    page = client.get("/admin/", headers=HTML)

    assert "no admin route named 'nope'" in caplog.text
    assert page.status_code == 200
    assert "Broken" not in page.text
    assert 'data-testid="sidebar-plugin-nav-admin-dashboard"' in page.text
    assert ">Plugins</h3>" in page.text
    assert [s["title"] for s in admin.templates.env.globals["plugin_nav"]] == [None]


def test_nav_entry_testid_overrides_the_derived_one(monkeypatch: pytest.MonkeyPatch) -> None:
    """
    Scenario: several nav entries share a url_name and tell themselves apart by testid
      Given two entries to "admin-dashboard", one with testid="nav-home"
      When  the dashboard renders
      Then  that link carries data-testid="nav-home" and the other keeps the derived id
    """

    class _Nav:
        name = "nav"

        def on_register(self, admin: Any) -> None:
            admin.plugins.add_nav_entry(
                self, label="Home", url_name="admin-dashboard", testid="nav-home"
            )
            admin.plugins.add_nav_entry(self, label="Start", url_name="admin-dashboard")

    _install(monkeypatch, nav=_Nav)
    _, client = _admin(auth=False)

    page = client.get("/admin/", headers=HTML).text

    assert 'data-testid="nav-home"' in page
    assert 'data-testid="sidebar-plugin-nav-admin-dashboard"' in page


# -- permissions --------------------------------------------------------------------


async def _codenames(engine: AsyncEngine) -> dict[str, str | None]:
    async with AsyncSession(engine) as session:
        rows = (await session.execute(select(Permission))).scalars().all()
        return {row.codename: row.content_type for row in rows}


def _perm_admin(engine: AsyncEngine, registry: Any) -> Admin:
    admin = Admin(
        FastAPI(),
        engine=engine,
        settings=HyperAdminSettings(create_tables=False, secret_key=_SECRET),
        permission_registry=registry,
    )
    admin.mount("/admin")
    return admin


@pytest.fixture
def perm_engine(tmp_path: Path) -> AsyncEngine:
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'perms.db'}")

    async def _create() -> None:
        async with engine.begin() as conn:
            await conn.run_sync(SQLModel.metadata.create_all)

    anyio.run(_create)
    return engine


def test_plugin_permission_is_synced(
    monkeypatch: pytest.MonkeyPatch,
    perm_engine: AsyncEngine,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """
    Scenario: plugin permission shows in the permission system
      Given the demo plugin declares view_demo_report
      And   another plugin declares view_pwwidget, which model PwWidget already defines
      When  the admin starts and permissions are synced (twice)
      Then  view_demo_report exists once with content type "plugin:demo"
      And   the colliding codename keeps the model's row and is logged at ERROR
    """

    class _Collide:
        name = "collide"

        def on_register(self, admin: Any) -> None:
            admin.plugins.add_permission(self, "view_pwwidget")

    _install(monkeypatch, demo=DemoPlugin, collide=_Collide)
    site.register(PwWidget)
    admin = _perm_admin(perm_engine, PermissionSyncService(engine=perm_engine))

    with caplog.at_level(logging.ERROR, logger="hyperadmin.core.plugin_wiring"):
        anyio.run(admin._sync_permissions)
        anyio.run(admin._sync_permissions)

    codenames = anyio.run(_codenames, perm_engine)
    assert codenames[DEMO_PERMISSION] == "plugin:demo"
    assert codenames["view_pwwidget"] == "pwwidget"
    assert "'view_pwwidget' not synced" in caplog.text


def test_permission_registry_without_sync_codenames_is_left_alone(demo: None) -> None:
    """
    Scenario: a custom PermissionRegistry without sync_codenames still works
      Given a registry implementing only sync_permissions
      When  permissions are synced
      Then  only sync_permissions is called
    """
    calls: list[Any] = []

    class _OnlyModels:
        async def sync_permissions(self, models: list[Any]) -> None:
            calls.append(models)

    admin = _perm_admin(create_async_engine("sqlite+aiosqlite:///:memory:"), _OnlyModels())

    anyio.run(admin._sync_permissions)

    assert calls == [[]]


def test_sync_codenames_creates_only_missing_rows(perm_engine: AsyncEngine) -> None:
    service = PermissionSyncService(engine=perm_engine)

    anyio.run(service.sync_codenames, [("a_b", "Can a b", "plugin:x"), ("a_b", "dup", None)])
    anyio.run(service.sync_codenames, [("a_b", "changed", None)])
    anyio.run(service.sync_codenames, [])

    assert anyio.run(_codenames, perm_engine) == {"a_b": "plugin:x"}
