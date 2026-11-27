---
name: hyperadmin-define-ui
description: Define or adjust HyperAdmin pages declaratively - ModelAdmin attributes, AdminOptions (list columns, search, filters, inline editing, form fields, fieldsets, two-column forms, inlines, relation widgets, detail panels, pagination, permissions), custom actions, sidebar groups, and report/dashboard definitions from hyperadmin-reports. Use when the user says "show these columns", "add a filter", "group the form fields", "edit child rows inline", "add a bulk action", "add a tab to the detail page", "sidebar group", "add a report", "dashboard widget", or asks which admin options HyperAdmin supports.
---

# Define the UI declaratively

HyperAdmin generates the list, detail, create and edit pages of each registered model from its
model plus two declarations: a `ModelAdmin` subclass and an `AdminOptions` object. This skill
lists everything those declarations support today, with the import paths. If a user asks for
something not listed here, say it is not supported declaratively and point to the
`hyperadmin-extend-ui` skill (template overrides) or `hyperadmin-new-plugin` (own pages).

Docs: API Reference > Views (`docs/api/views.md`), Navigation, Lists & Keyboard
(`docs/guides/navigation.md`), Large Tables & Performance (`docs/guides/performance.md`),
the reports plugin README (`plugins/hyperadmin-reports/README.md`).

## Flow

1. Read the model (fields, foreign keys, relationships, enums) and the existing registration.
2. Decide for each requirement whether it is a `ModelAdmin` attribute, an `AdminOptions` field,
   an `@action`, a `@panel`, a filter object, or not supported (say so).
3. Write the declaration; keep all registrations before `admin.mount()`.
4. Verify with a TestClient request (`/admin/<model>`, `/admin/<model>/<pk>`) or the app.

## Where each option goes

```python
from typing import ClassVar

from hyperadmin.core.model import ModelAdmin
from hyperadmin.core.options import AdminOptions
from hyperadmin.core.registry import site


class InvoiceAdmin(ModelAdmin):
    # Only these four may be class attributes:
    list_display: ClassVar[list[str]] = ["number", "customer", "status"]
    search_fields: ClassVar[list[str]] = ["number"]
    list_filter: ClassVar[list] = ["status"]
    list_editable: ClassVar[list[str]] = ["status"]
    # Every other option goes in AdminOptions:
    options: ClassVar[AdminOptions] = AdminOptions(can_delete=False)


site.register(Invoice, InvoiceAdmin)              # or:
site.register(Invoice, options=AdminOptions(...))  # explicit options win over class attributes
site.register(Invoice, InvoiceAdmin, app_label="billing")  # app_label: sidebar group fallback
                                                           # and template override folder
```

## `ModelAdmin` attributes and methods

| Attribute | Type | Effect |
|---|---|---|
| `verbose_name`, `verbose_name_plural` | `str` or `hyperadmin.gettext_lazy(...)` | Page titles and sidebar label. Plural is derived when unset (`JournalEntry` -> "Journal entries") |
| `icon` | `str` | Sidebar icon: a file name (without `.svg`) from `hyperadmin/static/icons` (see list below). Empty shows `layout-grid` |
| `nav_group` | `str` or lazy | Sidebar group label. Falls back to `app_label`, then the unnamed top group |
| `nav_order` | `int` | Position inside the group; ties sort by label |
| `permissions` | `Sequence[tuple[str, str]]` | Extra `(codename, name)` permissions created by built-in auth, for checks your own code makes |
| `list_display`, `search_fields`, `list_filter`, `list_editable` | lists | Same as the `AdminOptions` fields below |
| `options` | `AdminOptions` | Everything else |
| `get_queryset(self, request=None) -> dict` | method | Equality filters `{"column": value}` ANDed into every list, detail and palette query. Use for row scoping (`{"owner_id": request.state.user.id}`) |
| `@action(...)` methods | decorator | Custom actions, see below |
| `@panel(...)` methods | decorator | Detail-page tabs, see below |
| `self.adapter` | inside actions | Reads and writes rows of the model: `await self.adapter.get(pk)`, `await self.adapter.update(pk, {...})` |

