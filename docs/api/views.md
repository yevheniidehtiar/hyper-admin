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
`list_editable` as class attributes. Every other option goes in `AdminOptions`, and explicit
`options=` always wins.

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

## DynamicModelView

The `DynamicModelView` handles all CRUD views for a registered model: list, detail, create, and update. Routes are generated automatically by `HyperAdminRouter`.

::: hyperadmin.views.dynamic.DynamicModelView

## PydanticForm

`PydanticForm` binds a Pydantic/SQLModel class to a set of widgets, validates submitted data, and collects field-level errors for re-rendering.

::: hyperadmin.views.forms.PydanticForm

## HtmxWidget

The base widget class. Pairs a Jinja2 template with optional HTMX attributes and static assets.

::: hyperadmin.views.forms.HtmxWidget