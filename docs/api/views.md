# Views

## Configuring a model's admin

Configure a model with `AdminOptions`, a `ModelAdmin` subclass, or both. Pass either one to
`site.register()`:

```python
from typing import ClassVar

from hyperadmin.core.model import ModelAdmin
from hyperadmin.core.options import AdminOptions
from hyperadmin.core.registry import site
from myapp.models import User


class UserAdmin(ModelAdmin):
    verbose_name_plural = "People"
    list_display: ClassVar[list[str]] = ["username", "email", "is_active"]
    search_fields: ClassVar[list[str]] = ["username", "email"]
    list_filter: ClassVar[list[str]] = ["is_active"]


site.register(User, UserAdmin)

# or, with options only
site.register(User, options=AdminOptions(list_display=["username", "email"], can_delete=False))
```

A `ModelAdmin` subclass can declare `list_display`, `search_fields`, `list_filter` and
`list_editable` as class attributes, or a whole `options = AdminOptions(...)`. Every other
option goes in `AdminOptions`, and explicit `options=` always wins.

### `ModelAdmin` attributes

| `ModelAdmin` attribute | What it controls |
|-----------|-------------|
| `verbose_name`, `verbose_name_plural` | Display names; plain strings or `gettext_lazy(...)`. The plural defaults to the English plural of the singular, or of the class name split into words (`JournalEntry` → "Journal entries") |
| `icon` | Sidebar icon: a Lucide name such as `"receipt"`. Empty shows a generic grid icon |
| `nav_group`, `nav_order` | Sidebar group (falls back to the `app_label` passed to `site.register`) and position inside it; see [Navigation](../guides/navigation.md) |
| `permissions` | Extra `(codename, name)` pairs created at startup and shown in the permissions matrix; see [Extra codenames](auth.md#extra-codenames-modeladminpermissions) |
| `get_queryset(request)` | Method returning `{column: value}` equality filters ANDed into every list and detail query (row scoping) |
| `@action` / `@panel` methods | Custom single-record and bulk actions ([Actions](core.md#actions-fieldsets-and-inlines)) and detail-page tabs ([Detail panels](#detail-panels)) |

### `AdminOptions` fields

| `AdminOptions` field | What it controls |
|-----------|-------------|
| `can_create`, `can_edit`, `can_delete`, `can_list`, `can_detail` | Which pages and actions exist (all `True` by default) |
| `list_display` | Columns in the list view. Inferred when unset; JSON columns are left out |
| `search_fields` | Columns the search box matches |
| `list_filter` | Filters in the filter sidebar: field names or `FilterDef`s from `hyperadmin.filters` |
| `list_editable` | Columns editable inline in the list view |
| `saved_views_enabled` | Per-user saved views in the filter sidebar |
| `sensitive_fields` | Opt fields in or out of sensitive-field hiding (`{"secret_name": False}`) |
| `form_fields`, `form_layout`, `fieldsets` | Which fields the forms show, and how they are laid out |
| `inlines` | Related rows edited on the parent's form |
| `dependent_fields` | Selects whose choices depend on another field |
| `relation_filters`, `relation_display`, `use_autocomplete_widget` | How foreign-key choices are filtered, labelled and searched |
| `object_permission_checker` | Object-level permission checks for each row |
| `panels` | Tabbed panels on the detail page (see `hyperadmin.core.panels.panel`) |
| `realtime_notifications` | Opt the model into live CRUD notifications |
| `warn_unsaved_changes` | Ask before leaving a create, edit or popup form with unsaved changes (`True` by default) |
| `enforce_occ` | Optimistic concurrency (default `False`). The edit form carries the row's version, and a save made against an out-of-date copy is refused with HTTP 409 and a conflict dialog instead of overwriting the newer change. Needs a `version: int` column, a `__version_field__` class attribute naming another column, or an `updated_at` column with `HyperAdminSettings.concurrency_use_updated_at`; otherwise startup raises `ConcurrencyConfigurationError` |
| `palette_search` | Let the Cmd/Ctrl+K command palette find this model's records (default `False`). Typed text of 2 characters or more runs the list search over `search_fields`, inside `get_queryset` and only for users with `view_<model>`, and shows at most 5 matches |
| `pagination_mode` | `"offset"` (default: page numbers and a total) or `"cursor"` (previous / next by the sort column and primary key, the same cost on every page, no total). Lists sorted by a column holding NULLs fall back to page numbers |
| `count_cache_ttl` | Seconds to reuse the list total for the same filters and search (default `0`: count on every request). Dropped when the admin creates, updates or deletes a row of the model |
| `count_estimate_threshold` | Row count from which an unfiltered list shows the planner's estimate (`~4200000`) instead of `count(*)` (default `None`: always count). Filtered and searched lists always count exactly |
| `filter_cache_ttl` | Seconds to cache the related rows a foreign-key filter lists (default `60`; `0` queries on every render). Dropped when the admin writes the related model |
| `list_select_related` | Relations the list page loads in addition to the ones its columns name (default: none). Name a relation that a template or `__str__` reads |
| `auto_select_related` | Whether list columns naming a relation (`"category"`, `"category.name"`) load it (default `True`). `False` loads only `list_select_related` |
| `detail_select_related` | Relations the detail page loads (default `None`: all; `[]`: none) |
| `preload_threshold` | Related-table row count (estimated) from which a foreign-key widget becomes a lazy autocomplete instead of embedding every option (default `500`; `None` always preloads) |

The large-table options are explained, with measurements, in
[Large Tables & Performance](../guides/performance.md).

## DynamicModelView

The `DynamicModelView` handles all CRUD views for a registered model: list, detail, create, and update. Routes are generated automatically by `HyperAdminRouter`.

::: hyperadmin.views.dynamic.DynamicModelView

## PydanticForm

`PydanticForm` binds a Pydantic/SQLModel class to a set of widgets, validates submitted data, and collects field-level errors for re-rendering.

::: hyperadmin.views.forms.PydanticForm

## HtmxWidget

The base widget class. Pairs a Jinja2 template with optional HTMX attributes and static assets.

::: hyperadmin.views.forms.HtmxWidget
## Detail panels

Decorate a `ModelAdmin` method with `panel` to add a tab to the detail page, or pass panel
definitions in `AdminOptions.panels`. `pdf_stream_panel` builds a ready-made panel definition
that streams a PDF inline.

!!! warning "`PDFStreamPanel` is deprecated"
    `hyperadmin.PDFStreamPanel` is the same function under a class-style name. It emits a
    `DeprecationWarning` and will be removed in 0.6; use `pdf_stream_panel`.

::: hyperadmin.core.panels.panel

::: hyperadmin.panels.pdf_stream_panel

## Filters

`AdminOptions.list_filter` takes field names or filter definitions from `hyperadmin.filters`,
for example `DateRangeFilter(field="created_at")`. Every filter subclasses `FilterDef`.
[List Filters](../guides/filters.md) shows each built-in filter and how to write your own.

::: hyperadmin.filters.FilterDef

::: hyperadmin.filters.FilterBinding

::: hyperadmin.filters.DateRangeFilter

::: hyperadmin.filters.CurrentPeriodDefault

::: hyperadmin.filters.MultiChoiceFilter

::: hyperadmin.filters.MultiFKFilter

::: hyperadmin.filters.BooleanFilter

::: hyperadmin.filters.IsOwnerFilter

## Admin URLs

`admin_url_for(request, name, **path_params)` resolves a route name in the `hyperadmin:`
namespace for the current request, for example
`admin_url_for(request, "product-detail", item_id=1)`.

::: hyperadmin.views.urls.admin_url_for
