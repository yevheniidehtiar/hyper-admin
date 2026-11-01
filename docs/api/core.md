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