Bundled icon names: arrow-down arrow-up bar-chart-3 bell bookmark briefcase building-2 calendar
check chevron-down chevron-left chevron-right circle-check circle-help circle-x clock columns-3
command copy credit-card database download ellipsis external-link eye file-text filter folder
globe history home image info key-round layers layout-grid list-checks lock log-out mail
map-pin menu moon package panel-left-close panel-left-open pencil pin-off pin plus receipt
refresh-cw rotate-ccw search settings shield-check shopping-cart sliders-horizontal sparkles
store sun tag trash-2 triangle-alert truck upload user users wallet x.

## `AdminOptions` fields (`hyperadmin.core.options.AdminOptions`)

**Pages and operations**

| Field | Default | Effect |
|---|---|---|
| `can_create`, `can_edit`, `can_delete`, `can_list`, `can_detail` | `True` | Whether that page/endpoint exists at all |
| `warn_unsaved_changes` | `True` | Ask before leaving a form with unsaved edits |
| `enforce_occ` | `False` | Refuse an edit made against a stale copy (HTTP 409). Needs a `version: int` column, `__version_field__`, or `updated_at` with `HYPERADMIN_CONCURRENCY_USE_UPDATED_AT` |
| `object_permission_checker` | `None` | Per-row check: an object with `async has_object_permission(user, obj, action) -> bool` (`action` is `view`/`add`/`change`/`delete` or `action_<name>`). See `hyperadmin.core.auth.ObjectPermissionChecker` |
| `realtime_notifications` | `None` | Per-model override of live CRUD notifications (needs `Admin(realtime=...)`) |

**List page**

