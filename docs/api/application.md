# Application

## Usage

```python
from fastapi import FastAPI
from sqlalchemy.ext.asyncio import create_async_engine
from hyperadmin import Admin

app = FastAPI()
engine = create_async_engine("sqlite+aiosqlite:///app.db")

# Minimal setup — register models manually then mount
admin = Admin(app, engine=engine)
admin.mount("/admin")

# Auto-discover admin.py files in your app packages
admin = Admin(app, engine=engine, discover_apps=["myapp", "otherapp"])
admin.mount("/admin")
```

## Parameters

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `app` | `FastAPI` | required | The FastAPI application instance |
| `engine` | `AsyncEngine` | built-in SQLite | Async SQLAlchemy engine |
| `discover_apps` | `list[str] \| None` | `None` | Module paths to auto-discover `admin.py` in |
| `create_tables` | `bool` | `False` | Create every SQLModel table in `admin.startup()`. In demo mode (no `engine=`/`session_factory=`), tables are created automatically only for SQLite URLs. Otherwise use `admin.create_tables(scope=...)` or `hyperadmin init-db` |
| `template_dirs` | `list[str] \| None` | `None` | Extra Jinja2 template search paths |
| `mount_mode` | `"isolated" \| "router"` | `"isolated"` | `"isolated"` mounts the admin as a private sub-application (see below). `"router"` is the deprecated legacy mode, removed in 0.6 |
| `route_namespace` | `str` | `"hyperadmin"` | Name of the admin mount; admin route names resolve as `hyperadmin:user-list` |

## Isolated mount

`admin.mount("/admin")` builds a private FastAPI sub-application and attaches it with
`app.mount("/admin", ..., name="hyperadmin")`:

- the admin's locale, session and authentication middleware wrap admin requests only, so host
  routes get no `Content-Language` header and no admin cookie;
- the admin's static files are served from `/admin/static`, and the realtime WebSocket from
  `/admin/realtime/ws`; a host `/static` mount is left alone;
- admin routes are not in the host's `/openapi.json`, and their names are namespaced
  (`app.url_path_for("hyperadmin:user-list")`);
- the sub-application shares the host's `dependency_overrides` and `state`.

To serve your own page inside the admin (behind its login), add a route to `admin.asgi_app` after
`mount()`, and resolve admin URLs with `hyperadmin.views.urls.admin_url_for(request, name)`.

`admin.mount("/")` always uses router mode, because a sub-application mounted at the root
would shadow every host route.

Links and redirects the admin builds (login, logout, MFA, `{{ admin_prefix }}` in templates) use
the per-request admin path, so a host served under a `root_path` (for example `/api`) gets
`/api/admin/...`.

Uploaded files are served per record under the admin prefix, at
`{prefix}/{model}/{item_id}/file/{field}`, behind the admin's authentication, model and
object permissions and `get_queryset` scoping. There is no public `/uploads` mount any more;
`settings.public_uploads_path` restores one as a logged escape hatch (see
[File Uploads](../guides/file-uploads.md)).

## API Reference

::: hyperadmin.core.app.Admin

---

Next: [Views](views.md)