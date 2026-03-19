# Getting Started

## Prerequisites

- Python 3.10+
- A FastAPI application
- SQLModel or SQLAlchemy for your data models

## Installation

=== "pip"
    ```bash
    pip install hyperadmin
    ```

=== "uv"
    ```bash
    uv add hyperadmin
    ```

=== "poetry"
    ```bash
    poetry add hyperadmin
    ```

## Quickstart

The minimal setup needs three things: an engine, model registration, and a mount path.

```python
from fastapi import FastAPI
from sqlmodel import SQLModel, Field, create_engine
from hyperadmin import Admin
from hyperadmin.core.registry import site

# 1. Define a model
class Product(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    name: str
    price: float

# 2. Create app and admin
app = FastAPI()
admin = Admin(app, engine=engine)

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

### Option B — ModelView subclassing

```python
from hyperadmin.views.dynamic import ModelView

class ProductAdmin(ModelView, model=Product):
    column_searchable_list = [Product.name]
    icon = "inventory"
    name_plural = "Products"
```

`ModelView` subclasses call `site.register()` automatically at import time.

### Option C — auto-discovery

Place a `admin.py` file in your app package and pass the package name to `Admin`:

```python
# myapp/admin.py
from hyperadmin.core.registry import site
from myapp.models import Product
site.register(Product)

# main.py
admin = Admin(app, engine=engine, discover_apps=["myapp"])
```

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
admin = Admin(app, engine=engine, template_dirs=["my_templates/"])
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
