---
name: hyperadmin-new-plugin
description: Build a HyperAdmin plugin as its own Python package - entry point, the on_register seams (pages, sidebar entries, templates, static files, permissions, home page), validated settings, lifecycle hooks, packaging and tests, following how the first-party hyperadmin-reports, hyperadmin-tasks and hyperadmin-logfire plugins are built. Use when the user says "write a hyperadmin plugin", "add a custom admin page", "add my own page to the sidebar", "hook into create/update/delete", "audit log plugin", "package this as a plugin", or "plugin entry point".
---

# Build a HyperAdmin plugin

A plugin is any object with a `name` and an `on_register(admin)` method, found through the
`hyperadmin.plugins` entry-point group. There is no base class; `hyperadmin.Plugin` is a
runtime-checkable protocol usable as a type hint. Plugins add UI only through
`admin.plugins.*` calls made inside `on_register`, and observe the admin through hook methods.

Docs: Plugins > Overview, Writing a Plugin, Hook Reference (`docs/plugins/`). Reference
implementations in the HyperAdmin repository: `plugins/hyperadmin-reports` (pages, static
files, nav entries per report, home page, settings), `plugins/hyperadmin-tasks` (pages,
capability-dependent nav, permissions, settings), `plugins/hyperadmin-logfire` (hooks only,
no UI).

## Flow

1. **Decide the shape.** UI pages? Hooks only? Settings? A plugin observes; it cannot veto or
   change a save (hooks are observers), so validation belongs in the model or a permission.
2. **Pick the name.** Lowercase letter first, then lowercase letters, digits, `_`, `-`. It
   appears in URLs (`/admin/<name>/`), static paths, settings keys, `disabled_plugins` and logs.
   Prefix route names with it (`audit-index`); they join the `hyperadmin:` namespace.
3. **Create the package** (layout below), with the entry point name equal to `name`.
4. **Write `on_register`** with the seams it needs.
5. **Add hooks** as plain `def` methods taking keyword arguments and ending in `**kwargs`.
6. **Test** with a fake entry point (below) and TestClient.
7. **Install** with `pip install -e .`; `hyperadmin plugins list` shows it; every `Admin(...)` in
   that environment loads it.

## Package layout

```text
hyperadmin-audit/
  pyproject.toml
  README.md
  src/hyperadmin_audit/
    __init__.py
    plugin.py
    settings.py
    templates/audit/index.html       # templates live in a folder named after the plugin
    static/audit.css                 # optional, served at {prefix}/static/plugins/audit/
  tests/test_audit_plugin.py
```

```toml
# pyproject.toml
[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[project]
name = "hyperadmin-audit"
version = "0.1.0"
requires-python = ">=3.11"
dependencies = ["hyper-admin>=1.0.0"]

[project.entry-points."hyperadmin.plugins"]
audit = "hyperadmin_audit.plugin:AuditPlugin"   # entry-point name == plugin.name

[tool.hatch.build.targets.wheel]
packages = ["src/hyperadmin_audit"]
```

The entry point may name a class (instantiated with no arguments, once per `Admin`) or an
instance. A name mismatch skips the plugin as `invalid`.

## The plugin

<!-- check: complete -->
```python
# src/hyperadmin_audit/settings.py
from pydantic_settings import BaseSettings, SettingsConfigDict


class AuditSettings(BaseSettings):
    """Validated from Admin(plugin_settings={"audit": {...}}) and HYPERADMIN_AUDIT_* env vars."""

    model_config = SettingsConfigDict(env_prefix="HYPERADMIN_AUDIT_", extra="ignore")

    keep: int = 50
```

