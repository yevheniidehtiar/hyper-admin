---
name: hyperadmin-migrate-from-flask
description: Port a Flask-Admin (Flask-SQLAlchemy) admin to HyperAdmin on FastAPI - map ModelView options (column_list, column_searchable_list, column_filters, form_columns, inline_models, actions, can_* flags, is_accessible) to HyperAdmin, move db.Model classes to a plain SQLAlchemy declarative base on the same tables, replace Flask-Login access checks with ExternalAuth, and verify parity, with an explicit list of Flask-Admin features that have no equivalent yet. Use when the user says "migrate from Flask-Admin", "port my ModelView", "Flask to FastAPI admin", "replace flask_admin", or "move Flask-SQLAlchemy models".
---

# Migrate from Flask-Admin

HyperAdmin runs inside a FastAPI app, reads SQLAlchemy 2.0 (or SQLModel) models through an
async engine, and asks the FastAPI app who the user is. Flask-SQLAlchemy models move to a plain
declarative base with the same `__tablename__` and columns, so the tables do not change.

The docs page "Migrating > From Flask-Admin" (`docs/migration/from-flask-admin.md`) is the
reference; this skill follows it and adds the procedure. For the `flask-migration-agent`,
this skill is the source of truth for mappings and gaps.

## Procedure

1. **Inventory** (read-only): the `Admin(app, ...)` call, every `admin.add_view(...)`, each
   `ModelView` subclass and its options, `BaseView` subclasses with `@expose`, `FileAdmin`,
   custom templates (`list_template`, `edit_template`, ...), `is_accessible` /
   `inaccessible_callback`, Flask-Login setup (user loader, login view), `db.Model` classes,
   the database URL and driver.
2. **Map and report gaps** with the tables below. Agree with the user on each gap.
3. **Install** in the FastAPI project: `pip install hyper-admin==0.5.0a1` plus an async driver
   (`asyncpg`, `aiomysql`; `aiosqlite` is bundled).
4. **Move the models** to `class Base(DeclarativeBase)`; keep table and column names.
5. **Port each `ModelView`** to `ModelAdmin` + `AdminOptions`.
6. **Port access control** to `ExternalAuth` (or built-in auth for new admin accounts).
7. **Mount** with an async engine on the same database (`create_tables=False`).
8. **Verify parity** (checklist at the end).

A Flask app that keeps running can keep its sync engine; the admin only needs its own async
engine on the same database.

## Concept mapping

### Application and registration

| Flask-Admin | HyperAdmin |
|---|---|
| `Admin(app, name="Blog admin")` | `Admin(app, engine=engine, settings=HyperAdminSettings(site_title="Blog admin"))` then `admin.mount("/admin")`; `app` is FastAPI, `engine` an `AsyncEngine` |
| `admin.add_view(PostAdmin(Post, db.session))` | `site.register(Post, PostAdmin)` (`hyperadmin.core.registry.site`); no session passed; register before `mount()` |
| `class PostAdmin(ModelView)` | `class PostAdmin(ModelAdmin)` (`hyperadmin.core.model.ModelAdmin`) |
| `category="Blog"` | `nav_group = "Blog"`; order/icon with `Admin(nav_groups=[NavGroup(...)])` |
| `name="Blog posts"` | `verbose_name_plural = "Blog posts"` |
| `menu_icon_type`, `menu_icon_value` | `icon = "<lucide name>"` (bundled set in `hyperadmin/static/icons`) |
| `BaseView` + `@expose` | A plugin page: `admin.plugins.add_page(...)` + `add_nav_entry(...)` (`hyperadmin-new-plugin` skill) |
| `AdminIndexView` | A plugin home page (`set_home_page`) or the `hyperadmin-reports` dashboard |
| `list_template`, `edit_template`, `create_template`, `details_template` | `{app_label}/{model}/list.html`, `update.html`, `create.html`, `detail.html` in `HyperAdminSettings(template_dirs=[...])` with `site.register(..., app_label=...)` (`hyperadmin-extend-ui` skill) |
| `MenuLink` | `add_nav_entry` in a plugin (named admin routes only) |

### `ModelView` options

