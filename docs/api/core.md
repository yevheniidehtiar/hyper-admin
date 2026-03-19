# Core Components

## How Admin and SiteRegistry relate

`Admin` creates no registry of its own — it reads from the module-level `site` singleton in `hyperadmin.core.registry`. When you call `site.register(MyModel)` anywhere in your codebase, that model is automatically available when `admin.mount()` is called later.

```python
# In myapp/admin.py
from hyperadmin.core.registry import site
site.register(Product)

# In main.py
from hyperadmin import Admin
admin = Admin(app, engine=engine, discover_apps=["myapp"])
admin.mount("/admin")  # picks up Product automatically
```

Alternatively, use `ModelView` subclassing — it calls `site.register()` for you via `__init_subclass__`:

```python
from hyperadmin.views.dynamic import ModelView

class ProductAdmin(ModelView, model=Product):
    pass  # registered automatically at import time
```

## Admin

::: hyperadmin.core.app.Admin

## SiteRegistry

::: hyperadmin.core.registry.SiteRegistry

## AdminOptions

::: hyperadmin.core.options.AdminOptions