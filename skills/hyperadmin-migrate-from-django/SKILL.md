---
name: hyperadmin-migrate-from-django
description: Port a Django admin to HyperAdmin on FastAPI - map ModelAdmin options (list_display, search_fields, list_filter, fieldsets, inlines, actions, permissions, get_queryset) to HyperAdmin, convert Django models to SQLModel on the existing tables, mount the admin, choose auth, and verify parity, with an explicit list of Django admin features that have no equivalent yet. Use when the user says "migrate from Django admin", "port my admin.py", "replace django.contrib.admin", "convert Django models to SQLModel", or "Django to FastAPI admin".
---

# Migrate from Django admin

HyperAdmin runs inside a FastAPI app and reads SQLModel or SQLAlchemy models through an async
engine. The biggest change is the ORM, not the admin: Django models become SQLModel classes
pointing at the tables Django created, so the data stays where it is.

The docs page "Migrating > From Django Admin" (`docs/migration/from-django-admin.md`) is the
reference; this skill follows it and adds the procedure. For the `django-migration-agent`,
this skill is the source of truth for mappings and gaps.

## Procedure

1. **Inventory** (read-only). For each Django app: models (`models.py` or `models/`), admin
   classes (`admin.py`: `@admin.register`, `admin.site.register`, `ModelAdmin`,
   `TabularInline`, `StackedInline`, `SimpleListFilter`, `@admin.action`), custom admin
   templates (`templates/admin/`), `get_urls()`, auth customisations (`AUTH_USER_MODEL`,
   permissions, groups), settings that matter (`DATABASES`, `USE_TZ`, `TIME_ZONE`).
2. **Map and report gaps** with the tables below. Every option either maps, maps with a
   difference, or is in "No equivalent yet". Decide with the user what to do about each gap
   before generating code.
3. **Install** in the FastAPI project: `pip install hyper-admin==1.0.0` plus the async driver
   (`asyncpg` for PostgreSQL, `aiosqlite` is bundled, `aiomysql` for MySQL).
4. **Convert the models** to SQLModel, one Django app at a time, with `__tablename__` set to the
   Django table (`<app_label>_<model_name>` unless `Meta.db_table` is set).
