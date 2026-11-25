# Writing a Plugin

This page builds a small plugin, `hyperadmin-audit`, from an empty package to a tested one. It
logs every record created through the admin and shows the latest ones on its own admin page.

You need a Python package of your own and HyperAdmin installed. The plugin lives in that package,
not in your application.

## 1. The minimal plugin

A plugin is any object with a `name` and an `on_register(admin)` method:

```python title="src/hyperadmin_audit/plugin.py"
class AuditPlugin:
    name = "audit"

    def on_register(self, admin):
        self.admin = admin
```

There is no base class to inherit. HyperAdmin checks the shape with the runtime-checkable
`hyperadmin.Plugin` protocol, which you can use as a type hint.

`name` is the plugin's identity. It appears in URLs, static paths, settings keys, the disable list
and log records. It must start with a lowercase letter and contain only lowercase letters, digits,
`_` and `-`.

## 2. Declare the entry point

HyperAdmin finds plugins through the `hyperadmin.plugins` entry-point group. Add yours to the
package's `pyproject.toml`:

```toml title="pyproject.toml"
[project.entry-points."hyperadmin.plugins"]
audit = "hyperadmin_audit.plugin:AuditPlugin"
```

The entry-point name (`audit`) must equal the plugin's `name` attribute. If they differ, the plugin
is skipped as `invalid`.

The value can point at a class or at an instance. A class is instantiated with no arguments, once
per `Admin`.

After `pip install -e .`, the plugin shows up in `hyperadmin plugins list`, and every `Admin(...)`
in that environment loads it.

## 3. Implement `on_register`

`on_register(admin)` runs once, while `Admin(...)` is being constructed. It is the only place
where a plugin can add to the admin's UI, through `admin.plugins`:

| Method | Adds |
|---|---|
| `add_page(self, router, prefix=None)` | A FastAPI `APIRouter` served inside the admin, under `/<name>` by default. |
| `add_nav_entry(self, label=, url_name=, ...)` | A sidebar link to a named admin route. |
| `add_template_dir(self, path)` | A template directory, searched after the host's and HyperAdmin's own. |
| `set_static_dir(self, path)` | One static directory, served at `{prefix}/static/plugins/<name>/`. |
| `add_permission(self, codename, name=None)` | A permission codename that can be granted to groups. |

Each method takes the plugin itself as the first argument. Calling one outside your own
`on_register` raises `PluginError`.

Here is the audit plugin with a page, a sidebar link, a permission and a setting:

```python title="src/hyperadmin_audit/plugin.py"
import logging
from collections import deque
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
from pydantic import BaseModel

logger = logging.getLogger("hyperadmin_audit")


class AuditSettings(BaseModel):
    keep: int = 50


class AuditPlugin:
    name = "audit"
    settings_model = AuditSettings

    def on_register(self, admin: Any) -> None:
        settings: AuditSettings = admin.plugins.settings(self.name)
        self.recent: deque[str] = deque(maxlen=settings.keep)

        router = APIRouter()

        @router.get("/", name="audit-index", response_class=HTMLResponse)
        async def index(request: Request) -> HTMLResponse:
            context = {"recent": list(self.recent)}
            return admin.templates.TemplateResponse(request, "audit/index.html", context)

        admin.plugins.add_page(self, router)
        admin.plugins.add_template_dir(self, Path(__file__).parent / "templates")
        admin.plugins.add_permission(self, "view_audit_log")
        admin.plugins.add_nav_entry(
            self, label="Audit log", url_name="audit-index", permission="view_audit_log"
        )
```

```jinja title="src/hyperadmin_audit/templates/audit/index.html"
{% extends "_base.html" %}

{% block title %}Audit log | {{ site_title | default("HyperAdmin") }}{% endblock %}

{% block content %}
  <h1 class="ha-page-title">Audit log</h1>
  <ul data-testid="audit-recent">
    {% for message in recent %}
      <li>{{ message }}</li>
    {% endfor %}
  </ul>
{% endblock %}
```

What this gives you:

- **Settings.** `settings_model` is an optional pydantic model. HyperAdmin validates the
  operator's `Admin(plugin_settings={"audit": {"keep": 200}})` into it before `on_register`
  runs, and `admin.plugins.settings(self.name)` returns the instance.
- **A page.** The route is served at `{prefix}/audit/`, behind the admin's login, CSRF check and
  error pages. Its name joins the `hyperadmin:` namespace, so prefix route names with your
  plugin name. Declare routes directly on the router you pass: a nested `include_router` or a
  mount is rejected and the page is not served.
- **A template.** Put templates in a folder named after the plugin and extend `_base.html` to
  get the admin layout. A plugin cannot override HyperAdmin's own templates; an operator can
  override yours by placing the same relative path in their template directory.
- **A permission and a link.** The link is hidden from users who lack `view_audit_log`. Hiding
  the link does not protect the page: check the codename in the route with
  `await admin.permission_checker.has_permission(request.state.user, "view_audit_log")`
  (`permission_checker` is `None` when the admin runs without authentication).

If `on_register` raises, the plugin is skipped and everything it added is rolled back. A page
prefix or permission codename that another plugin already uses raises `PluginError`, with the same
result.