| Field | Default | Effect |
|---|---|---|
| `list_display` | inferred | Columns: field names, relationship names (shows the related row's `__str__`), dotted paths (`"customer.name"`), model properties (not sortable). `[]` shows no columns |
| `search_fields` | inferred | Columns the search box matches; `[]` turns search off |
| `list_filter` | inferred | Field names (exact-match select) and/or filter objects (below); `[]` turns filters off |
| `list_editable` | `[]` | Columns edited in place in the list (never the primary key). Inline cell edits do not fire the plugin CRUD hooks |
| `saved_views_enabled` | `True` | Per-user saved views (needs the `hyperadmin_saved_view` table) |
| `palette_search` | `False` | The Cmd/Ctrl+K palette also finds this model's records (via `search_fields`) |
| `pagination_mode` | `"offset"` | `"cursor"` for very large tables (prev/next only, no total) |
| `count_cache_ttl` | `0` | Seconds to cache the list total |
| `count_estimate_threshold` | `None` | Show the planner estimate as total above this many rows |
| `list_select_related` | `None` | Extra relations to load for the list |
| `auto_select_related` | `True` | Load relations named in `list_display` |
| `filter_cache_ttl` | `60` | Seconds to cache the rows offered by foreign-key filters |

Page size is global: `HyperAdminSettings(items_per_page=10)` (max 100), and users pick rows per
page in the UI. There is no per-model page size or default ordering; users sort by clicking a
column heading.

**Forms**

| Field | Default | Effect |
|---|---|---|
| `form_fields` | `[]` (all editable fields) | Which fields the create/edit forms show, in order. Name the FK **column** (`customer_id`), not the relationship |
| `form_layout` | `FormLayout.SINGLE` | `FormLayout.TWO_COLUMN` for a two-column grid (`hyperadmin.core.layouts.FormLayout`) |
| `fieldsets` | `[]` | `FieldsetSpec(name=, fields=[], collapsed=False, description=None)` from `hyperadmin.core.fieldsets`. Fields not in any fieldset render in an ungrouped section |
| `inlines` | `[]` | `InlineModelSpec(model=, fk_field=, fields=[], max_num=0, extra=1, title="", relationship_name="")` from `hyperadmin.core.inlines`. One layout (no tabular/stacked choice). Inline rows do not fire the plugin CRUD hooks |
| `dependent_fields` | `{}` | `{"city": "country_id"}`: the child select reloads when the parent changes |
| `relation_filters` | `None` | `{"variant_id": RelationDependency(depends_on="supplier_id", placeholder=None)}` (`hyperadmin.core.options.RelationDependency`): narrows an autocomplete by another field |
| `relation_display` | `None` | Option labels per FK: a format string `{"supplier_id": "{name} - {city}"}` or a callable |
| `use_autocomplete_widget` | `True` | `False` falls back to a plain `<select>` for FK/M2M |
| `preload_threshold` | `500` | Above this many related rows an FK widget loads options as you type; `None` always preloads |
| `sensitive_fields` | `{}` | Override sensitive-field detection: `{"token_count": False, "ssn": True}`. Sensitive fields are hidden from detail, list, search, filters and sorting, and write-only on forms. Names matching `password`, `secret`, `token`, `hash` are sensitive by default; with SQLModel mark one with `Field(schema_extra={"json_schema_extra": {"hyperadmin_sensitive": True}})` |

Widgets are chosen from the field type (bool -> checkbox, int/float -> number, datetime ->
datetime-local, Enum -> select, FK column -> autocomplete, `fastapi-storages` `FileType`/`ImageType`
-> upload; long-text names `description`/`text`/`body`/`content` -> textarea). A SQLModel
many-to-many `Relationship(link_model=...)` is not a form field (register the link model
instead), and a JSON `dict` column does not accept JSON text in the generated form. There is no
per-field widget, label, help-text or read-only option in `AdminOptions`; a field's
`Field(description=...)` is shown as help text. To keep a field off the forms, leave it out of
`form_fields` (the detail page still shows it).

**Detail page**

| Field | Default | Effect |
|---|---|---|
| `panels` | `None` | Lazily loaded tabs: `PanelDef(slug=, label=, handler=, icon=None, permission=None, enabled=None)` from `hyperadmin.core.panels`. The handler is `async (request, obj) -> Response` |
| `detail_select_related` | `None` (all) | Relations the detail page loads; `[]` loads none |

## Filters (`hyperadmin.filters`)

All take keyword arguments only.

| Class | Arguments | Notes |
|---|---|---|
| `DateRangeFilter` | `field`, `label=None`, `presets=("today", "this_week", "this_month", "last_month", "this_quarter")` | From/to dates plus presets |
| `CurrentPeriodDefault` | `field`, `label=None`, `period="month"` | A date filter that starts on the current period |
| `MultiChoiceFilter` | `field`, `label=None`, `choices=None` | `choices` is an Enum class or `[(value, label), ...]` |
| `MultiFKFilter` | `field`, `label=None`, `searchable=True` | Several related rows; name the FK column |
| `BooleanFilter` | `field`, `label=None` | Yes / no / any |
| `IsOwnerFilter` | `owner_fields`, `label="Mine only"`, `help_text=None` | Rows owned by the signed-in user |

Custom filter: subclass `FilterDef` as a frozen keyword-only dataclass, set `template` (a Jinja
partial in your `template_dirs`), implement `parse(qs) -> dict` and
`compile(parsed, binding=None) -> list[FilterCondition]`
(`hyperadmin.core.filtering.FilterCondition(field, op, value)`, ops `exact`, `gte`, `lte`,
`in`, `isnull`). A working example is `OverdueFilter` in `examples/erp/filters.py` with its
template `examples/erp/templates/filters/overdue.html`.

## Actions (`hyperadmin.core.actions.action`)

```python
from typing import Any

from fastapi import HTTPException, Request
from pydantic import BaseModel

from hyperadmin.core.actions import action


class DiscountForm(BaseModel):
    percent: int = 10


class InvoiceAdmin(ModelAdmin):
    @action(label="Mark paid", bulk=True)  # list page, runs once per selected row
    async def mark_paid(self, request: Request, item_id: int, *, params: Any = None) -> None:
        await self.adapter.update(item_id, {"status": Status.paid})

    @action(label="Discount", bulk=True, form=DiscountForm)  # asks for params first
    async def discount(self, request: Request, item_id: int, *, params: DiscountForm) -> None:
        if params.percent > 50:
            raise HTTPException(status_code=400, detail="At most 50%")  # marks this row failed

    @action(label="Resend")  # one record: a button on its page
    async def resend(self, request: Request, item_id: int) -> None: ...
```

- `bulk=True` handlers must take a keyword-only `params`; `form=` requires `bulk=True`
  (`TypeError` otherwise). `requires_selection=False` allows running with no rows selected.
- `item_id` is the typed primary key (int, UUID or str).
- Permission codename: `action_<method name>_<model>`.
- An action returns nothing; the admin renders a per-row result. It cannot return its own
  response.

## Detail panels (`hyperadmin.core.panels.panel`)

```python
from fastapi import Request
from fastapi.responses import HTMLResponse

from hyperadmin.core.panels import panel


class InvoiceAdmin(ModelAdmin):
    @panel(label="Summary", icon="file-text")  # slug defaults to the method name
    async def summary(self, request: Request, obj: Invoice) -> HTMLResponse:
        return HTMLResponse(f"<p>Invoice {obj.number}</p>")
```

Served at `/admin/<model>/<pk>/panels/<slug>`. Arguments: `label`, `slug=None`, `icon=None`,
`permission=None` (default codename `view_<model>_panel_<slug>`), `enabled=None` (an
`(obj) -> bool` predicate that hides the tab). `hyperadmin.pdf_stream_panel(slug=, label=,
path_resolver=, enabled=None, icon=None, permission=None)` builds a panel that streams a PDF
file inline; put it in `AdminOptions(panels=[...])`.

## Sidebar groups (`hyperadmin.NavGroup`)

```python
from hyperadmin import Admin, NavGroup

admin = Admin(
    app,
    engine=engine,
    nav_groups=[
        NavGroup("Sales", icon="shopping-cart", order=0),
        NavGroup("Accounting", icon="receipt", order=1, collapsed=True),
    ],
)
```

`NavGroup(label, icon=None, order=0, collapsed=False)` sets order, icon and initial state of a
group whose label matches a `ModelAdmin.nav_group` (or a plugin nav entry's `section`).
Undeclared groups appear after declared ones, by label. Users only see models they may view.

## Reports and dashboards (`hyperadmin-reports` plugin)

The first-party `hyperadmin-reports` package (source in `plugins/hyperadmin-reports/` of the
HyperAdmin repository) adds declarative pivot reports and a home-page dashboard. It is
discovered through its entry point once installed. Register reports and widgets **before**
`Admin(...)` is built.

```python
from hyperadmin.filters import DateRangeFilter
from hyperadmin_reports import (
    ChartWidget,
    Count,
    Group,
    QuickAction,
    QuickActionsWidget,
    ReportView,
    StatWidget,
    Sum,
    TimeBucket,
    register_report,
    register_widget,
)


class OrderRevenueReport(ReportView):
    slug = "orders-revenue"
    model = Order
    rows = [Group("sku")]
    cols = [TimeBucket("created_at", period="month")]  # or period="auto"
    values = [Sum("amount"), Count("id")]
    filters = [DateRangeFilter(field="created_at"), "status"]


register_report(OrderRevenueReport)
register_widget(StatWidget(OrderRevenueReport))
register_widget(ChartWidget(OrderRevenueReport))
register_widget(QuickActionsWidget([QuickAction("All reports", "reports-index")]))
admin = Admin(app, engine=engine)
```

- Aggregates: `Sum`, `Count`, `Min`, `Max` (with totals), `StringAggComma`, `Many2One`.
- Pages: `/admin/reports/`, `/admin/reports/<slug>/` (grid, chart, CSV and XLSX export).
  Permission `view_report_<slug with - as _>` or `ReportView.permission`.
- With at least one widget the dashboard replaces the admin home page (`/admin/`); settings
  via `Admin(plugin_settings={"reports": {"dashboard_home": False}})`. Saved per-user layouts
  need the `hyperadmin_reports_dashboard_layout` table (`await create_layout_table(engine)`).
- A report reads its table directly: `ModelAdmin.get_queryset` scoping does not apply to it.
- Custom cards: subclass `DashboardWidget` with `key`, `title`, `permission()` and
  `async render(request, admin) -> WidgetBody(template, context)`.

## Not supported declaratively

Say so rather than inventing an option: read-only form fields, per-column labels or
formatters, per-model default ordering or page size, computed `ModelAdmin` methods as columns
(use a model property), per-admin save/delete hooks (use model validation, or observe with
plugin hooks), export of model lists (reports export CSV/XLSX), queryset joins in
`get_queryset` (equality filters only), custom form classes.