<!-- check: complete -->
```python
# src/hyperadmin_audit/plugin.py
import logging
from collections import deque
from pathlib import Path
from typing import Any, ClassVar

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import HTMLResponse

from hyperadmin_audit.settings import AuditSettings

logger = logging.getLogger("hyperadmin_audit")
PACKAGE_DIR = Path(__file__).parent
VIEW_PERMISSION = "view_audit_log"


class AuditPlugin:
    name: ClassVar[str] = "audit"
    settings_model: ClassVar[type[AuditSettings]] = AuditSettings

    def on_register(self, admin: Any) -> None:
        settings: AuditSettings = admin.plugins.settings(self.name) or AuditSettings()
        self.recent: deque[str] = deque(maxlen=settings.keep)

        router = APIRouter()

        @router.get("/", name="audit-index", response_class=HTMLResponse)
        async def index(request: Request) -> HTMLResponse:
            checker = admin.permission_checker  # None when the admin runs without auth
            user = getattr(request.state, "user", None)
            if checker is not None and not await checker.has_permission(user, VIEW_PERMISSION):
                raise HTTPException(status_code=403)
            context = {"recent": list(self.recent)}
            return admin.templates.TemplateResponse(request, "audit/index.html", context)

        plugins = admin.plugins
        plugins.add_page(self, router)  # served at {prefix}/audit/
        plugins.add_template_dir(self, PACKAGE_DIR / "templates")
        plugins.set_static_dir(self, PACKAGE_DIR / "static")
        plugins.add_permission(self, VIEW_PERMISSION, name="Can view the audit log")
        plugins.add_nav_entry(
            self,
            label="Audit log",
            url_name="audit-index",
            icon="history",
            permission=VIEW_PERMISSION,
            section="Tools",
            testid="nav-audit-index",
        )

    def on_after_create(self, *, model: type, instance: Any, **kwargs: Any) -> None:
        message = f"created {model.__name__} #{getattr(instance, 'id', '?')}"
        self.recent.append(message)
        logger.info(message)

    def on_after_delete(self, *, model: type, pk: Any, **kwargs: Any) -> None:
        self.recent.append(f"deleted {model.__name__} #{pk}")
```

```jinja
{#- src/hyperadmin_audit/templates/audit/index.html -#}
{% extends "base.html" %}
{% block title %}Audit log | {{ site_title | default("HyperAdmin") }}{% endblock %}
{% block content %}
  <link rel="stylesheet" href="{{ url_for('static', path='/plugins/audit/audit.css') }}">
  <h1 class="ha-page-title">Audit log</h1>
  <ul data-testid="audit-recent">
    {% for message in recent %}<li>{{ message }}</li>{% endfor %}
  </ul>
{% endblock %}
```

## `admin.plugins` seams (only inside `on_register`)

Each takes the plugin as first argument; calling one elsewhere raises `PluginError`.

| Call | Effect |
|---|---|
| `add_page(plugin, router, *, prefix=None)` | Serves a FastAPI `APIRouter` inside the admin, under `/<name>` by default, behind the admin's login, CSRF check, locale and error pages. Declare routes directly on that router: a nested `include_router` or a mount is rejected |
| `add_nav_entry(plugin, *, label, url_name, icon=None, permission=None, section=None, order=0, url_params=None, testid=None)` | Sidebar link to a named route. `section` puts it in the group with that label (`NavGroup` styles it). `permission` only hides the link: check it in the route too |
| `add_template_dir(plugin, path)` | Template directory searched after the host's and the built-ins (a plugin cannot override built-in templates) |
| `set_static_dir(plugin, path)` | One static directory per plugin, at `{prefix}/static/plugins/<name>/`; link with `url_for('static', path='/plugins/<name>/...')` |
| `add_permission(plugin, codename, name=None)` | A codename that can be granted to groups (built-in auth) or passed to your `has_permission` |
| `set_home_page(plugin, endpoint)` | Serve `async (request) -> Response` at the admin index `{prefix}/` (one plugin per admin; falls back to the welcome page if it raises anything but `HTTPException`). Used by the reports dashboard |
| `settings(name)` | The validated `settings_model` instance (`None` without a `settings_model`) |

Also useful inside routes: `admin.templates` (the Jinja2Templates; extend `base.html`),
`admin.permission_checker` (`None` without auth), `request.state.user`. A prefix or codename
already taken by another plugin raises `PluginError`. If `on_register` raises, the plugin is
skipped and everything it added is rolled back.

## Hooks

Plain `def` methods named after the hook, keyword arguments only, end with `**kwargs`. Return
values are ignored, exceptions are logged and swallowed, `async def` hooks are ignored with an
`ERROR` log.

