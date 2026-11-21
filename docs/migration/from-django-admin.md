# Migrating from Django admin

This guide maps Django admin concepts to HyperAdmin and ports a small blog admin step by step.
It covers what HyperAdmin does today, and it lists what has [no equivalent yet](#no-equivalent-yet)
so you can decide before you start.

The largest change is not the admin. HyperAdmin runs inside a **FastAPI** application and reads
**SQLModel or SQLAlchemy** models through an **async** engine, so the models move from the Django
ORM to SQLAlchemy. The database can stay as it is: the new models can point at the tables Django
created.

Django's side of each comparison follows
[the Django admin site documentation](https://docs.djangoproject.com/en/stable/ref/contrib/admin/).

## Concept mapping

### Site and registration

| Django admin | HyperAdmin | Notes |
|---|---|---|
| `admin.site.urls` in `urls.py` | `Admin(app, engine=engine)` then `admin.mount("/admin")` | The admin is mounted on a FastAPI app |
| `admin.site.register(Post, PostAdmin)` | `site.register(Post, PostAdmin)` | `from hyperadmin.core.registry import site`. Register before `admin.mount()` |
| `@admin.register(Post)` | `site.register(Post, PostAdmin)` | There is no decorator form |
| `class PostAdmin(admin.ModelAdmin)` | `class PostAdmin(ModelAdmin)` | `from hyperadmin.core.model import ModelAdmin` |
| `admin.py` autodiscovery through `INSTALLED_APPS` | `HyperAdminSettings(discover_apps=["blog"])` | Imports `blog/admin.py`. `auto_discover=True` registers every SQLModel table without an `admin.py` |
| `AdminSite.site_title` | `HyperAdminSettings(site_title="...")` | Shown in the navbar and on the login page |
| `Meta.verbose_name`, `Meta.verbose_name_plural` on the model | `verbose_name`, `verbose_name_plural` on the `ModelAdmin` | Plain strings or `hyperadmin.gettext_lazy` |
| Models grouped by app on the index page | `nav_group`, `nav_order` and `icon` on the `ModelAdmin`; `Admin(nav_groups=[NavGroup(...)])` | See [Navigation, Lists & Keyboard](../guides/navigation.md) |

### List page

| Django `ModelAdmin` option | HyperAdmin | Notes |
|---|---|---|
| `list_display` | `list_display` | Class attribute, or `AdminOptions(list_display=[...])`. Names of model fields, relationships and properties. Inferred when unset |
| `search_fields` | `search_fields` | Inferred when unset; `[]` turns search off |
| `list_filter` | `list_filter` | Field names, or filter objects from `hyperadmin.filters` (`DateRangeFilter`, `MultiChoiceFilter`, `MultiFKFilter`, `BooleanFilter`) |
| `SimpleListFilter` subclass | `FilterDef` subclass | `from hyperadmin.filters import FilterDef` |
| `date_hierarchy` | `DateRangeFilter(field="published_at")` | A date-range filter, not a drill-down |
| `list_editable` | `list_editable` | Cells are edited in place |
| `list_select_related` | `AdminOptions(list_select_related=[...])` | Relations named in `list_display` are loaded automatically. See [Large Tables & Performance](../guides/performance.md) |
| `actions` | `@action(label="...", bulk=True)` methods | `from hyperadmin.core.actions import action`. See [Actions](#actions) |
| `ordering` | No option | Users sort by clicking a column heading |
| `list_per_page` | No option | |

### Forms and detail page

| Django `ModelAdmin` option | HyperAdmin | Notes |
|---|---|---|
| `fields` | `AdminOptions(form_fields=[...])` | Which fields the forms show, in order |
| `exclude` | `AdminOptions(form_fields=[...])` | List the fields you want; there is no exclude list |
| `fieldsets` | `AdminOptions(fieldsets=[FieldsetSpec(...)])` | `FieldsetSpec(name=, fields=, collapsed=, description=)` |
| `inlines` (`TabularInline`, `StackedInline`) | `AdminOptions(inlines=[InlineModelSpec(...)])` | One layout. `InlineModelSpec(model=, fk_field=, relationship_name=, fields=, extra=, max_num=)` |
| `autocomplete_fields`, `raw_id_fields` | Automatic | A foreign key renders as a searchable select. Above `AdminOptions.preload_threshold` rows (500 by default) it loads options as you type |
| `FileField`, `ImageField` | `fastapi-storages` column types | See [File Uploads](../guides/file-uploads.md) |
| `formfield_overrides`, a custom `form` | No option | Forms are generated from the model. Widgets are chosen from the field type; see [Widgets](../frontend/widgets.md) |
| `readonly_fields` | No option | See [No equivalent yet](#no-equivalent-yet) |

### Data and permissions

| Django admin | HyperAdmin | Notes |
|---|---|---|
| `get_queryset(request)` returning a `QuerySet` | `get_queryset(request)` returning a `dict` | The dict holds equality filters, `{"column": value}`, added to every list and detail query |
| `has_add_permission`, `has_change_permission`, `has_delete_permission`, `has_view_permission` | `AdminOptions(can_create=, can_edit=, can_delete=, can_list=, can_detail=)`, permission codenames, `AdminOptions(object_permission_checker=...)` | See [Authentication and permissions](#authentication-and-permissions) |
| `save_model`, `delete_model`, `save_formset` | No hook | See [No equivalent yet](#no-equivalent-yet) |
| Template overrides in `templates/admin/` | `HyperAdminSettings(template_dirs=[...])` | See [Override templates](../getting-started.md#override-templates) |
| `get_urls()` for extra admin pages | A router added with `admin.plugins.add_page(...)` | See [Your own pages in the sidebar](../guides/navigation.md#your-own-pages-in-the-sidebar) |

## Port a small admin

The example is a blog with authors, posts and comments.

### Before: Django

```python
# blog/models.py
from django.db import models


class Author(models.Model):
    name = models.CharField(max_length=100)
    email = models.EmailField(unique=True)

    def __str__(self):
        return self.name


class Post(models.Model):
    class Status(models.TextChoices):
        DRAFT = "draft", "Draft"
        PUBLISHED = "published", "Published"

    title = models.CharField(max_length=200)
    body = models.TextField(blank=True)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.DRAFT)
    published_at = models.DateTimeField(null=True, blank=True)
    author = models.ForeignKey(Author, on_delete=models.CASCADE, related_name="posts")

    def __str__(self):
        return self.title


class Comment(models.Model):
    post = models.ForeignKey(Post, on_delete=models.CASCADE, related_name="comments")
    name = models.CharField(max_length=100)
    text = models.TextField()
```

```python
# blog/admin.py
from django.contrib import admin

from .models import Author, Comment, Post


class CommentInline(admin.TabularInline):
    model = Comment
    extra = 1


@admin.register(Author)
class AuthorAdmin(admin.ModelAdmin):
    list_display = ["name", "email"]
    search_fields = ["name", "email"]


@admin.register(Post)
class PostAdmin(admin.ModelAdmin):
    list_display = ["title", "author", "status", "published_at"]
    list_filter = ["status", "author"]
    search_fields = ["title", "body"]
    fieldsets = [
        ("Content", {"fields": ["title", "body", "author"]}),
        ("Publishing", {"fields": ["status", "published_at"], "classes": ["collapse"]}),
    ]
    inlines = [CommentInline]
    actions = ["publish"]

    @admin.action(description="Publish")
    def publish(self, request, queryset):
        queryset.update(status=Post.Status.PUBLISHED)

    def get_queryset(self, request):
        queryset = super().get_queryset(request)
        if request.user.is_superuser:
            return queryset
        return queryset.filter(status=Post.Status.PUBLISHED)
```

### Step 1: install

HyperAdmin is in pre-release, so pin the version:

```bash
pip install hyper-admin==0.5.0a1
```

### Step 2: rewrite the models

Each Django model becomes a SQLModel class. `__tablename__` points it at the table Django
created (`<app label>_<model name>`), so the data stays where it is.

<!-- run: blog blog-auth -->
```python
# blog/models.py
import enum
from datetime import datetime

from sqlmodel import Field, Relationship, SQLModel


class PostStatus(str, enum.Enum):
    draft = "draft"
    published = "published"


class Author(SQLModel, table=True):
    __tablename__ = "blog_author"

    id: int | None = Field(default=None, primary_key=True)
    name: str = Field(max_length=100)
    email: str = Field(max_length=254, unique=True)

    posts: list["Post"] = Relationship(back_populates="author")

    def __str__(self) -> str:
        return self.name


class Post(SQLModel, table=True):
    __tablename__ = "blog_post"

    id: int | None = Field(default=None, primary_key=True)
    title: str = Field(max_length=200)
    body: str = ""
    status: PostStatus = PostStatus.draft
    published_at: datetime | None = None
    author_id: int = Field(foreign_key="blog_author.id")

    author: Author | None = Relationship(back_populates="posts")
    comments: list["Comment"] = Relationship(back_populates="post")

    def __str__(self) -> str:
        return self.title


class Comment(SQLModel, table=True):
    __tablename__ = "blog_comment"

    id: int | None = Field(default=None, primary_key=True)
    post_id: int = Field(foreign_key="blog_post.id")
    name: str = Field(max_length=100)
    text: str

    post: Post | None = Relationship(back_populates="comments")
```

What changed:

| Django | SQLModel |
|---|---|
| `models.CharField(max_length=100)` | `str = Field(max_length=100)` |
| `models.TextField(blank=True)` | `str = ""` |
| `models.DateTimeField(null=True, blank=True)` | <code>datetime &#124; None = None</code> |
| `models.ForeignKey(Author, ...)` named `author` | The column `author_id: int = Field(foreign_key="blog_author.id")` and the relationship <code>author: Author &#124; None = Relationship(...)</code> |
| `related_name="posts"` | `posts: list["Post"] = Relationship(back_populates="author")` on the other side |
| `TextChoices` | A Python `enum.Enum` |
| The implicit `id` | <code>id: int &#124; None = Field(default=None, primary_key=True)</code> |

Three things to check on your own models:

- **Enum storage.** SQLAlchemy stores the *name* of an enum member, and Django stores the
  *value* of a choice. The example gives each member a name equal to the value Django stored
  (`draft = "draft"`), so existing rows load.
- **Rules that live in Django, not in the database.** `on_delete=models.CASCADE` is carried out
  by Django's ORM. Check what your database's foreign keys do on delete before you rely on it.
- **Migrations.** HyperAdmin never changes your schema unless you turn `create_tables` on. Keep
  one tool in charge of the schema: Django's migrations while both apps run, then
  [Alembic](https://alembic.sqlalchemy.org/) or the tool your FastAPI app uses.

[SQLModel's documentation](https://sqlmodel.tiangolo.com/) covers fields and relationships in
full. Plain SQLAlchemy 2.0 models work too; see
[Add HyperAdmin to an existing app](../guides/existing-app.md#1-register-your-models).

### Step 3: port the `ModelAdmin` classes

<!-- run: blog blog-auth -->
```python
# blog/admin.py
from typing import Any, ClassVar

from fastapi import Request

from hyperadmin.core.actions import action
from hyperadmin.core.fieldsets import FieldsetSpec
from hyperadmin.core.inlines import InlineModelSpec
from hyperadmin.core.model import ModelAdmin
from hyperadmin.core.options import AdminOptions
from hyperadmin.core.registry import site


class AuthorAdmin(ModelAdmin):
    list_display: ClassVar[list[str]] = ["name", "email"]
    search_fields: ClassVar[list[str]] = ["name", "email"]


class PostAdmin(ModelAdmin):
    list_display: ClassVar[list[str]] = ["title", "author", "status", "published_at"]
    list_filter: ClassVar[list[str]] = ["status", "author_id"]
    search_fields: ClassVar[list[str]] = ["title", "body"]
    options: ClassVar[AdminOptions] = AdminOptions(
        fieldsets=[
            FieldsetSpec(name="Content", fields=["title", "body", "author_id"]),
            FieldsetSpec(name="Publishing", fields=["status", "published_at"], collapsed=True),
        ],
        inlines=[
            InlineModelSpec(
                model=Comment, fk_field="post_id", relationship_name="comments", extra=1
            ),
        ],
    )

    @action(label="Publish", bulk=True)
    async def publish(self, request: Request, item_id: int, *, params: Any = None) -> None:
        await self.adapter.update(item_id, {"status": PostStatus.published})

    def get_queryset(self, request: Request | None = None) -> dict[str, Any]:
        user = getattr(request.state, "user", None) if request else None
        if user is None or user.is_superuser:
            return {}
        return {"status": PostStatus.published}


site.register(Author, AuthorAdmin)
site.register(Post, PostAdmin)
```

What changed:

- `list_display`, `search_fields`, `list_filter` and `list_editable` are class attributes, as in
  Django. Every other option goes in an `AdminOptions` object on the class (`options = ...`) or
  passed to `site.register(Post, options=AdminOptions(...))`.
- Filters and form fields name the foreign-key **column** (`author_id`). `list_display` can name
  the relationship (`author`), which shows the related row's `__str__`.
- The inline is a spec, not a class. `fk_field` is the column on `Comment` that points at the
  post, and `relationship_name` is the relationship on `Post` that holds the comments.
- `get_queryset` returns a dict of equality filters instead of a queryset. Without
  authentication there is no `request.state.user`.

#### Actions

A Django action receives a queryset once. A HyperAdmin bulk action is an `async` method that is
called **once for each selected row** with that row's primary key, and the admin then shows a
result for each row. Raise `fastapi.HTTPException` to mark one row as failed.

- `@action(label="Publish", bulk=True)` adds the action to the list page. The method must accept
  a keyword-only `params` argument.
- `@action(label="Publish")` without `bulk=True` adds a button for a single record. The method
  signature is `(self, request, item_id)`.
- `form=SomePydanticModel` (with `bulk=True`) asks the user for parameters first and passes the
  validated model as `params`.

### Step 4: mount the admin

<!-- run: blog -->
```python
# main.py
from fastapi import FastAPI
from sqlalchemy.ext.asyncio import create_async_engine

from hyperadmin import Admin
from hyperadmin.core.settings import HyperAdminSettings

engine = create_async_engine("sqlite+aiosqlite:///blog.db")
app = FastAPI()

admin = Admin(app, engine=engine, settings=HyperAdminSettings(create_tables=False))
admin.mount("/admin")
```

In a project with several files, import `blog.admin` before `admin.mount()`, or let HyperAdmin
import it with `HyperAdminSettings(discover_apps=["blog"])`.

The engine must be async: `sqlite+aiosqlite://` for SQLite, or `postgresql+asyncpg://` for
PostgreSQL. `create_tables=False` (the default) leaves the schema to your migrations. On an empty
database, `create_tables=True` creates the tables on startup.

Start the app with your ASGI server (for example `uvicorn main:app`) and open
`http://localhost:8000/admin/`. At this point the admin has no login. The next section adds one.

## Authentication and permissions

Django admin uses `django.contrib.auth`. HyperAdmin has two modes, and you pick one.

| Django | HyperAdmin built-in auth | HyperAdmin with your own auth |
|---|---|---|
| `django.contrib.auth.models.User` | `hyperadmin.auth.User`, in the `hyperadmin_users` table | Your own user model, returned by your `get_user` dependency |
| `Group`, `Permission` | `hyperadmin.auth.Group`, `hyperadmin.auth.Permission` | Your own rules in `ExternalAuth(has_permission=...)` |
| `is_superuser` | `User.is_superuser`: every permission | A truthy `is_superuser` attribute on your user: every permission |
| `is_staff` | No such field. Every active user can sign in, and sees the models they hold `view_*` on | `ExternalAuth(can_access=...)`; by default `is_superuser` or `is_staff` must be truthy |
| `is_active` | `User.is_active` | Your `get_user` decides |
| Codenames `add_post`, `change_post`, `delete_post`, `view_post` | The same four codenames per model, created in `hyperadmin_permissions` at startup. A custom action checks `action_<name>_<model>` | The same codenames, passed to your `has_permission(user, codename)` |
| `manage.py createsuperuser` | `hyperadmin createsuperuser --database-url ...` | Not needed |
| `manage.py migrate` for the auth tables | `hyperadmin init-db --database-url ...`, or `hyperadmin.auth.metadata()` in Alembic | Not needed: no `hyperadmin_*` user tables |
| The admin login page | Built in, at `/admin/login` | Your app's login page (`login_url`), or a form the admin serves for your token endpoint |
| CSRF middleware | Built in. Enforced whenever auth is configured | Built in |
| `has_*_permission(request, obj)` | `AdminOptions(object_permission_checker=...)` | The same option |

The codename uses the lowercased model class name, as in Django: `Post` gives `view_post`.

### Built-in auth

This replaces the wiring from step 4:

<!-- run: blog-auth -->
```python
# main.py
from fastapi import FastAPI
from sqlalchemy.ext.asyncio import create_async_engine

from hyperadmin import Admin
from hyperadmin.auth.permissions import ModelPermissionChecker, PermissionSyncService
from hyperadmin.auth.session import SessionAuthBackend

engine = create_async_engine("sqlite+aiosqlite:///blog.db")
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

Sessions and CSRF tokens are signed, so the app needs a secret in the `HYPERADMIN_SECRET_KEY`
environment variable; without one it refuses to start. Set it, then create the auth tables and
the first user:

```bash
export HYPERADMIN_SECRET_KEY="$(python -c 'import secrets; print(secrets.token_urlsafe(32))')"
hyperadmin init-db --database-url sqlite+aiosqlite:///blog.db
hyperadmin createsuperuser --database-url sqlite+aiosqlite:///blog.db
```

Users, groups and permissions are then managed in the admin itself, like in Django.

**Existing Django users do not carry over.** The built-in user table is separate from
`auth_user`, and passwords are hashed with Argon2, so Django's password hashes are not accepted.
To keep your current accounts and sign-in, use your own auth instead.

### Your own auth

`Admin(auth=ExternalAuth(get_user=...))` reuses the authentication of your FastAPI app: its user
model, its login page and its permission rules. [Bring Your Own Auth](../guides/external-auth.md)
is the reference, and [Add HyperAdmin to an existing app](../guides/existing-app.md) is the
walkthrough.

In this mode the admin needs no user tables. Saved views and pinned sidebar pages are stored in
two tables of their own; see
[Tables and migrations](../guides/existing-app.md#5-tables-and-migrations).

## No equivalent yet

HyperAdmin does not have these Django admin features today. Check the
[roadmap](../roadmap.md) before you plan around one.

| Django admin feature | Status in HyperAdmin |
|---|---|
| `readonly_fields` | No option. Leaving a field out of `form_fields` removes it from the forms, and the detail page still shows it |
| `save_model`, `delete_model`, `save_formset`, `response_add` and the other per-admin hooks | No per-admin save or delete hook. Rules that must always run belong in the model layer or the database |
| A queryset in `get_queryset` (joins, `Q` objects, annotations) | Equality filters on the model's own columns only |
| Computed columns: a `ModelAdmin` method or a callable in `list_display` | `list_display` reads attributes of the model only. A property on the model can be listed; it cannot be sorted on |
| `ordering`, `list_per_page`, `list_max_show_all` | No option |
| `date_hierarchy` drill-down | `DateRangeFilter` only |
| `StackedInline` versus `TabularInline`, nested inline options | One inline layout |
| `formfield_overrides`, custom `ModelForm`, `prepopulated_fields` | Forms are generated from the model |
| `LogEntry` and the object history page | No change history for your models |
| `save_as`, `save_on_top`, `view_on_site` | No option |
| Importing users and password hashes from `django.contrib.auth` | Not supported; see [Authentication and permissions](#authentication-and-permissions) |
| Sync database drivers | The engine must be async |

## What you gain

Features with no direct Django admin counterpart, each documented elsewhere on this site:

- Per-user saved views in the filter sidebar
- [The command palette, pinned pages and keyboard shortcuts](../guides/navigation.md)
- [Live updates and presence](../guides/realtime.md)
- [Cursor pagination, cached and estimated counts for large tables](../guides/performance.md)
- Tabbed panels on the detail page (`AdminOptions(panels=[...])`)
- Optimistic concurrency control (`AdminOptions(enforce_occ=True)`)
