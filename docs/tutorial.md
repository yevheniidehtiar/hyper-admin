# Tutorial

This tutorial will guide you through the process of setting up HyperAdmin and customizing it for your needs.

## 1. Installation

First, install HyperAdmin. It is in pre-release, so pin the version. The distribution is
`hyper-admin`; the import name is `hyperadmin`:

```bash
pip install hyper-admin==0.5.0a1
```

## 2. Basic Setup

Here's how to create a simple admin interface for your FastAPI application.

```python
from fastapi import FastAPI
from sqlalchemy.ext.asyncio import create_async_engine
from sqlmodel import Field, SQLModel
from hyperadmin import Admin
from hyperadmin.core.registry import site
from hyperadmin.core.settings import HyperAdminSettings

# 1. Define your models
class Product(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    name: str
    price: float

# 2. Create a FastAPI app and an admin instance
engine = create_async_engine("sqlite+aiosqlite:///app.db")
app = FastAPI()
# create_tables=True is for a first run; use your own migrations in production
admin = Admin(app, engine=engine, settings=HyperAdminSettings(create_tables=True))

# 3. Register your models
site.register(Product)

# 4. Mount the admin interface
admin.mount(path="/admin")
```

## 3. Customizing the Admin Interface

You can customize the admin interface for each model by using `AdminOptions`.

For example, if you want to disable the delete functionality for the `Product` model, you can do this:

```python
from hyperadmin.core.options import AdminOptions

# Create custom admin options
product_options = AdminOptions(can_delete=False)

# Register the model with the custom options
site.register(Product, options=product_options)
```

The available options are:
- `can_create`: Enable or disable the create view.
- `can_edit`: Enable or disable the update view.
- `can_delete`: Enable or disable the delete functionality.
- `can_list`: Enable or disable the list view.
- `can_detail`: Enable or disable the detail view.

---

Next: [Examples](examples.md)
