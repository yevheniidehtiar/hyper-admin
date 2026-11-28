# Migrating from Flask-Admin

This guide maps Flask-Admin concepts to HyperAdmin and ports a small blog admin step by step. It
covers what HyperAdmin does today, and it lists what has [no equivalent yet](#no-equivalent-yet)
so you can decide before you start.

HyperAdmin mounts on a **FastAPI** application and reads SQLAlchemy models through an **async**
engine. Moving from Flask-Admin therefore has three parts:

1. The models leave Flask-SQLAlchemy's `db.Model` for a plain SQLAlchemy declarative base. The
   tables and the data do not change.
2. The `ModelView` classes become `ModelAdmin` classes.
3. Access control moves from `is_accessible()` to a FastAPI dependency that returns the current
   user.

The guide covers the SQLAlchemy backend (`flask_admin.contrib.sqla`). Flask-Admin's side of each
comparison follows [the Flask-Admin documentation](https://flask-admin.readthedocs.io/).

## Concept mapping

### Application and registration

| Flask-Admin | HyperAdmin | Notes |
|---|---|---|
| `Admin(app, name="Blog admin")` | `Admin(app, engine=engine, settings=HyperAdminSettings(site_title="Blog admin"))` then `admin.mount("/admin")` | `app` is a FastAPI app, and the engine is an `AsyncEngine` |
| `admin.add_view(PostAdmin(Post, db.session))` | `site.register(Post, PostAdmin)` | `from hyperadmin.core.registry import site`. No session is passed: the admin opens its own from the engine. Register before `admin.mount()` |
| `class PostAdmin(ModelView)` | `class PostAdmin(ModelAdmin)` | `from hyperadmin.core.model import ModelAdmin` |
| `category="Blog"` | `nav_group = "Blog"` on the `ModelAdmin` | Order and icon of a group: `Admin(nav_groups=[NavGroup(...)])`. See [Navigation, Lists & Keyboard](../guides/navigation.md) |
| `name="Blog posts"` | `verbose_name_plural = "Blog posts"` | |
| `BaseView` with `@expose` | A router added with `admin.plugins.add_page(...)` | See [Your own pages in the sidebar](../guides/navigation.md#your-own-pages-in-the-sidebar) |
| Template overrides (`list_template`, `edit_template`, ...) | `HyperAdminSettings(template_dirs=[...])` | See [Override templates](../getting-started.md#override-templates) |

### `ModelView` options

| Flask-Admin `ModelView` | HyperAdmin | Notes |
|---|---|---|
| `column_list` | `list_display` | Inferred when unset |
| `column_searchable_list` | `search_fields` | Inferred when unset; `[]` turns search off |
| `column_filters` | `list_filter` | Field names, or filter objects from `hyperadmin.filters` |
| `column_editable_list` | `list_editable` | Cells are edited in place |
| `form_columns` | `AdminOptions(form_fields=[...])` | Names the foreign-key column (`author_id`), not the relationship |
| `inline_models` | `AdminOptions(inlines=[InlineModelSpec(...)])` | `InlineModelSpec(model=, fk_field=, relationship_name=, fields=, extra=, max_num=)` |
| `form_ajax_refs` | Automatic | A foreign key renders as a searchable select. Above `AdminOptions.preload_threshold` rows (500 by default) it loads options as you type |
| `can_create`, `can_edit`, `can_delete`, `can_view_details` | `AdminOptions(can_create=, can_edit=, can_delete=, can_detail=)` | `can_list` also exists |
| `@action(name, text, confirmation)` | `@action(label="...", bulk=True)` | `from hyperadmin.core.actions import action`. See [Actions](#actions) |
| `get_query()`, `get_count_query()` | `get_queryset(request)` returning a `dict` | Equality filters, `{"column": value}`, added to every list and detail query |
| `is_accessible()` | `ExternalAuth(can_access=...)` and `ExternalAuth(has_permission=...)` | See [Authentication and permissions](#authentication-and-permissions) |
| `inaccessible_callback()` | `ExternalAuth(login_url="/login")` | Anonymous browsers are redirected there with `?next=` |
| `column_exclude_list`, `form_excluded_columns` | No option | List the fields you want in `list_display` and `form_fields` |
| `column_sortable_list` | No option | Every listed column that is a model field can be sorted |
| `column_default_sort` | No option | |
| `page_size` | No per-model option | Global only: `HyperAdminSettings(items_per_page=...)` (`HYPERADMIN_ITEMS_PER_PAGE`, default 10, at most 100). Users pick 10, 25, 50 or 100 rows below the table |
| `column_labels`, `column_formatters`, `column_descriptions` | No option | See [No equivalent yet](#no-equivalent-yet) |
| `on_model_change`, `after_model_change`, `on_model_delete` | No hook | See [No equivalent yet](#no-equivalent-yet) |
| `can_export`, `export_types` | No export | |

`AdminOptions` has more than the table shows: fieldsets, form layouts, detail-page panels. The
[Views reference](../api/views.md) lists every field.

## Port a small admin

The example is a blog with authors, posts and comments, and an `Account` table for the people who
sign in.

### Before: Flask-Admin

```python
# app.py
import enum
import os

from flask import Flask, redirect, request, url_for
from flask_admin import Admin
from flask_admin.actions import action
from flask_admin.contrib.sqla import ModelView
from flask_login import LoginManager, UserMixin, current_user
from flask_sqlalchemy import SQLAlchemy

app = Flask(__name__)
app.config["SECRET_KEY"] = os.environ["SECRET_KEY"]
app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///blog.db"
db = SQLAlchemy(app)
login_manager = LoginManager(app)
login_manager.login_view = "login"


class PostStatus(enum.Enum):
    draft = "draft"
    published = "published"


class Account(db.Model, UserMixin):
    __tablename__ = "accounts"
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(254), unique=True, nullable=False)
    is_admin = db.Column(db.Boolean, default=False, nullable=False)


class Author(db.Model):
    __tablename__ = "authors"
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(254), unique=True, nullable=False)

    def __str__(self):
        return self.name


class Post(db.Model):
    __tablename__ = "posts"
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    body = db.Column(db.Text, default="", nullable=False)
    status = db.Column(db.Enum(PostStatus), default=PostStatus.draft, nullable=False)
    published_at = db.Column(db.DateTime)
    author_id = db.Column(db.Integer, db.ForeignKey("authors.id"), nullable=False)
    author = db.relationship(Author, backref="posts")

    def __str__(self):
        return self.title


class Comment(db.Model):
    __tablename__ = "comments"
    id = db.Column(db.Integer, primary_key=True)
    post_id = db.Column(db.Integer, db.ForeignKey("posts.id"), nullable=False)
    name = db.Column(db.String(100), nullable=False)
    text = db.Column(db.Text, nullable=False)
    post = db.relationship(Post, backref="comments")


@login_manager.user_loader
def load_user(user_id):
    return db.session.get(Account, int(user_id))


class SecureModelView(ModelView):
    def is_accessible(self):
        return current_user.is_authenticated and current_user.is_admin

    def inaccessible_callback(self, name, **kwargs):
        return redirect(url_for("login", next=request.url))


class AuthorAdmin(SecureModelView):
    column_list = ["name", "email"]
    column_searchable_list = ["name", "email"]


class PostAdmin(SecureModelView):
    column_list = ["title", "author", "status", "published_at"]
    column_searchable_list = ["title", "body"]
    column_filters = ["status"]
    column_editable_list = ["status"]
    form_columns = ["title", "body", "author", "status", "published_at"]
    inline_models = [Comment]
    can_delete = False

    @action("publish", "Publish", "Publish the selected posts?")
    def action_publish(self, ids):
        Post.query.filter(Post.id.in_(ids)).update(
            {"status": PostStatus.published}, synchronize_session=False
        )
        db.session.commit()


admin = Admin(app, name="Blog admin")
admin.add_view(AuthorAdmin(Author, db.session, category="Blog"))
admin.add_view(PostAdmin(Post, db.session, name="Blog posts", category="Blog"))
```

The app's own `login` view is left out.

### Step 1: install

Install HyperAdmin:

```bash
pip install hyper-admin==1.0.0
```

The Flask app and the new FastAPI app can run side by side on the same database while you
migrate.

### Step 2: move the models to a plain declarative base

Flask-SQLAlchemy models are SQLAlchemy models bound to the Flask extension. A FastAPI app has no
Flask application context, so the models move to a declarative base of their own. Keep every
`__tablename__` and column as it is, and the tables do not change.

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


class Account(Base):
    __tablename__ = "accounts"

    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(254), unique=True)
    is_admin: Mapped[bool] = mapped_column(default=False)


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
    comments: Mapped[list["Comment"]] = relationship(back_populates="post")

    def __str__(self) -> str:
        return self.title


class Comment(Base):
    __tablename__ = "comments"

    id: Mapped[int] = mapped_column(primary_key=True)
    post_id: Mapped[int] = mapped_column(ForeignKey("posts.id"))
    name: Mapped[str] = mapped_column(String(100))
    text: Mapped[str] = mapped_column(Text)

    post: Mapped[Post] = relationship(back_populates="comments")
```

What changed:

| Flask-SQLAlchemy | SQLAlchemy 2.0 |
|---|---|
| `class Post(db.Model)` | `class Post(Base)`, with `class Base(DeclarativeBase)` |
| `db.Column(db.String(200), nullable=False)` | `Mapped[str] = mapped_column(String(200))` |
| `db.Column(db.DateTime)` (nullable) | <code>Mapped[datetime &#124; None]</code> |
| `db.relationship(Author, backref="posts")` | `relationship(back_populates="posts")` on one side and `relationship(back_populates="author")` on the other |
| `Post.query`, `db.session` | A session from your FastAPI app's `async_sessionmaker` |

The older `Column(...)` style also works on a plain declarative base, so a large model file can
move with fewer edits. [SQLAlchemy's ORM documentation](https://docs.sqlalchemy.org/en/20/orm/)
covers both styles, and SQLModel `table=True` models work too.

### Step 3: port the `ModelView` classes

<!-- run: blog -->
```python
# admin.py
from typing import Any, ClassVar

from fastapi import Request

from hyperadmin.core.actions import action
from hyperadmin.core.inlines import InlineModelSpec
from hyperadmin.core.model import ModelAdmin
from hyperadmin.core.options import AdminOptions
from hyperadmin.core.registry import site


class AuthorAdmin(ModelAdmin):
    nav_group = "Blog"
    list_display: ClassVar[list[str]] = ["name", "email"]
    search_fields: ClassVar[list[str]] = ["name", "email"]


class PostAdmin(ModelAdmin):
    nav_group = "Blog"
    verbose_name_plural = "Blog posts"
    list_display: ClassVar[list[str]] = ["title", "author", "status", "published_at"]
    search_fields: ClassVar[list[str]] = ["title", "body"]
    list_filter: ClassVar[list[str]] = ["status"]
    list_editable: ClassVar[list[str]] = ["status"]
    options: ClassVar[AdminOptions] = AdminOptions(
        form_fields=["title", "body", "author_id", "status", "published_at"],
        inlines=[
            InlineModelSpec(model=Comment, fk_field="post_id", relationship_name="comments"),
        ],
        can_delete=False,
    )

    @action(label="Publish", bulk=True)
    async def publish(self, request: Request, item_id: int, *, params: Any = None) -> None:
        await self.adapter.update(item_id, {"status": PostStatus.published})


site.register(Author, AuthorAdmin)
site.register(Post, PostAdmin)
```

What changed:

- The view class no longer takes the model and a session. The model is passed to `site.register`.
- `list_display`, `search_fields`, `list_filter` and `list_editable` are class attributes. Every
  other option goes in an `AdminOptions` object on the class (`options = ...`) or passed to
  `site.register(Post, options=AdminOptions(...))`.
- `list_display` can name the relationship (`author`), which shows the related row's `__str__`.
  `form_fields` names the foreign-key column (`author_id`).
- The inline is a spec. `fk_field` is the column on `Comment` that points at the post, and
  `relationship_name` is the relationship on `Post` that holds the comments.
- `can_delete=False` removes the delete button and the delete route.

#### Actions

A Flask-Admin action receives the list of selected ids once. A HyperAdmin bulk action is an
`async` method that is called **once for each selected row** with that row's primary key. The
admin then shows a result for each row. Raise `fastapi.HTTPException` to mark one row as failed.

- `@action(label="Publish", bulk=True)` adds the action to the list page. The method must accept
  a keyword-only `params` argument.
- `@action(label="Publish")` without `bulk=True` adds a button for a single record. The method
  signature is `(self, request, item_id)`.
- `form=SomePydanticModel` (with `bulk=True`) asks the user for parameters first and passes the
  validated model as `params`.

`self.adapter` reads and writes rows of the model (`get`, `update`), so the action needs no
session of its own.

### Step 4: port access control and mount the admin

Flask-Admin asks each view `is_accessible()`, and the view reads Flask-Login's `current_user`.
HyperAdmin asks your FastAPI app for the current user once per request, through a dependency you
write, and then applies its own checks.

The example assumes the FastAPI app signs users in with a session cookie: its login view stores
the account id in `request.session["account_id"]`.

<!-- run: blog -->
```python
# main.py
import os

from fastapi import FastAPI, Request
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from starlette.middleware.sessions import SessionMiddleware

from hyperadmin import Admin
from hyperadmin.auth import ExternalAuth
from hyperadmin.core.settings import HyperAdminSettings

engine = create_async_engine("sqlite+aiosqlite:///blog.db")
SessionLocal = async_sessionmaker(engine, expire_on_commit=False)

app = FastAPI()
app.add_middleware(SessionMiddleware, secret_key=os.environ["SECRET_KEY"])


async def get_current_account(request: Request) -> Account | None:
    account_id = request.session.get("account_id")
    if account_id is None:
        return None
    async with SessionLocal() as session:
        return await session.get(Account, account_id)


def can_access(account: Account) -> bool:
    return account.is_admin


def has_permission(account: Account, codename: str) -> bool:
    return account.is_admin


admin = Admin(
    app,
    engine=engine,
    settings=HyperAdminSettings(site_title="Blog admin"),
    auth=ExternalAuth(
        get_user=get_current_account,
        can_access=can_access,
        has_permission=has_permission,
        login_url="/login",
        logout_url="/logout",
        display_name=lambda account: account.email,
    ),
)
admin.mount("/admin")
```

How the pieces map:

| Flask-Admin | HyperAdmin |
|---|---|
| `current_user` from Flask-Login | The object your `get_user` dependency returns. It is also `request.state.user` in `get_queryset` and in actions |
| `is_accessible()` returning `False` for a signed-in user | `can_access(user)` returning `False`: the admin answers 403 |
| `inaccessible_callback()` redirecting to the login view | `login_url`: an anonymous browser is redirected to `/login?next=/admin/...` |
| The same `is_accessible()` on every view | `has_permission(user, codename)`, asked for `view_post`, `add_post`, `change_post`, `delete_post` and `action_publish_post` |

The admin's CSRF protection is on in this mode, so set `HYPERADMIN_SECRET_KEY` in the
environment.

In a project with several files, import `admin.py` before `admin.mount()`, or let HyperAdmin
import it with `HyperAdminSettings(discover_apps=["yourpackage"])`.

Saved views and pinned sidebar pages are stored for each user in two tables,
`hyperadmin_saved_view` and `hyperadmin_nav_pin`. Until they exist the admin works without those
two features and logs the missing table. [Tables and migrations](../guides/existing-app.md#5-tables-and-migrations)
has the DDL.

## Authentication and permissions

A Flask session cookie is signed and encoded by Flask, and FastAPI does not read it out of the
box. Signing in has to exist on the FastAPI side: a login view of your own that sets a cookie, or a token your
frontend already holds. HyperAdmin works with either, and
[Bring Your Own Auth](../guides/external-auth.md) covers cookie sessions, bearer tokens and
single-page apps.

Flask-Admin has one question per view (`is_accessible()`). HyperAdmin has three levels:

| Level | Where | Example |
|---|---|---|
| May this user open the admin at all? | `ExternalAuth(can_access=...)` | Admins only. By default the user needs a truthy `is_superuser` or `is_staff` |
| May this user do this to this model? | `ExternalAuth(has_permission=...)`, with the codename `<action>_<model>` | Editors may `view_post` and `change_post`, but not `delete_post` |
| May this user touch this row? | `AdminOptions(object_permission_checker=...)`, and `ModelAdmin.get_queryset(request)` to limit which rows are listed | Authors see their own posts |

To write a finer rule than the example's, split the codename:

<!-- run: blog -->
```python
def editor_permissions(account: Account, codename: str) -> bool:
    if account.is_admin:
        return True
    action_name, _, model = codename.partition("_")
    return model == "post" and action_name in {"view", "add", "change"}
```

The sidebar lists only the models the user may view. Without `has_permission`, a user with a
truthy `is_superuser` attribute gets every permission and every other user can only view.

HyperAdmin also has built-in auth, with its own user, group and permission tables, a login page
and `hyperadmin createsuperuser`. Use it when the admin should manage its own accounts; the
[Django admin guide](from-django-admin.md#built-in-auth) shows the wiring.

## No equivalent yet

HyperAdmin does not have these Flask-Admin features today. Check the [roadmap](../roadmap.md)
before you plan around one.

| Flask-Admin feature | Status in HyperAdmin |
|---|---|
| Backends other than SQLAlchemy (MongoEngine, Peewee, ...) | SQLModel and SQLAlchemy only |
| A synchronous engine or session | The engine must be async. An app that writes with a sync engine can give the admin an async engine on the same database |
| The file manager (`FileAdmin`) | No file manager. Model fields can hold uploads; see [File Uploads](../guides/file-uploads.md) |
| Export (`can_export`, `export_types`) | No export |
| `column_formatters`, `column_type_formatters` | No per-column formatter. A property on the model can be listed in `list_display` |
| `column_labels`, `column_descriptions` | No per-column label or description. Labels are derived from the field name |
| `column_default_sort` | No option |
| `page_size`, `can_set_page_size` | No per-model option; the global `items_per_page` setting sets the default page size and users can always pick 10, 25, 50 or 100 rows |
| `on_model_change`, `after_model_change`, `on_model_delete`, `after_model_delete` | No per-admin save or delete hook. Plugin [lifecycle hooks](../plugins/hooks.md) observe the create, edit and delete views (not bulk actions or inline edits) but cannot change or veto a save. Rules that must always run belong in the model layer or the database |
| `get_query()` returning a query (joins, arbitrary conditions) | `get_queryset(request)` returns equality filters on the model's own columns only |
| WTForms customisation: `form_args`, `form_widget_args`, `form_overrides`, `form_extra_fields`, a custom `form` | Forms are generated from the model. Widgets are chosen from the field type; see [Widgets](../frontend/widgets.md) |
| Modal create and edit (`create_modal`, `edit_modal`) | Create and edit are pages |
| A custom action that returns its own response or flashes a message | A bulk action returns nothing; the admin renders the per-row results |

## What you gain

Features with no direct Flask-Admin counterpart, each documented elsewhere on this site:

- Permission codenames per model and action, and per-row rules (above)
- Fieldsets and detail-page panels ([Views reference](../api/views.md))
- Filter objects for date ranges and multiple choices, and per-user saved views
- [The command palette, pinned pages and keyboard shortcuts](../guides/navigation.md)
- [Live updates and presence](../guides/realtime.md)
- [Cursor pagination, cached and estimated counts for large tables](../guides/performance.md)
