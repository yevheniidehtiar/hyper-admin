# Getting Started

## Prerequisites

- Python 3.11+
- A FastAPI application
- SQLModel or SQLAlchemy 2.0+ models (see [Compatibility & Performance](compatibility.md))

## Installation

HyperAdmin is in pre-release, so pin the version (installers skip pre-releases otherwise).
The distribution is `hyper-admin`; the import name is `hyperadmin`.

=== "pip"
    ```bash
    pip install hyper-admin==0.5.0a1
    ```

=== "uv"
    ```bash
    uv add hyper-admin==0.5.0a1
    ```

=== "poetry"
    ```bash
    poetry add hyper-admin==0.5.0a1
    ```

## Quickstart

The minimal setup needs three things: an engine, model registration, and a mount path.

```python
from fastapi import FastAPI
from sqlalchemy.ext.asyncio import create_async_engine
from sqlmodel import SQLModel, Field
from hyperadmin import Admin
from hyperadmin.core.registry import site
from hyperadmin.core.settings import HyperAdminSettings

# 1. Define a model
class Product(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    name: str
    price: float

# 2. Create app and admin
engine = create_async_engine("sqlite+aiosqlite:///app.db")
app = FastAPI()
# create_tables=True creates the SQLModel tables on startup: fine for a first run,
# but use your own migrations in production
admin = Admin(app, engine=engine, settings=HyperAdminSettings(create_tables=True))

# 3. Register the model
site.register(Product)

# 4. Mount the admin interface
admin.mount("/admin")
```

Navigate to `http://localhost:8000/admin/` to see your admin panel.

## Registering models

### Option A — direct registration

```python
from hyperadmin.core.registry import site
from hyperadmin.core.options import AdminOptions

site.register(Product)

# With options (disable delete)
site.register(Order, options=AdminOptions(can_delete=False))
```

### Option B — a `ModelAdmin` subclass

```python
from typing import ClassVar

from hyperadmin.core.model import ModelAdmin
from hyperadmin.core.registry import site


class ProductAdmin(ModelAdmin):
    list_display: ClassVar[list[str]] = ["name", "price"]
    search_fields: ClassVar[list[str]] = ["name"]
    list_filter: ClassVar[list[str]] = ["price"]


site.register(Product, ProductAdmin)
```

### Option C — discover `admin.py` modules

Put the registrations in an `admin.py` module in your app package, and list the package in
the `discover_apps` setting:

```python
# myapp/admin.py
from hyperadmin.core.registry import site
from myapp.models import Product

site.register(Product)

# main.py
from hyperadmin.core.settings import HyperAdminSettings

admin = Admin(app, engine=engine, settings=HyperAdminSettings(discover_apps=["myapp"]))
```

Every setting can also come from the environment, for example
`HYPERADMIN_DISCOVER_APPS='["myapp"]'`.

### Option D — zero-config auto-discovery

`HyperAdminSettings(auto_discover=True)` registers every SQLModel `table=True` model it finds,
with inferred list columns, search fields and filters. Plain SQLAlchemy models are not found
yet, so register those explicitly.

### Plain SQLAlchemy models

Models built on SQLAlchemy 2.0 `DeclarativeBase` (or the legacy `declarative_base()`) register
with the same `site.register(Model)` call. HyperAdmin builds their form and list schema from the
mapper. Create their tables with your own migrations or `Base.metadata.create_all`, because
`create_tables` covers SQLModel tables only. See
[Add HyperAdmin to an existing app](guides/existing-app.md#1-register-your-models).

## Customisation

### Restrict operations

```python
from hyperadmin.core.options import AdminOptions

site.register(Invoice, options=AdminOptions(
    can_create=False,
    can_delete=False,
))
```

### Override templates

Provide custom template directories searched before the built-in ones:

```python
settings = HyperAdminSettings(template_dirs=["my_templates/"])
admin = Admin(app, engine=engine, settings=settings)
```

HyperAdmin resolves templates in this order:

1. `{app_label}/{model_name}/{view_name}.html`
2. `{app_label}/{model_name}/default.html`
3. `{app_label}/{view_name}.html`
4. `{app_label}/default.html`
5. `{view_name}.html`
6. `default.html`

For example, to override the list view for a `User` model in a `users` app, create:
`my_templates/users/user/list.html`

---

Next: [Tutorial](tutorial.md)
