---
name: hyperadmin-getting-started
description: Set up HyperAdmin in a FastAPI project - install the package, mount the admin, register a first model with a ModelAdmin, add sign-in, and run it. Use when the user says "add an admin to my FastAPI app", "install hyperadmin", "set up hyperadmin", "first ModelAdmin", "mount the admin", or starts a new project on HyperAdmin.
---

# Getting started with HyperAdmin

HyperAdmin is an admin interface for FastAPI. It reads SQLModel or SQLAlchemy 2.0 models through
an **async** engine and renders server-side pages with Jinja2 and HTMX. The distribution is
`hyper-admin`; the import name is `hyperadmin`.

Reference pages on the docs site: Getting Started, Tutorial, Add HyperAdmin to an existing app
(`docs/getting-started.md`, `docs/tutorial.md`, `docs/guides/existing-app.md` in the repository).

## Flow

1. **Check the project.** Find the FastAPI app object, how the engine or session is built, and
   whether models are SQLModel (`table=True`) or SQLAlchemy `DeclarativeBase`. A sync engine
   (`create_engine`, `psycopg2`, `pymysql`) needs an async counterpart for the admin
   (`sqlite+aiosqlite://`, `postgresql+asyncpg://`, `mysql+aiomysql://`). Both can point at the
   same database.
2. **Install.** HyperAdmin is in pre-release, so pin the version:
   `pip install hyper-admin==0.5.0a1` or `uv add hyper-admin==0.5.0a1`. Add the async driver
   (`aiosqlite` ships with HyperAdmin; add `asyncpg` for PostgreSQL).
3. **Mount the admin** (snippet below). Register models before `admin.mount()`.
4. **Pick auth** (section below). Without one, the admin has no login.
5. **Run** with `uvicorn main:app --reload` (or `fastapi dev main.py`) and open
   `http://localhost:8000/admin/`.
6. **Verify** with a TestClient test (last section).

## Minimal app

<!-- check: complete -->
```python
# main.py
from typing import ClassVar

from fastapi import FastAPI
from sqlalchemy.ext.asyncio import create_async_engine
from sqlmodel import Field, SQLModel

from hyperadmin import Admin
from hyperadmin.core.model import ModelAdmin
from hyperadmin.core.registry import site
from hyperadmin.core.settings import HyperAdminSettings


class Product(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    name: str
    price: float
    in_stock: bool = True


class ProductAdmin(ModelAdmin):
    icon = "package"  # a Lucide icon name
    list_display: ClassVar[list[str]] = ["name", "price", "in_stock"]
    search_fields: ClassVar[list[str]] = ["name"]
    list_filter: ClassVar[list[str]] = ["in_stock"]


engine = create_async_engine("sqlite+aiosqlite:///app.db")
app = FastAPI()
# create_tables=True creates SQLModel tables on startup: fine for a first run.
# In production keep your own migrations (Alembic) and leave it False (the default).
admin = Admin(app, engine=engine, settings=HyperAdminSettings(create_tables=True))

site.register(Product, ProductAdmin)
admin.mount("/admin")
```

Facts that matter:

- `site` (`hyperadmin.core.registry.site`) is a process-wide registry. Registering the same
  model twice raises `ValueError`; tests should call `site.unregister(Model)` in teardown.
- Without `list_display`, `search_fields` and `list_filter`, HyperAdmin infers them.
  `search_fields = []` turns search off.
- Instead of a `ModelAdmin` subclass you can pass options:
  `site.register(Product, options=AdminOptions(can_delete=False))`
  (`from hyperadmin.core.options import AdminOptions`).
- Every `HyperAdminSettings` field can come from a `HYPERADMIN_*` environment variable
  (`HYPERADMIN_DATABASE_URL`, `HYPERADMIN_SECRET_KEY`, `HYPERADMIN_DISCOVER_APPS='["myapp"]'`).
- Many files: put registrations in `myapp/admin.py` and set
  `HyperAdminSettings(discover_apps=["myapp"])`, or import that module before `mount()`.
- `HyperAdminSettings(auto_discover=True)` registers every SQLModel `table=True` model it finds.
  Plain SQLAlchemy models are not auto-discovered; register those explicitly.