5. **Port the admin classes** to `ModelAdmin` + `AdminOptions`.
6. **Mount** with an async engine on the same database; `create_tables=False`.
7. **Auth**: built-in auth (new accounts) or `ExternalAuth` (reuse the FastAPI app's users).
8. **Verify parity** (checklist at the end), app by app.

Keep one tool in charge of the schema: Django migrations while both apps run, then Alembic.
HyperAdmin never changes the schema unless `create_tables=True`.

## Concept mapping

### Site and registration

| Django admin | HyperAdmin |
|---|---|
| `path("admin/", admin.site.urls)` | `admin = Admin(app, engine=engine)` then `admin.mount("/admin")` |
| `admin.site.register(Post, PostAdmin)`, `@admin.register(Post)` | `site.register(Post, PostAdmin)` (`hyperadmin.core.registry.site`); no decorator form; register before `mount()` |
| `class PostAdmin(admin.ModelAdmin)` | `class PostAdmin(ModelAdmin)` (`hyperadmin.core.model.ModelAdmin`) |
| `admin.py` autodiscovery | `HyperAdminSettings(discover_apps=["blog"])` imports `blog/admin.py` |
| `AdminSite.site_title` / `site_header` | `HyperAdminSettings(site_title=...)` (navbar and login page). `site_header` exists but the built-in templates do not show it |
| `Meta.verbose_name(_plural)` | `verbose_name`, `verbose_name_plural` on the `ModelAdmin` |
| App grouping on the index | `nav_group`, `nav_order`, `icon` on the `ModelAdmin`; `Admin(nav_groups=[NavGroup(...)])` |
| `AdminSite.index_template` / custom index | A plugin home page (`admin.plugins.set_home_page`) or the reports dashboard |

### List page

| Django | HyperAdmin | Difference |
|---|---|---|
| `list_display` | `list_display` | Fields, relationships (`__str__`), dotted paths `"author.name"`, model properties. Not `ModelAdmin` methods or callables |
| `list_display_links` | none | The title cell links to the record |
| `search_fields` | `search_fields` | Column names; no `^`, `=`, `@` prefixes, no `author__name` lookups |
| `list_filter` (field) | `list_filter` | Name the FK **column** (`author_id`) |
| `list_filter` (`SimpleListFilter`) | `FilterDef` subclass (`hyperadmin.filters`) | `parse` + `compile` instead of `lookups` + `queryset` |
| `RelatedFieldListFilter`, `ChoicesFieldListFilter`, `BooleanFieldListFilter` | `MultiFKFilter`, `MultiChoiceFilter`, `BooleanFilter` | |
| `date_hierarchy` | `DateRangeFilter(field=...)` | Range + presets, no drill-down |
| `list_editable` | `list_editable` | |
| `list_select_related` | `AdminOptions(list_select_related=[...])` | Relations in `list_display` load automatically |
| `actions` + `@admin.action` | `@action(label=..., bulk=True)` | Called once per selected row with its pk; `async`; must accept keyword-only `params` |
| `actions` with an intermediate page | `@action(..., bulk=True, form=PydanticModel)` | The form is a Pydantic model |
| `ordering`, `list_per_page`, `list_max_show_all` | none per model | Users sort by column; page size is global `HyperAdminSettings(items_per_page=...)` plus a rows-per-page picker |
| `show_full_result_count` | `AdminOptions(count_estimate_threshold=...)`, `count_cache_ttl` | |

### Forms and detail page

| Django | HyperAdmin | Difference |
|---|---|---|
| `fields` | `AdminOptions(form_fields=[...])` | FK column names (`author_id`) |
| `exclude` | `form_fields` | List what you want; no exclude list |
| `fieldsets` | `AdminOptions(fieldsets=[FieldsetSpec(name=, fields=, collapsed=, description=)])` | `"classes": ["collapse"]` -> `collapsed=True` |
| `TabularInline` / `StackedInline` | `AdminOptions(inlines=[InlineModelSpec(model=, fk_field=, relationship_name=, fields=, extra=, max_num=)])` | One layout |
| `autocomplete_fields`, `raw_id_fields` | automatic | FK renders as a searchable select; lazy above `preload_threshold` (500) rows |
| `filter_horizontal` / `filter_vertical` | none for SQLModel | A SQLModel `Relationship(link_model=...)` is not a form field. Register the link model as its own admin (two FK selects per row) |
| `radio_fields` | none | Enums render as a select |
| `FileField`, `ImageField` | `fastapi-storages` `FileType` / `ImageType` columns | See File Uploads guide |
| Two-column admin form | `AdminOptions(form_layout=FormLayout.TWO_COLUMN)` | |
| Dependent selects (third-party) | `AdminOptions(dependent_fields=...)`, `relation_filters=...` | |
| Change-view tabs (third-party) | `@panel(label=...)` methods, `AdminOptions(panels=[...])` | |

### Data, permissions, extension

| Django | HyperAdmin | Difference |
|---|---|---|
| `get_queryset(request)` -> QuerySet | `get_queryset(self, request=None)` -> `dict` | Equality filters `{"column": value}` only |
| `has_add/change/delete/view_permission` | `AdminOptions(can_create=, can_edit=, can_delete=, can_list=, can_detail=)`, permission codenames, `object_permission_checker` | |
| `has_*_permission(request, obj)` | `AdminOptions(object_permission_checker=...)` | `async has_object_permission(user, obj, action)` |
| Codenames `add_post`, `change_post`, `delete_post`, `view_post` | Same four, plus `action_<name>_post` per action | Lowercased class name |
| `Meta.permissions` | `ModelAdmin.permissions = [("refund_order", "Can refund orders")]` | |
| `get_urls()` | A plugin page (`admin.plugins.add_page`) | See `hyperadmin-new-plugin` |
| `templates/admin/<app>/<model>/change_list.html` | `{app_label}/{model}/list.html` in `HyperAdminSettings(template_dirs=[...])` | Needs `site.register(..., app_label=...)`; see `hyperadmin-extend-ui` |
| `save_model`, `delete_model` | none per admin | Plugin hooks observe (`on_after_create`, ...) but cannot change or veto; rules belong in the model or the database |
| Signals (`post_save`) on admin writes | Plugin hooks `on_after_create/update/delete`, or adapter-call hooks for every write | Observers only |

### Auth

| Django | Built-in auth | `ExternalAuth` |
|---|---|---|
| `User` | `hyperadmin.auth.User` (`hyperadmin_users`) | Your user, returned by `get_user` |
| `Group`, `Permission` | `hyperadmin.auth.Group`, `Permission` | Your rules in `has_permission(user, codename)` |
| `is_superuser` | `User.is_superuser` | Truthy `is_superuser` on your user |
| `is_staff` | none: every active user can sign in and sees what they may view | `can_access=`; default needs `is_superuser` or `is_staff` |
| `createsuperuser` | `hyperadmin createsuperuser --database-url ...` | not needed |
| `migrate` for auth tables | `hyperadmin init-db --database-url ...` or `hyperadmin.auth.metadata()` in Alembic | not needed |

Django password hashes are not accepted by built-in auth (Argon2, separate table). To keep
existing accounts, authenticate in the FastAPI app and use `ExternalAuth`.

## Converting models

| Django field | SQLModel |
|---|---|
| implicit `id` (`AutoField`/`BigAutoField`) | `id: int \| None = Field(default=None, primary_key=True)` |
| `CharField(max_length=n)`, `SlugField`, `EmailField`, `URLField` | `str = Field(max_length=n)` |
| `TextField(blank=True)` | `str = ""` |
| `null=True` | `X \| None = None` |
| `IntegerField`, `BigIntegerField`, `PositiveIntegerField` | `int` |
| `BooleanField(default=False)` | `bool = False` |
| `DecimalField(max_digits, decimal_places)` | `Decimal = Field(max_digits=..., decimal_places=...)` |
| `FloatField` | `float` |
| `DateField`, `DateTimeField`, `TimeField` | `date`, `datetime`, `time` |
| `UUIDField` | `uuid.UUID` |
| `JSONField` | `dict = Field(default_factory=dict, sa_type=JSON)` (`from sqlalchemy import JSON`). JSON columns are left out of inferred list columns, and the generated form does not accept JSON text for a `dict` field: keep them out of `form_fields` |
| `TextChoices` / `IntegerChoices` | an `enum.Enum`; member **names** equal the stored values (see below) |
| `ForeignKey(Author, related_name="posts")` | `author_id: int = Field(foreign_key="blog_author.id")` + `author: Author \| None = Relationship(back_populates="posts")`, and `posts: list["Post"] = Relationship(back_populates="author")` on `Author` |
| `OneToOneField` | as `ForeignKey`, plus `unique=True` on the column |
| `ManyToManyField` | a link model on the Django join table (`<app>_<model>_<field>`, columns `id`, `<model>_id`, `<other>_id`) and `Relationship(link_model=...)` on both sides. Edit the pairs through an admin of the link model |
| `FileField`, `ImageField` | `fastapi-storages` `FileType` / `ImageType` column (stores the path, like Django) |
| `Meta.db_table` | `__tablename__` |
| `Meta.ordering`, `Meta.verbose_name` | not on the model: `verbose_name` goes on the `ModelAdmin`; no default ordering |
| `__str__` | keep it: list cells and relation labels use it |

Checks on each model:

- **Enums.** SQLAlchemy stores the member **name**, Django stores the choice **value**. Name
  members after the stored values (`draft = "draft"`) so existing rows load.
- **Datetimes.** With `USE_TZ=True` Django stores UTC; recent SQLModel versions refuse naive
  datetimes on write, so defaults must be aware (`datetime.now(timezone.utc)`).
- **Deletion rules.** `on_delete=CASCADE` runs in Django's ORM, not always in the database.
  Check the actual foreign key constraints before relying on deletes.
- **Validators, `clean()`, `save()` overrides.** Not carried over. Reimplement as Pydantic
  validation where it matters; it only runs where the admin validates input.

Generating a first draft from the database is an option: `sqlacodegen --generator sqlmodels
<url>` (a separate tool) reads the live schema. Review its output against the Django models.

## Ported example

<!-- check: complete -->
```python
import enum
from datetime import datetime
from typing import Any, ClassVar

from fastapi import FastAPI, Request
from sqlalchemy.ext.asyncio import create_async_engine
from sqlmodel import Field, Relationship, SQLModel

from hyperadmin import Admin
from hyperadmin.core.actions import action
from hyperadmin.core.fieldsets import FieldsetSpec
from hyperadmin.core.inlines import InlineModelSpec
from hyperadmin.core.model import ModelAdmin
from hyperadmin.core.options import AdminOptions
from hyperadmin.core.registry import site
from hyperadmin.core.settings import HyperAdminSettings


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


class AuthorAdmin(ModelAdmin):
    nav_group = "Blog"
    list_display: ClassVar[list[str]] = ["name", "email"]
    search_fields: ClassVar[list[str]] = ["name", "email"]


class PostAdmin(ModelAdmin):
    nav_group = "Blog"
    list_display: ClassVar[list[str]] = ["title", "author", "status", "published_at"]
    list_filter: ClassVar[list[str]] = ["status", "author_id"]
    search_fields: ClassVar[list[str]] = ["title", "body"]
    options: ClassVar[AdminOptions] = AdminOptions(
        fieldsets=[
            FieldsetSpec(name="Content", fields=["title", "body", "author_id"]),
            FieldsetSpec(name="Publishing", fields=["status", "published_at"], collapsed=True),
        ],
        inlines=[
            InlineModelSpec(model=Comment, fk_field="post_id", relationship_name="comments"),
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


engine = create_async_engine("sqlite+aiosqlite:///blog.db")  # same database Django uses
app = FastAPI()
admin = Admin(app, engine=engine, settings=HyperAdminSettings(create_tables=False))
site.register(Author, AuthorAdmin)
site.register(Post, PostAdmin)
admin.mount("/admin")
```

## No equivalent yet

Report each of these explicitly when the source admin uses it:

| Django admin feature | Status |
|---|---|
| `readonly_fields` | No option. Leaving a field out of `form_fields` removes it from forms; the detail page still shows it |
| `save_model`, `delete_model`, `save_formset`, `response_add`, other per-admin hooks | No hook that can change or veto a save. Plugin hooks only observe |
| QuerySet in `get_queryset` (joins, `Q`, annotations) | Equality filters on the model's own columns only |
| `ModelAdmin` methods / callables in `list_display`, `@admin.display` | Model attributes, properties and dotted paths only; properties are not sortable |
| `ordering`, `list_per_page` per model, `list_max_show_all`, `sortable_by` | No per-model option |
| `date_hierarchy` drill-down | `DateRangeFilter` only |
| `StackedInline` vs `TabularInline`, nested inlines | One inline layout, one level |
| `formfield_overrides`, custom `form`/`ModelForm`, `prepopulated_fields`, `radio_fields` | Forms are generated from the model; widgets come from the field type |
| `LogEntry`, object history page | No change history |
| `save_as`, `save_on_top`, `view_on_site` | No option |
| `search_fields` lookups across relations (`author__name`) | Own columns only |
| Export of change lists | None for model lists (the reports plugin exports CSV/XLSX of reports) |
| Django auth users and password hashes | Not importable; use `ExternalAuth` to keep them |
| Sync database drivers | The engine must be async |

## Parity checklist

For each model, compare the old and the new admin side by side:

- [ ] The model appears in the expected sidebar group for a user who may view it, and not for
      one who may not.
- [ ] List columns, search (same matches for a sample query), filters, sortable columns.
- [ ] Create and edit forms: same fields and order, fieldsets, inlines; saving round-trips
      every field type (enums, dates, decimals, FKs, M2M) on existing rows.
- [ ] Each action runs on a selection and reports per-row results.
- [ ] `get_queryset` scoping hides the same rows.
- [ ] Permissions: a non-superuser sees and can do exactly what the codenames allow.
- [ ] Existing rows load without errors (enum names, naive datetimes, nullable columns).
- [ ] Every "No equivalent yet" item has an agreed replacement or is accepted as dropped.

Automate the list with TestClient tests per model (status 200, a known row's text on the
list page, a create round-trip), and a Playwright test per critical flow (see
`hyperadmin-extend-ui`).