| Flask-Admin | HyperAdmin | Difference |
|---|---|---|
| `column_list` | `list_display` | Fields, relationships (`__str__`), dotted paths, properties |
| `column_searchable_list` | `search_fields` | Own columns only; `[]` turns search off |
| `column_filters` | `list_filter` | Field names or `hyperadmin.filters` objects (`DateRangeFilter`, `MultiChoiceFilter`, `MultiFKFilter`, `BooleanFilter`, `IsOwnerFilter`) |
| `column_editable_list` | `list_editable` | |
| `column_sortable_list` | automatic | Every listed model column sorts |
| `column_exclude_list`, `form_excluded_columns` | none | List what you want in `list_display` / `form_fields` |
| `form_columns` | `AdminOptions(form_fields=[...])` | Name the FK column (`author_id`), not the relationship |
| `form_create_rules`, `form_edit_rules` (`rules.FieldSet`) | `AdminOptions(fieldsets=[FieldsetSpec(...)])` | Same fieldsets for create and edit |
| `inline_models` | `AdminOptions(inlines=[InlineModelSpec(model=, fk_field=, relationship_name=, fields=, extra=, max_num=)])` | |
| `form_ajax_refs` | automatic | FK renders as a searchable select; lazy above `preload_threshold` (500) |
| `can_create`, `can_edit`, `can_delete`, `can_view_details` | `AdminOptions(can_create=, can_edit=, can_delete=, can_detail=)` | Plus `can_list` |
| `@action(name, text, confirmation)` | `@action(label=..., bulk=True)` (`hyperadmin.core.actions`) | Called once per selected row with its pk; `async`; keyword-only `params` |
| `get_query()`, `get_count_query()` | `get_queryset(self, request=None)` -> `dict` | Equality filters on own columns |
| `is_accessible()` | `ExternalAuth(can_access=...)` + `ExternalAuth(has_permission=...)` | Three levels, see Auth |
| `inaccessible_callback()` | `ExternalAuth(login_url="/login")` | Anonymous browsers go to `/login?next=...` |
| `page_size` | global `HyperAdminSettings(items_per_page=...)` | No per-model value; users pick rows per page |
| `column_default_sort` | none | Users sort by column |
| `create_modal`, `edit_modal` | none | Pages; FK "+" opens an inline create popup |

### Auth

| Flask-Admin + Flask-Login | HyperAdmin |
|---|---|
| `current_user` | What your `ExternalAuth(get_user=...)` dependency returns; also `request.state.user` |
| `is_accessible()` False for a signed-in user | `can_access(user)` False -> 403 |
| `inaccessible_callback()` redirect | `login_url` |
| Same check in every view | `has_permission(user, codename)` with `view_post`, `add_post`, `change_post`, `delete_post`, `action_publish_post` |
| Per-row rules in `get_query` | `get_queryset` (which rows list) + `AdminOptions(object_permission_checker=...)` (per-row check) |

A Flask session cookie is signed by Flask; FastAPI does not read it. Signing in must exist on
the FastAPI side (your own login route setting a cookie, or a bearer token with `TokenCookie`).
Set `HYPERADMIN_SECRET_KEY`: the admin's CSRF protection is on whenever auth is configured.

## Moving the models

| Flask-SQLAlchemy | SQLAlchemy 2.0 |
|---|---|
| `db = SQLAlchemy(app)`, `class Post(db.Model)` | `class Base(DeclarativeBase): pass`, `class Post(Base)` |
| implicit table name | keep the table Flask-SQLAlchemy used: set `__tablename__` explicitly (it derives snake_case from the class name) |
| `db.Column(db.String(200), nullable=False)` | `Mapped[str] = mapped_column(String(200))` |
| `db.Column(db.DateTime)` | `Mapped[datetime \| None]` |
| `db.relationship(Author, backref="posts")` | `relationship(back_populates="posts")` on both sides |
| `db.Table("post_tags", ...)` | `Table("post_tags", Base.metadata, ...)` and `relationship(secondary=post_tags)` |
| `Post.query`, `db.session` | an `async_sessionmaker` session in your FastAPI code |

The old `Column(...)` style also works on a plain declarative base. Plain SQLAlchemy models are
not picked up by `auto_discover`; register each one. `create_tables` covers SQLModel tables only.
Datetime columns that SQLAlchemy defines as naive stay naive; check timezone handling against
how Flask wrote them.

## Ported example