| Hook | Keyword arguments | Fires |
|---|---|---|
| `on_model_register` | `admin`, `model`, `options` | Once per registered model |
| `on_before_create` / `on_after_create` | `admin`, `model`, `data` / `instance` | Create form |
| `on_before_update` / `on_after_update` | `admin`, `model`, `pk`, `data` / `instance` | Edit form |
| `on_before_delete` / `on_after_delete` | `admin`, `model`, `pk` | Delete action |
| `on_before_adapter_call` / `on_after_adapter_call` | `admin`, `model`, `op`, `kwargs` / `result`, `error` | Every adapter operation, including inline edits, inline rows, quick-create and bulk actions |
| `on_validation_error` | `admin`, `model`, `field_errors` | Create/edit validation failed |
| `on_auth_event` | `admin`, `event`, `user`, `username`, `request` (+ `model`) | Sign-in, failed sign-in, sign-out, denied permission |

The six CRUD hooks fire only from the create form, edit form and delete action; use the
adapter-call hooks to see every write. Hooks run on the event loop inside the request: hand slow
work to a queue. One plugin object serves all requests: no per-request state on `self` (use a
`contextvars.ContextVar`). `data`, `instance` and `kwargs` are live objects: treat them as
read-only, and filter field values before logging them.

## Tests

<!-- check: complete -->
```python
# tests/test_audit_plugin.py
from collections.abc import Iterator
from importlib.metadata import EntryPoint

import anyio
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import create_async_engine
from sqlmodel import Field, SQLModel

from hyperadmin import Admin
from hyperadmin.core import plugins as plugins_module
from hyperadmin.core.registry import site
from hyperadmin.core.settings import HyperAdminSettings


class Note(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    text: str


@pytest.fixture
def admin(monkeypatch: pytest.MonkeyPatch) -> Iterator[Admin]:
    entry_point = EntryPoint(
        name="audit", value="hyperadmin_audit.plugin:AuditPlugin", group="hyperadmin.plugins"
    )
    # Patch the name the registry looks up, not importlib.metadata.entry_points.
    monkeypatch.setattr(plugins_module, "entry_points", lambda *, group: [entry_point])
    monkeypatch.delenv("HYPERADMIN_DISABLED_PLUGINS", raising=False)
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")

    async def create_schema() -> None:
        async with engine.begin() as conn:
            await conn.run_sync(SQLModel.metadata.create_all)

    anyio.run(create_schema)
    admin = Admin(
        FastAPI(),
        engine=engine,
        settings=HyperAdminSettings(create_tables=False),
        plugin_settings={"audit": {"keep": 5}},
    )
    site.register(Note)
    admin.mount("/admin")
    yield admin
    site.unregister(Note)


def test_plugin_is_discovered(admin: Admin) -> None:
    assert "audit" in admin.plugins
    assert admin.plugins.skipped == {}


def test_create_shows_on_the_audit_page(admin: Admin) -> None:
    client = TestClient(admin.app)
    response = client.post("/admin/note", data={"text": "hello"}, follow_redirects=False)
    assert response.status_code == 303
    page = client.get("/admin/audit/")
    assert page.status_code == 200
    assert "created Note #1" in page.text
```

- `admin.plugins.skipped` maps a plugin name to `disabled`, `load_error`, `invalid` or
  `register_error`: assert on it so a failing test names the reason.
- Without discovery: `admin.plugins.register(AuditPlugin(), admin=admin)` before `mount()`;
  it returns `False` when rejected. Registering after `mount()` gets no pages or links.
- Hooks can be unit-tested by calling the method directly with keyword arguments.

## Operating a plugin

- Settings: `Admin(plugin_settings={"audit": {"keep": 200}})` or `HYPERADMIN_AUDIT_KEEP=200`
  (with a `BaseSettings` model). Invalid settings skip the plugin and log the error.
- Disable: `Admin(disabled_plugins=["audit"])` or `HYPERADMIN_DISABLED_PLUGINS=audit`; skip all
  discovery with `HyperAdminSettings(plugins_enabled=False)`.
- Inspect: `hyperadmin plugins list` (entry points, no import), `admin.plugins.names()`.
- A plugin that owns tables declares them on its own `MetaData` (as `hyperadmin-reports` does
  with `dashboard_metadata()`), so they do not appear in the host's migrations uninvited, and
  documents the DDL.