- Passing neither `engine` nor `session_factory` runs demo mode on
  `HYPERADMIN_DATABASE_URL` (in-memory SQLite by default). An existing app passes its own:
  `Admin(app, session_factory=async_sessionmaker(...))`.
- Datetime columns: recent SQLModel versions reject naive datetimes on write. Use
  `Field(default_factory=lambda: datetime.now(timezone.utc))`.

## Auth: pick one mode

**Built-in auth** (users, groups, permissions stored in `hyperadmin_*` tables, login page at
`/admin/login`):

<!-- check: complete -->
```python
from fastapi import FastAPI
from sqlalchemy.ext.asyncio import create_async_engine

from hyperadmin import Admin
from hyperadmin.auth.permissions import ModelPermissionChecker, PermissionSyncService
from hyperadmin.auth.session import SessionAuthBackend

engine = create_async_engine("sqlite+aiosqlite:///app.db")
app = FastAPI()
admin = Admin(
    app,
    engine=engine,
    auth_backend=SessionAuthBackend(engine=engine),
    permission_checker=ModelPermissionChecker(engine=engine),
    permission_registry=PermissionSyncService(engine=engine),
)
admin.mount("/admin")
```

Then, in the shell:

```bash
export HYPERADMIN_SECRET_KEY="$(python -c 'import secrets; print(secrets.token_urlsafe(32))')"
hyperadmin init-db --database-url sqlite+aiosqlite:///app.db
hyperadmin createsuperuser --database-url sqlite+aiosqlite:///app.db
```

The app refuses to start without `HYPERADMIN_SECRET_KEY` when auth is configured. Permission
codenames per model are `view_<model>`, `add_<model>`, `change_<model>`, `delete_<model>`
(lowercased class name), plus `action_<action>_<model>` for each `@action`.

**Your own auth** (reuse the host app's users and login):

<!-- check: complete -->
```python
from fastapi import FastAPI, Request
from sqlalchemy.ext.asyncio import create_async_engine

from hyperadmin import Admin
from hyperadmin.auth import ExternalAuth

engine = create_async_engine("sqlite+aiosqlite:///app.db")
app = FastAPI()


async def get_current_user(request: Request) -> object | None:
    """Return your user object, or None when nobody is signed in."""
    return getattr(request.state, "user", None)


admin = Admin(
    app,
    engine=engine,
    auth=ExternalAuth(
        get_user=get_current_user,
        can_access=lambda user: bool(getattr(user, "is_staff", False)),
        has_permission=lambda user, codename: bool(getattr(user, "is_superuser", False)),
        login_url="/login",
    ),
)
admin.mount("/admin")
```

`get_user` is a normal FastAPI dependency. By default a user may open the admin when
`is_superuser` or `is_staff` is truthy; superusers get every permission and other users are
view-only until `has_permission` says otherwise. Bearer-token apps use
`ExternalAuth(token_cookie=TokenCookie(...))`; see the Bring Your Own Auth guide
(`docs/guides/external-auth.md`). OAuth sign-in (GitHub, Google) needs the `oauth` extra; see
`docs/guides/oauth-sso.md`.

## Lifespan

If the host app has a lifespan, compose the admin's:

```python
@asynccontextmanager
async def lifespan(app: FastAPI):
    async with admin.lifespan():
        yield
```

Without it the first admin request runs startup. With realtime enabled
(`Admin(realtime=RealtimeSettings(...))`) composing the lifespan is required.

## Verify

<!-- check: complete -->
```python
# tests/test_admin.py
from fastapi.testclient import TestClient

from main import app


def test_admin_lists_products() -> None:
    with TestClient(app) as client:
        created = client.post(
            "/admin/product", data={"name": "Lamp", "price": "12.5"}, follow_redirects=False
        )
        assert created.status_code == 303
        page = client.get("/admin/product")
        assert page.status_code == 200
        assert "Lamp" in page.text
```

URLs: the list of model `Product` is `/admin/product`, a record is `/admin/product/<pk>`, the
create form posts to `/admin/product`. Next steps: the `hyperadmin-define-ui` skill for list,
form and detail options; `hyperadmin-extend-ui` for templates and CSS; `hyperadmin-new-plugin`
for pages of your own.
