# Add HyperAdmin to an existing FastAPI app

This guide adds HyperAdmin to a FastAPI application that already exists: it has
its own models, its own database engine and migrations, its own lifespan and
its own login. The admin plugs into all of them. It does not take over the
app.

When you mount the admin at `/admin`, nothing outside `/admin` changes:

- nothing is mounted at the root (the admin's assets live under `/admin/static`);
- no middleware is added to the host app;
- no tables are created unless you ask for it;
- no cookie named `session` is set, and your own session cookie is left alone;
- admin route names (`hyperadmin:*`) do not clash with yours;
- your `/openapi.json` gets no admin entries.

A complete, runnable version of everything below is in
[`examples/byoa/`](https://github.com/yevheniidehtiar/hyper-admin/tree/develop/examples/byoa).

## Before you start

You need:

- a FastAPI app with SQLModel models (int, UUID or natural `str` primary keys all work);
- an async SQLAlchemy engine (`sqlite+aiosqlite`, `postgresql+asyncpg`, ...) or an
  `async_sessionmaker` built on it;
- a FastAPI dependency that returns the current user, or `None` for an anonymous
  request. Most apps already have one, for example `get_current_user`.

Install the package. The distribution is `hyper-admin`; the import name is `hyperadmin`:

```bash
pip install hyper-admin==0.5.0a1
```

## The minimal wiring

<!-- minimal-wiring -->
```python
from hyperadmin import Admin
from hyperadmin.auth import ExternalAuth
from hyperadmin.core.registry import site

from myapp.auth import get_current_user  # your existing dependency
from myapp.db import sessionmaker  # your async_sessionmaker
from myapp.main import app
from myapp.models import Country, Project

site.register(Project)
site.register(Country)

admin = Admin(
    app,
    session_factory=sessionmaker,
    auth=ExternalAuth(get_user=get_current_user, login_url="/login"),
)
admin.mount("/admin")
```

Then set a secret key, which signs the admin's CSRF tokens:

```bash
export HYPERADMIN_SECRET_KEY="$(python -c 'import secrets; print(secrets.token_urlsafe(32))')"
```

That is all. Start your app and open `/admin/`. An anonymous browser is sent to
`/login?next=%2Fadmin%2F`; once your login has run, `get_current_user` returns
the user and the admin opens.

Without a secret key, `Admin(...)` raises `ValueError` at startup: with `auth=`
the admin enforces CSRF, and the default key is refused. Set
`HYPERADMIN_DEBUG=true` to accept the default key during local development.

The rest of this guide explains each part and the choices you may want to make.

## 1. Register your models

`site.register(Model)` adds a model to the admin with inferred list columns,
search fields and filters. To configure a model, pass a `ModelAdmin` subclass:

```python
from hyperadmin.core.model import ModelAdmin


class ProjectAdmin(ModelAdmin):
    list_display = ["name", "country_code"]


site.register(Project, ProjectAdmin)
```

Register models before `admin.mount()`: the routes are built when the admin is
mounted.

Primary keys are detected from the SQLAlchemy mapper, so `int`, `uuid.UUID`
and natural `str` keys work in every view, form, inline, bulk action and popup.
A malformed key in a URL returns 404. Two limits apply to `str` keys:

- a key that contains `/` cannot be reached (Starlette matches on the decoded path);
- a key equal to a literal route segment (`create`, `choices`, ...) is shadowed
  on GET by that route.

Keys cannot be changed after a row is created. A model with a composite primary
key is shown as a list only.

## 2. Reuse your engine or session factory

Pass whichever your app already has:

```python
admin = Admin(app, engine=engine, auth=...)  # an AsyncEngine
admin = Admin(app, session_factory=sessionmaker, auth=...)  # an async_sessionmaker
```

A host that only has a generator dependency such as `get_session()` can wrap it:
`session_factory=asynccontextmanager(get_session)`.

When you pass neither, the admin runs in *demo mode*: it builds its own engine
from `HYPERADMIN_DATABASE_URL` (an in-memory SQLite database by default). That
is for trying the admin out, not for an existing app.

## 3. Bring your own auth

`ExternalAuth(get_user=...)` makes your dependency guard every admin route.
FastAPI resolves it as a normal sub-dependency, so its own dependencies
(`OAuth2PasswordBearer`, `get_db`), `yield` dependencies, sync functions and
`app.dependency_overrides` all work as they do on your own routes. A dependency
that reads `request.app.state` works too: the admin sub-application shares the
host's `state`.

By default a user may open the admin when `is_superuser` or `is_staff` is
truthy. Superusers get full access; every other user is **view-only** until you
map your own permissions with `has_permission`. A user who is not a superuser
can never change or delete rows of your user model unless `has_permission`
explicitly allows it.

How the admin gets the user depends on how your app authenticates:

| Your app authenticates with | What to do |
|---|---|
| A cookie (server-side session, signed cookie) | Nothing more. The browser sends the cookie to `/admin` too. |
| A bearer token held by an SPA | Hand the token to the admin once: `TokenCookie()` plus `POST /admin/auth/session`. |
| A bearer token, and you do not want to touch the frontend | Let the admin serve its own login form: `TokenCookie(token_endpoint=...)`. |

For a bearer-only host that should not change its frontend at all, point the
admin at your token endpoint. The admin then serves a login form at
`/admin/login`, posts the credentials to that endpoint server side and keeps
the returned token in an `HttpOnly` cookie scoped to `/admin`:

```python
from hyperadmin.auth import ExternalAuth, TokenCookie

auth = ExternalAuth(
    get_user=get_current_user,
    token_cookie=TokenCookie(token_endpoint="/token"),  # or "auto", or a callable
)
```

[Bring your own auth](external-auth.md) covers every option, including the
token handoff, logout, permissions and WebSockets.

## 4. Compose the admin lifespan

The admin has a small startup step (table creation if you opted in, and
permission sync for built-in auth) and a shutdown step (draining realtime
connections). Compose both into your own lifespan:

```python
from contextlib import asynccontextmanager


@asynccontextmanager
async def lifespan(app: FastAPI):
    # ... your own startup ...
    async with admin.lifespan():
        yield
    # ... your own shutdown ...


app = FastAPI(lifespan=lifespan)
```

If you skip this, the first admin request runs the startup step for you. There
is no such safety net for shutdown: **if you enable realtime
(`Admin(realtime=RealtimeSettings(...))`), you must compose `admin.lifespan()`**,
or open SSE and WebSocket connections are not drained on a graceful shutdown.
The admin logs a one-time warning when realtime is on and startup came from the
first-request safety net.

`admin.startup()` and `admin.shutdown()` are also available if you prefer to
call them yourself. Both are idempotent.

## 5. Tables and migrations

The admin never runs DDL against your database unless you ask it to.
`create_tables` defaults to `False`, so your migrations stay the only thing that
changes your schema.

- **Your own models:** keep creating them with Alembic (or your own lifespan).
- **Bring-your-own-auth mode:** the admin needs no tables of its own. The built-in
  `hyperadmin_*` user, group and permission tables are not even registered on
  `SQLModel.metadata`, so Alembic autogenerate does not see them.
- **Built-in auth (`auth_backend=`):** create its tables with
  `hyperadmin init-db --database-url URL`, or include `hyperadmin.auth.metadata()`
  in your Alembic `target_metadata`.

Set `HYPERADMIN_CREATE_TABLES=true` to have startup create every table on
`SQLModel.metadata`, or call `await admin.create_tables(scope="hyperadmin")`
for the built-in auth tables only.

When a table is missing, the list page shows a banner telling you to run your
migrations or `hyperadmin init-db`, and the error is logged with its traceback.

### Upgrading the built-in auth tables

HyperAdmin ships no migration tool, so a column added to a `hyperadmin_*` table
in a new release is created on fresh databases by `hyperadmin init-db` and picked
up by Alembic autogenerate through `hyperadmin.auth.metadata()`. Existing
databases add it with their own migration. The column each release adds:

| Since | Table | Column | Alembic operation |
|---|---|---|---|
| v0.5.7 | `hyperadmin_groups` | `permissions_version` | `op.add_column("hyperadmin_groups", sa.Column("permissions_version", sa.Integer(), nullable=False, server_default="0"))` |

The downgrade is `op.drop_column("hyperadmin_groups", "permissions_version")`.

The same release adds two tables for the permission matrix, both part of
`hyperadmin.auth.metadata()` once `hyperadmin.permissions` is imported (the
matrix page imports it when it is registered):

| Since | Table | Purpose |
|---|---|---|
| v0.5.7 | `hyperadmin_permission_audit` | one row per permission change: `actor_key`, `group_id`, `action`, `model`, `codename`, `object_pk`, `before`, `after`, `created_at` |
| v0.5.7 | `hyperadmin_group_object_permissions` | the matrix's object rules: `group_id`, `model`, `codename`, `object_pk`, unique together |

Alembic autogenerate produces their `create_table` operations; written by
hand they are:

```python
op.create_table(
    "hyperadmin_permission_audit",
    sa.Column("id", sa.Integer(), primary_key=True),
    sa.Column("actor_key", sa.String(255), nullable=False),
    sa.Column("group_id", sa.Integer(), nullable=False),
    sa.Column("action", sa.String(64), nullable=False),
    sa.Column("model", sa.String(255), nullable=False),
    sa.Column("codename", sa.String(255), nullable=False),
    sa.Column("object_pk", sa.String(255), nullable=True),
    sa.Column("before", sa.Boolean(), nullable=False),
    sa.Column("after", sa.Boolean(), nullable=False),
    sa.Column("created_at", sa.DateTime(), nullable=False),
)
op.create_index("ix_hyperadmin_permission_audit_actor_key", "hyperadmin_permission_audit", ["actor_key"])
op.create_index("ix_hyperadmin_permission_audit_group_id", "hyperadmin_permission_audit", ["group_id"])
op.create_table(
    "hyperadmin_group_object_permissions",
    sa.Column("id", sa.Integer(), primary_key=True),
    sa.Column("group_id", sa.Integer(), sa.ForeignKey("hyperadmin_groups.id"), nullable=False),
    sa.Column("model", sa.String(255), nullable=False),
    sa.Column("codename", sa.String(255), nullable=False),
    sa.Column("object_pk", sa.String(255), nullable=False),
    sa.UniqueConstraint("group_id", "model", "codename", "object_pk", name="uq_group_object_rule"),
)
op.create_index("ix_hyperadmin_group_object_permissions_group_id", "hyperadmin_group_object_permissions", ["group_id"])
```

The downgrade is `op.drop_table("hyperadmin_group_object_permissions")` and
`op.drop_table("hyperadmin_permission_audit")`. Set `permissions_matrix_enabled=False` on
`HyperAdminSettings` to leave the matrix (and its sidebar entry) out of an
admin that has no groups to edit; the codename it gates on is
`permissions_matrix_codename` (default `change_groups_permissions`, superusers
always pass).

v0.5.6 adds one table for the filter library's saved views. It is part of
`hyperadmin.auth.metadata()` and of `SQLModel.metadata` as soon as the admin
views are imported (every mounted admin, in both auth modes), so autogenerate
sees it:

| Since | Table | Purpose |
|---|---|---|
| v0.5.6 | `hyperadmin_saved_view` | one row per saved filter set: `user_key`, `model`, `name`, `querystring`, `is_default`, `created_at`; `(user_key, model, name)` unique |

Written by hand:

```python
op.create_table(
    "hyperadmin_saved_view",
    sa.Column("id", sa.Integer(), primary_key=True),
    sa.Column("user_key", sa.String(255), nullable=False),
    sa.Column("model", sa.String(255), nullable=False),
    sa.Column("name", sa.String(255), nullable=False),
    sa.Column("querystring", sa.String(), nullable=False),
    sa.Column("is_default", sa.Boolean(), nullable=False),
    sa.Column("created_at", sa.DateTime(), nullable=False),
    sa.UniqueConstraint("user_key", "model", "name", name="uq_hyperadmin_saved_view_name"),
)
op.create_index("ix_hyperadmin_saved_view_user_key", "hyperadmin_saved_view", ["user_key"])
op.create_index("ix_hyperadmin_saved_view_model", "hyperadmin_saved_view", ["model"])
```

The downgrade is `op.drop_table("hyperadmin_saved_view")`. Until the table exists,
the list page logs a warning and leaves the saved-views panel out; set
`AdminOptions(saved_views_enabled=False)` on a model to leave its saved-view
endpoints unregistered as well. `user_key` is the stringified
`request.state.user_key`, so saved views work for host users in bring-your-own-auth
mode too.

`permissions_version` is the permission matrix's optimistic-concurrency stamp:
every grid an operator loads carries the group's current value, and a save is
only committed (and the stamp bumped, atomically with the permission rows) when
that value is still current. A stale grid therefore cannot overwrite a newer
save; it gets a 409 and reloads. Existing groups start at `0`. See
`docs/specs/permission-matrix-ui.md`.

## 6. Datetimes and timezones

Naive and timezone-aware columns both work, on every supported sqlmodel version
(including sqlmodel's own `UTCDateTime`). Aware values are shown and entered in
`HYPERADMIN_TIMEZONE` (default `UTC`). To use a per-user zone, set
`request.state.hyperadmin_timezone = ZoneInfo("Europe/Amsterdam")` in a
middleware or dependency of your own.

## 7. What lives under `/admin`

The admin is mounted as a private sub-application:

- its stylesheets and scripts are served from `/admin/static`, so your `/static` stays yours;
- its route names are namespaced: use `app.url_path_for("hyperadmin:project-list")`
  from host code;
- its cookies (`hyperadmin_csrf`, `hyperadmin_token`, `hyperadmin_locale`) are
  scoped to the admin path, which follows your app's `root_path` when it runs
  behind a path prefix;
- uploaded files are served per record at `/admin/{model}/{id}/file/{field}`,
  behind the admin's permission checks;
- `admin.asgi_app` is the sub-application, if you want to add your own routes behind the admin's middleware.

## 8. Going to production

- **Secret key.** Set `HYPERADMIN_SECRET_KEY` to a long random value.
- **TLS-terminating proxy.** The CSRF `Origin` check compares hosts, not schemes,
  so an https browser behind a proxy that talks plain http to your app is not
  refused. Still set `HYPERADMIN_COOKIE_SECURE=true`, or start uvicorn with
  `--forwarded-allow-ips` set to your proxy's address so the app sees `https`
  and marks cookies `Secure` on its own.
- **Other origins.** If the admin is reached through another hostname than the
  one in the request's `Host` header, list it in `HYPERADMIN_CSRF_TRUSTED_ORIGINS`
  (a JSON list, for example `'["https://admin.example.com"]'`).
- **Custom templates.** Every built-in page and HTMX request carries the CSRF
  token. A custom template with a raw `<form method="post">` needs
  `{{ csrf_input() }}` inside the form; your own JavaScript can read the token
  from `<meta name="csrf-token">` and send it as `X-CSRF-Token`.

## 9. Testing your app

Your existing tests keep working:

- `app.dependency_overrides[get_current_user] = lambda: fake_user` applies under
  `/admin` too, because the admin shares the host's overrides;
- an unsafe admin request (POST, DELETE, ...) needs the CSRF token. Read it from
  `<meta name="csrf-token">` on any admin page and send it as `X-CSRF-Token`, or
  build the admin with `HyperAdminSettings(csrf_mode="off")` in tests.

## Troubleshooting

| Symptom | Cause and fix |
|---|---|
| `ValueError: Auth or CSRF enforcement is enabled but no secret_key is configured` | Set `HYPERADMIN_SECRET_KEY`. |
| 401 page "Sign in to the host application" | `get_user` returned `None` and neither `login_url` nor `TokenCookie(token_endpoint=...)` is set. Set one of them. |
| 403 page naming `can_access` | The user is signed in but is neither `is_superuser` nor `is_staff`. Pass your own `ExternalAuth(can_access=...)`. |
| 403 on every save, with header `X-HyperAdmin-CSRF: failed` | A custom form or script sends no CSRF token, or a proxy changes the host. See "Going to production". |
| 422 on every admin page | `get_user` needs a query or path parameter. It must resolve from headers and cookies alone. |
| A list page shows a "table does not exist" banner | Run your migrations (or `hyperadmin init-db` for built-in auth tables). |

!!! note "Where the code differs from the design document"
    This guide follows the code as released. Two details differ from
    `docs/specs/bring-your-own-app.md`:

    - `admin.create_tables()` defaults to `scope="all"` (every table on
      `SQLModel.metadata`), not `"hyperadmin"`. Pass the scope explicitly.
    - The one-time warning about an https `Origin` on a plain-http request is
      logged by the built-in session middleware only, so a bring-your-own-auth
      admin behind a TLS proxy logs nothing. Set `HYPERADMIN_COOKIE_SECURE=true`
      yourself.