The [navigation guide](../guides/navigation.md#your-own-pages-in-the-sidebar) covers sidebar
groups, icons and ordering.

## 4. Add a hook handler

A hook handler is a method named after the hook. Add this one to `AuditPlugin`:

```python title="src/hyperadmin_audit/plugin.py"
    def on_after_create(self, *, model: type, instance: Any, **kwargs: Any) -> None:
        message = f"created {model.__name__}: {instance!r}"
        self.recent.append(message)
        logger.info(message)
```

HyperAdmin calls it after every record created through the admin's create form. The rules:

- Hooks are plain `def` methods. An `async def` hook is ignored, with one `ERROR` log line.
- Arguments are passed by keyword. Name the ones you use and end the signature with `**kwargs`,
  so the handler keeps working when a later release passes one more argument.
- The return value is ignored. Hooks observe; they cannot change or veto the operation.
- Implement only the hooks you need. A hook you do not define costs nothing.

HyperAdmin finds handlers by looking up the hook name on the registered plugin object, so the
plugin needs its `name` attribute and the method must be reachable as `plugin.on_after_create`.

The [hook reference](hooks.md) lists every hook with its arguments and timing.

## 5. Test the plugin

You do not need to install the package to test discovery. Replace the `entry_points` function
that the registry calls with one that returns your entry point, then build an admin as usual:

```python title="tests/test_audit_plugin.py"
import logging
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
        name="audit",
        value="hyperadmin_audit.plugin:AuditPlugin",
        group="hyperadmin.plugins",
    )
    monkeypatch.setattr(plugins_module, "entry_points", lambda *, group: [entry_point])
    monkeypatch.delenv("HYPERADMIN_DISABLED_PLUGINS", raising=False)

    engine = create_async_engine("sqlite+aiosqlite:///:memory:")

    async def create_schema() -> None:
        async with engine.begin() as conn:
            await conn.run_sync(SQLModel.metadata.create_all)

    anyio.run(create_schema)
    admin = Admin(FastAPI(), engine=engine, settings=HyperAdminSettings(create_tables=False))
    site.register(Note)
    admin.mount("/admin")
    yield admin
    site.unregister(Note)


def test_plugin_is_discovered(admin: Admin) -> None:
    assert "audit" in admin.plugins
    assert admin.plugins.skipped == {}


def test_create_is_logged(admin: Admin, caplog: pytest.LogCaptureFixture) -> None:
    client = TestClient(admin.app)
    with caplog.at_level(logging.INFO, logger="hyperadmin_audit"):
        response = client.post("/admin/note", data={"text": "hello"}, follow_redirects=False)
    assert response.status_code == 303
    assert "created Note" in caplog.text

    page = client.get("/admin/audit/")
    assert page.status_code == 200
    assert "created Note" in page.text
```

Points to note:

- Patch `entry_points` in the `hyperadmin.core.plugins` module, the name the registry looks
  up, not `importlib.metadata.entry_points`.
- The fake must accept the `group` keyword. A real `EntryPoint` imports your class through its
  `value`, so the test also proves that the path in `pyproject.toml` is right.
- Clear `HYPERADMIN_DISABLED_PLUGINS`, so a variable in the developer's shell cannot disable the
  plugin under test.
- `admin.plugins.skipped` tells you why a plugin did not load. Assert on it and a failing test
  names the reason.

To test a hook without discovery, register the plugin by hand before `mount()`:

```python
admin.plugins.register(AuditPlugin(), admin=admin)
```

`register` returns `False` when the plugin was rejected.

## Common pitfalls

**Per-request state on the plugin.** One plugin object serves every request of the process, and
requests overlap. Do not keep "the current user" or "the current record" on `self` between a
`before` hook and its `after` hook. Use a `contextvars.ContextVar`, or key the state by something
both hooks receive. The `recent` list above is safe because it is process-wide on purpose. It is
also per process: with several workers each one has its own.

**Slow or blocking hooks.** Hooks are synchronous and run inside the request, on the event loop.
A hook that calls a remote service or runs a query delays that request and every other request
of the worker. Hand slow work to a queue or a background task and return.

**Counting on exceptions.** An exception raised by a hook is logged and swallowed. The save still
happens and the user sees no error, so a hook cannot be used to block an operation. For that, use
model validation or a permission check.

**Changing the arguments.** `data`, `kwargs` and `instance` are the live objects the admin is
working with. Treat them as read-only: a change may or may not reach the database, and it will
confuse the next plugin in line.

**Assuming every write passes the CRUD hooks.** `on_before_create` and its siblings fire from the
create, edit and delete forms only. Inline cell edits and inline child rows, for example, reach
the database without them. To see every write, use the
[adapter-call hooks](hooks.md#adapter-calls).

**Registering late.** A plugin registered by hand after `admin.mount()` gets no pages or sidebar
links, and may get no adapter-call hooks. Register before `mount()`.

**Logging secrets.** `on_validation_error` and `on_auth_event` are built to carry no input values
and no password. `data`, `instance` and adapter `kwargs` do carry field values: filter them
before you log or export them.