<!-- check: complete -->
```python
import enum
import os
from datetime import datetime
from typing import Any, ClassVar

from fastapi import FastAPI, Request
from sqlalchemy import ForeignKey, String, Text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship
from starlette.middleware.sessions import SessionMiddleware

from hyperadmin import Admin
from hyperadmin.auth import ExternalAuth
from hyperadmin.core.actions import action
from hyperadmin.core.inlines import InlineModelSpec
from hyperadmin.core.model import ModelAdmin
from hyperadmin.core.options import AdminOptions
from hyperadmin.core.registry import site
from hyperadmin.core.settings import HyperAdminSettings


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


class Comment(Base):
    __tablename__ = "comments"

    id: Mapped[int] = mapped_column(primary_key=True)
    post_id: Mapped[int] = mapped_column(ForeignKey("posts.id"))
    text: Mapped[str] = mapped_column(Text)
    post: Mapped[Post] = relationship(back_populates="comments")


class PostAdmin(ModelAdmin):
    nav_group = "Blog"
    verbose_name_plural = "Blog posts"
    list_display: ClassVar[list[str]] = ["title", "author", "status", "published_at"]
    search_fields: ClassVar[list[str]] = ["title", "body"]
    list_filter: ClassVar[list[str]] = ["status"]
    list_editable: ClassVar[list[str]] = ["status"]
    options: ClassVar[AdminOptions] = AdminOptions(
        form_fields=["title", "body", "author_id", "status", "published_at"],
        inlines=[InlineModelSpec(model=Comment, fk_field="post_id", relationship_name="comments")],
        can_delete=False,
    )

    @action(label="Publish", bulk=True)
    async def publish(self, request: Request, item_id: int, *, params: Any = None) -> None:
        await self.adapter.update(item_id, {"status": PostStatus.published})


engine = create_async_engine("sqlite+aiosqlite:///blog.db")  # same database Flask uses
SessionLocal = async_sessionmaker(engine, expire_on_commit=False)
app = FastAPI()
app.add_middleware(SessionMiddleware, secret_key=os.environ.get("SECRET_KEY", "change-me"))


async def get_current_account(request: Request) -> Account | None:
    account_id = request.session.get("account_id")  # set by your FastAPI login route
    if account_id is None:
        return None
    async with SessionLocal() as session:
        return await session.get(Account, account_id)


admin = Admin(
    app,
    engine=engine,
    settings=HyperAdminSettings(site_title="Blog admin"),
    auth=ExternalAuth(
        get_user=get_current_account,
        can_access=lambda account: account.is_admin,
        has_permission=lambda account, codename: account.is_admin,
        login_url="/login",
        logout_url="/logout",
        display_name=lambda account: account.email,
    ),
)
site.register(Author)
site.register(Post, PostAdmin)
admin.mount("/admin")
```

Saved views and pinned pages need two tables, `hyperadmin_saved_view` and `hyperadmin_nav_pin`;
without them the admin works and logs the missing table. The existing-app guide
(`docs/guides/existing-app.md`, section "Tables and migrations") has the DDL.

## No equivalent yet

Report each of these explicitly when the source admin uses it:

| Flask-Admin feature | Status |
|---|---|
| Backends other than SQLAlchemy (MongoEngine, Peewee, pymongo) | SQLModel and SQLAlchemy only |
| Sync engine or session | The admin's engine must be async (a second, async engine on the same database works) |
| `FileAdmin` file manager | None; model fields can hold uploads (File Uploads guide) |
| `can_export`, `export_types` | No export of model lists (the reports plugin exports CSV/XLSX of reports) |
| `column_formatters`, `column_type_formatters` | No per-column formatter; list a model property instead |
| `column_labels`, `column_descriptions` | No per-column label; labels derive from the field name, help text from `Field(description=...)` on SQLModel fields |
| `column_default_sort`, `page_size` per view, `can_set_page_size` | No per-model option (global `items_per_page`, users pick rows per page) |
| `on_model_change`, `after_model_change`, `on_model_delete`, `after_model_delete` | No per-admin hook that can change or veto; plugin hooks only observe |
| `get_query()` with joins or arbitrary conditions | Equality filters on own columns only |
| WTForms customisation (`form_args`, `form_widget_args`, `form_overrides`, `form_extra_fields`, custom `form`) | Forms are generated from the model; widgets come from the field type |
| `create_modal`, `edit_modal` | Pages |
| Action that returns its own response or flashes | A bulk action returns nothing; the admin renders per-row results |
| `column_details_list`, `column_details_exclude_list` | None; the detail page shows all non-sensitive fields |

## Parity checklist

- [ ] Every `add_view` has a registration, in the expected sidebar group.
- [ ] List columns, search matches for a sample query, filters, editable cells.
- [ ] Forms: same fields and order, inline rows save, every column type round-trips on
      existing rows (enums, dates, decimals, FKs).
- [ ] Each action runs on a selection.
- [ ] Access: anonymous users are redirected to `login_url`, non-admins get 403 or the
      reduced permissions you mapped, admins have full access.
- [ ] `get_query` scoping became `get_queryset` (or an `object_permission_checker`) and hides
      the same rows.
- [ ] Every `BaseView` page has a plugin page, or is accepted as dropped.
- [ ] Every "No equivalent yet" item has an agreed replacement or is accepted as dropped.

Automate with TestClient tests per model and Playwright tests for critical flows (see
`hyperadmin-extend-ui`).
