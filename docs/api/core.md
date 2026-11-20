# Core Components

## How Admin and SiteRegistry relate

`Admin` creates no registry of its own — it reads from the module-level `site` singleton in `hyperadmin.core.registry`. When you call `site.register(MyModel)` anywhere in your codebase, that model is automatically available when `admin.mount()` is called later.

```python
# In myapp/admin.py
from hyperadmin.core.registry import site
site.register(Product)

# In main.py
from hyperadmin import Admin
from hyperadmin.core.settings import HyperAdminSettings
admin = Admin(app, engine=engine, settings=HyperAdminSettings(discover_apps=["myapp"]))
admin.mount("/admin")  # picks up Product automatically
```

To configure a model, pass a `ModelAdmin` subclass as the second argument:

```python
from hyperadmin.core.model import ModelAdmin

class ProductAdmin(ModelAdmin):
    list_display = ["name", "price"]

site.register(Product, ProductAdmin)
```

## Admin

::: hyperadmin.core.app.Admin

## SiteRegistry

::: hyperadmin.core.registry.SiteRegistry

## AdminOptions

::: hyperadmin.core.options.AdminOptions

## NavGroup

::: hyperadmin.core.navigation.NavGroup

## Settings

`HyperAdminSettings` (also importable as `from hyperadmin import HyperAdminSettings`) reads every
field from a `HYPERADMIN_<FIELD>` environment variable. The settings table is in
[Application](application.md#settings).

!!! note "`items_per_page` is not used"
    `HyperAdminSettings.items_per_page` (`HYPERADMIN_ITEMS_PER_PAGE`) is accepted but no code
    reads it in this release. The list view's page size comes from the `page_size` query
    parameter (10 by default, 100 at most).

::: hyperadmin.core.settings.HyperAdminSettings

## Actions, fieldsets and inlines

Decorate a `ModelAdmin` method with `action` to add a custom single-record or bulk action; it
checks the `action_<name>` permission
(see [Authentication & Permissions](auth.md#permission-codenames)). Use `FieldsetSpec` in
`AdminOptions.fieldsets` to group form fields, and `InlineModelSpec` in `AdminOptions.inlines`
to edit related rows on the parent's form.

::: hyperadmin.core.actions.action

::: hyperadmin.core.fieldsets.FieldsetSpec

::: hyperadmin.core.inlines.InlineModelSpec

## Optimistic concurrency

`StaleRecordError` is raised by an adapter when a row changed after the user loaded it, and
`ConcurrencyConfigurationError` at startup when `enforce_occ` is set on a model with no version
field.

::: hyperadmin.core.concurrency.StaleRecordError

::: hyperadmin.core.concurrency.ConcurrencyConfigurationError

## Rate limiting

Pass an object with an async `acquire(key) -> RateLimitDecision` method as
`Admin(rate_limiter=...)` to enforce one request limit across workers; see
[Performance](../guides/performance.md).

::: hyperadmin.core.rate_limit.RateLimiter

::: hyperadmin.core.rate_limit.RateLimitDecision

## Engines, schemas and translations

::: hyperadmin.db.build_engine

::: hyperadmin.core.schema_for

::: hyperadmin.i18n.gettext_lazy

`hyperadmin.__version__` is the installed version of the `hyper-admin` distribution.
