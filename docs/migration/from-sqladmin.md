# Migrating from SQLAdmin

SQLAdmin and HyperAdmin both mount on a FastAPI (or Starlette) app and both read SQLAlchemy
models, so this is the shortest of the three migrations: **your models and your database do not
change**. You rewrite the admin classes, the way the admin is mounted, and the authentication
backend.

This guide maps SQLAdmin concepts to HyperAdmin, ports a small blog admin step by step, and lists
what has [no equivalent yet](#no-equivalent-yet). SQLAdmin's side of each comparison follows
[the SQLAdmin documentation](https://aminalaee.github.io/sqladmin/).

## Concept mapping

### Application and registration

| SQLAdmin | HyperAdmin | Notes |
|---|---|---|
| `Admin(app, engine)` | `Admin(app, engine=engine)` then `admin.mount("/admin")` | The engine must be an `AsyncEngine`. `session_factory=` takes your `async_sessionmaker` instead |
| `base_url="/admin"` | The path given to `admin.mount()` | |
| `title="..."` | `HyperAdminSettings(site_title="...")` | |
| `admin.add_view(PostAdmin)` | `site.register(Post, PostAdmin)` | `from hyperadmin.core.registry import site`. Register before `admin.mount()` |
| `class PostAdmin(ModelView, model=Post)` | `class PostAdmin(ModelAdmin)` | `from hyperadmin.core.model import ModelAdmin`. The model is given to `site.register` |
| `name`, `name_plural` | `verbose_name`, `verbose_name_plural` | |
| `icon` (a Font Awesome class) | `icon` (a Lucide icon name, for example `"file-text"`) | The names are the files in `hyperadmin/static/icons` |
| `category` | `nav_group` | Order and icon of a group: `Admin(nav_groups=[NavGroup(...)])`. See [Navigation, Lists & Keyboard](../guides/navigation.md) |
| `templates_dir` | `HyperAdminSettings(template_dirs=[...])` | See [Override templates](../getting-started.md#override-templates) |
| `BaseView` with `@expose` | A router added with `admin.plugins.add_page(...)` | See [Your own pages in the sidebar](../guides/navigation.md#your-own-pages-in-the-sidebar) |

### `ModelView` options

| SQLAdmin `ModelView` | HyperAdmin | Notes |
|---|---|---|
| `column_list` | `list_display` | Strings, not model attributes: `["title", "author"]`. Inferred when unset |
| `column_searchable_list` | `search_fields` | Strings. Inferred when unset; `[]` turns search off |
| `column_filters` | `list_filter` | Field names, or filter objects from `hyperadmin.filters` |
| `column_sortable_list` | No option | Every listed column that is a model field can be sorted |
| `form_columns` | `AdminOptions(form_fields=[...])` | Names the foreign-key column (`author_id`), not the relationship |
| `form_ajax_refs` | Automatic | A foreign key renders as a searchable select. Above `AdminOptions.preload_threshold` rows (500 by default) it loads options as you type |
| `can_create`, `can_edit`, `can_delete`, `can_view_details` | `AdminOptions(can_create=, can_edit=, can_delete=, can_detail=)` | `can_list` also exists |
| `@action(name=, label=, ...)` | `@action(label="...", bulk=True)` | `from hyperadmin.core.actions import action`. See [Actions](#actions) |
| `list_query`, `count_query` | `get_queryset(request)` returning a `dict` | Equality filters, `{"column": value}`, added to every list and detail query |
| `is_accessible(request)`, `is_visible(request)` | Permission codenames | See [Authentication and permissions](#authentication-and-permissions) |
| `column_exclude_list`, `form_excluded_columns` | No option | List the fields you want in `list_display` and `form_fields` |
| `column_default_sort` | No option | |
| `page_size`, `page_size_options` | No per-model option | Global only: `HyperAdminSettings(items_per_page=...)` (`HYPERADMIN_ITEMS_PER_PAGE`, default 10, at most 100). Users pick 10, 25, 50 or 100 rows below the table; the choices are fixed |
| `column_labels`, `column_formatters`, `column_details_list` | No option | See [No equivalent yet](#no-equivalent-yet) |
| `on_model_change`, `after_model_change`, `on_model_delete`, `after_model_delete` | No hook | See [No equivalent yet](#no-equivalent-yet) |
| `can_export`, `column_export_list` | No export | |

`AdminOptions` has more than the table shows: fieldsets, inline related rows, inline list editing,
detail-page panels. The [Views reference](../api/views.md) lists every field.

## Port a small admin

The example is a blog with authors and posts.

### The models stay as they are

Both admins read these models. Nothing in this file changes.

<!-- run: blog -->
```python
# models.py
import enum
from datetime import datetime

from sqlalchemy import ForeignKey, String, Text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class PostStatus(enum.Enum):
    draft = "draft"
    published = "published"


class Author(Base):
    __tablename__ = "authors"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(100))
    email: Mapped[str] = mapped_column(String(254), unique=True)

    posts: Mapped[list["Post"]] = relationship(back_populates="author")

    def __str__(self) -> str:
        return self.name


class Post(Base):
    __tablename__ = "posts"

    id: Mapped[int] = mapped_column(primary_key=True)
    title: Mapped[str] = mapped_column(String(200))
    body: Mapped[str] = mapped_column(Text, default="")
    status: Mapped[PostStatus] = mapped_column(default=PostStatus.draft)
    published_at: Mapped[datetime | None]
    author_id: Mapped[int] = mapped_column(ForeignKey("authors.id"))

    author: Mapped[Author] = relationship(back_populates="posts")

    def __str__(self) -> str:
        return self.title
```

SQLModel `table=True` models work the same way.

### Before: SQLAdmin

```python
# main.py
import os

from fastapi import FastAPI
from sqladmin import Admin, ModelView, action
from sqladmin.authentication import AuthenticationBackend
from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from starlette.requests import Request
from starlette.responses import RedirectResponse

from models import Author, Post, PostStatus

engine = create_async_engine("sqlite+aiosqlite:///blog.db")
app = FastAPI()


class AdminAuth(AuthenticationBackend):
    async def login(self, request: Request) -> bool:
        form = await request.form()
        if form["username"] == "admin" and form["password"] == os.environ["ADMIN_PASSWORD"]:
            request.session.update({"user": "admin"})
            return True
        return False

    async def logout(self, request: Request) -> bool:
        request.session.clear()
        return True

    async def authenticate(self, request: Request) -> bool:
        return "user" in request.session


class AuthorAdmin(ModelView, model=Author):
    name_plural = "Authors"
    icon = "fa-solid fa-user"
    column_list = [Author.name, Author.email]
    column_searchable_list = [Author.name, Author.email]


class PostAdmin(ModelView, model=Post):
    name_plural = "Blog posts"
    icon = "fa-solid fa-newspaper"
    column_list = [Post.title, Post.author, Post.status, Post.published_at]
    column_searchable_list = [Post.title, Post.body]
    column_sortable_list = [Post.title, Post.published_at]
    form_columns = [Post.title, Post.body, Post.author, Post.status, Post.published_at]
    can_delete = False

    @action(name="publish", label="Publish", confirmation_message="Publish the selected posts?")
    async def publish(self, request: Request) -> RedirectResponse:
        pks = [int(pk) for pk in request.query_params.get("pks", "").split(",") if pk]
        async with AsyncSession(engine) as session:
            await session.execute(
                update(Post).where(Post.id.in_(pks)).values(status=PostStatus.published)
            )
            await session.commit()
        return RedirectResponse(request.url_for("admin:list", identity=self.identity))


admin = Admin(app, engine, authentication_backend=AdminAuth(secret_key=os.environ["SECRET_KEY"]))
admin.add_view(AuthorAdmin)
admin.add_view(PostAdmin)
```

### Step 1: install

Install HyperAdmin:

```bash
pip install hyper-admin==1.0.0
```

Both admins can be mounted on the same app at different paths while you migrate.

### Step 2: port the `ModelView` classes

<!-- run: blog -->
```python
# admin.py
from typing import Any, ClassVar

from fastapi import Request

from hyperadmin.core.actions import action
from hyperadmin.core.model import ModelAdmin
from hyperadmin.core.options import AdminOptions
from hyperadmin.core.registry import site


class AuthorAdmin(ModelAdmin):
    verbose_name_plural = "Authors"
    icon = "user"
    list_display: ClassVar[list[str]] = ["name", "email"]
    search_fields: ClassVar[list[str]] = ["name", "email"]


class PostAdmin(ModelAdmin):
    verbose_name_plural = "Blog posts"
    icon = "file-text"
    list_display: ClassVar[list[str]] = ["title", "author", "status", "published_at"]
    search_fields: ClassVar[list[str]] = ["title", "body"]
    options: ClassVar[AdminOptions] = AdminOptions(
        form_fields=["title", "body", "author_id", "status", "published_at"],
        can_delete=False,
    )

    @action(label="Publish", bulk=True)
    async def publish(self, request: Request, item_id: int, *, params: Any = None) -> None:
        await self.adapter.update(item_id, {"status": PostStatus.published})


site.register(Author, AuthorAdmin)
site.register(Post, PostAdmin)
```

What changed:

- The model is passed to `site.register`, not to the class statement.
- Columns are named by strings. `list_display`, `search_fields`, `list_filter` and
  `list_editable` are class attributes; every other option goes in an `AdminOptions` object on
  the class (`options = ...`) or passed to `site.register(Post, options=AdminOptions(...))`.
- `list_display` can name the relationship (`author`), which shows the related row's `__str__`.
  `form_fields` names the foreign-key column (`author_id`).
- `can_delete=False` removes the delete button and the delete route.
- There is no `column_sortable_list`: the title, status and date columns can all be sorted.

#### Actions

A SQLAdmin action receives the request once, reads the selected keys from `pks`, and returns a
response. A HyperAdmin bulk action is an `async` method that is called **once for each selected
row** with that row's primary key. The admin then shows a result for each row, so the method
returns nothing. Raise `fastapi.HTTPException` to mark one row as failed.

- `@action(label="Publish", bulk=True)` adds the action to the list page. The method must accept
  a keyword-only `params` argument.
- `@action(label="Publish")` without `bulk=True` adds a button for a single record. The method
  signature is `(self, request, item_id)`.
- `form=SomePydanticModel` (with `bulk=True`) asks the user for parameters first and passes the
  validated model as `params`.

`self.adapter` reads and writes rows of the model (`get`, `update`), so the action needs no
session of its own.

### Step 3: port the authentication backend and mount the admin

SQLAdmin's `AuthenticationBackend` does three jobs. In HyperAdmin they are three settings of
`ExternalAuth`:

| SQLAdmin `AuthenticationBackend` | HyperAdmin `ExternalAuth` |
|---|---|
| `login(request)`: check the submitted credentials | `TokenCookie(token_endpoint=issue_token)`: a function `issue_token(username, password)` that returns a token, or `None` to refuse. The admin serves the login form at `/admin/login` |
| `authenticate(request)`: is this request signed in? | `get_user`: a FastAPI dependency that returns the user, or `None` for an anonymous request |
| `logout(request)` | Built in: the admin clears its cookie and redirects to `logout_url` |

<!-- run: blog -->
```python
# main.py
import os
import secrets
from dataclasses import dataclass

from fastapi import FastAPI, Request
from itsdangerous import BadSignature, URLSafeTimedSerializer
from sqlalchemy.ext.asyncio import create_async_engine

from hyperadmin import Admin
from hyperadmin.auth import ExternalAuth, TokenCookie

engine = create_async_engine("sqlite+aiosqlite:///blog.db")
app = FastAPI()
signer = URLSafeTimedSerializer(os.environ["SECRET_KEY"])


@dataclass
class AdminUser:
    id: str
    username: str
    is_superuser: bool = True


def issue_token(username: str, password: str) -> str | None:
    if username == "admin" and secrets.compare_digest(password, os.environ["ADMIN_PASSWORD"]):
        return signer.dumps({"sub": username})
    return None


def get_user(request: Request) -> AdminUser | None:
    scheme, _, token = request.headers.get("Authorization", "").partition(" ")
    if scheme.lower() != "bearer":
        return None
    try:
        claims = signer.loads(token, max_age=8 * 3600)
    except BadSignature:
        return None
    return AdminUser(id=claims["sub"], username=claims["sub"])


admin = Admin(
    app,
    engine=engine,
    auth=ExternalAuth(
        get_user=get_user,
        token_cookie=TokenCookie(token_endpoint=issue_token),
    ),
)
admin.mount("/admin")
```

How it works:

- An anonymous browser is sent to `/admin/login`. The form posts the credentials to
  `issue_token`, and the admin keeps the returned token in its own `HttpOnly` cookie.
- On every admin request the admin turns the cookie back into an `Authorization: Bearer` header,
  and `get_user` validates it.
- The admin's CSRF protection is on in this mode, so set `HYPERADMIN_SECRET_KEY` in the
  environment as well.

In a project with several files, import `admin.py` before `admin.mount()`, or let HyperAdmin
import it with `HyperAdminSettings(discover_apps=["yourpackage"])`.

Saved views and pinned sidebar pages are stored for each user in two tables,
`hyperadmin_saved_view` and `hyperadmin_nav_pin`. Until they exist the admin works without those
two features and logs the missing table. [Tables and migrations](../guides/existing-app.md#5-tables-and-migrations)
has the DDL.

If your app already has a login page or issues tokens, pass its dependency as `get_user` and
skip `issue_token`. [Bring Your Own Auth](../guides/external-auth.md) covers cookie sessions,
bearer tokens and single-page apps.

## Authentication and permissions

| SQLAdmin | HyperAdmin |
|---|---|
| `AuthenticationBackend.authenticate(request)` | `ExternalAuth(get_user=...)` |
| `AuthenticationBackend.login` and the built-in login page | `TokenCookie(token_endpoint=...)`, or your app's own login page with `ExternalAuth(login_url="/login")` |
| `AuthenticationBackend.logout` | `ExternalAuth(logout_url="/")` |
| Everyone who passes `authenticate` can open the admin | `ExternalAuth(can_access=...)`. By default the user needs a truthy `is_superuser` or `is_staff` |
| `ModelView.is_accessible(request)` | `ExternalAuth(has_permission=...)`: a function `has_permission(user, codename)` asked for `view_post`, `add_post`, `change_post`, `delete_post` and `action_<name>_post` |
| `ModelView.is_visible(request)` | The sidebar lists only the models the user holds `view_<model>` on |
| No per-row rule | `AdminOptions(object_permission_checker=...)` and `ModelAdmin.get_queryset(request)` |

The defaults are stricter than SQLAdmin's. Without `has_permission`, a user with a truthy
`is_superuser` gets every permission and every other user can only view. The example's
`AdminUser` sets `is_superuser = True` to keep SQLAdmin's behaviour: whoever signs in can do
everything.

HyperAdmin also has built-in auth, with its own user, group and permission tables, a login page
and `hyperadmin createsuperuser`. Use it when the admin should manage its own accounts:

<!-- run: builtin -->
```python
from hyperadmin.auth.permissions import ModelPermissionChecker, PermissionSyncService
from hyperadmin.auth.session import SessionAuthBackend

admin = Admin(
    app,
    engine=engine,
    auth_backend=SessionAuthBackend(engine=engine),
    permission_checker=ModelPermissionChecker(engine=engine),
    permission_registry=PermissionSyncService(engine=engine),
)
```

It needs the `hyperadmin_*` tables; see
[Tables and migrations](../guides/existing-app.md#5-tables-and-migrations).

## No equivalent yet

HyperAdmin does not have these SQLAdmin features today. Check the [roadmap](../roadmap.md)
before you plan around one.

| SQLAdmin feature | Status in HyperAdmin |
|---|---|
| A synchronous `Engine` | The engine must be async. An app that writes with a sync engine can give the admin an async engine on the same database |
| CSV export (`can_export`, `column_export_list`) | No export |
| `column_formatters`, `column_formatters_detail` | No per-column formatter. A property on the model can be listed in `list_display` |
| `column_labels` | No per-column label. Labels are derived from the field name |
| `column_details_list`, `column_details_exclude_list` | No per-model field list for the detail page. `AdminOptions(sensitive_fields=...)` hides a field everywhere |
| `column_default_sort` | No option |
| `page_size`, `page_size_options` | No per-model option; the global `items_per_page` setting sets the default page size, and the 10 / 25 / 50 / 100 choices are fixed |
| `on_model_change`, `after_model_change`, `on_model_delete`, `after_model_delete` | No per-admin save or delete hook. Plugin [lifecycle hooks](../plugins/hooks.md) observe the create, edit and delete views (not bulk actions or inline edits) but cannot change or veto a save. Rules that must always run belong in the model layer or the database |
| `list_query`, `count_query`, `search_query` returning statements | `get_queryset(request)` returns equality filters on the model's own columns only |
| `form_overrides`, `form_args`, `form_widget_args`, a custom `form` | Forms are generated from the model |
| A custom action that returns its own response | A bulk action returns nothing; the admin renders the per-row results |

## What you gain

Features with no direct SQLAdmin counterpart, each documented elsewhere on this site:

- Permission codenames per model and action, and per-row rules (above)
- Fieldsets, inline related rows and inline list editing ([Views reference](../api/views.md))
- Filter objects for date ranges and multiple choices, and per-user saved views
- [The command palette, pinned pages and keyboard shortcuts](../guides/navigation.md)
- [Live updates and presence](../guides/realtime.md)
- [Cursor pagination, cached and estimated counts for large tables](../guides/performance.md)
