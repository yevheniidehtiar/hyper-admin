# Tutorial

This tutorial will guide you through the process of setting up HyperAdmin and customizing it for your needs.

## 1. Installation

First, install HyperAdmin and its dependencies:

```bash
pip install hyperadmin
```

## 2. Basic Setup

Here's how to create a simple admin interface for your FastAPI application.

```python
from fastapi import FastAPI
from sqlmodel import Field, SQLModel, create_engine
from hyperadmin.main import Admin
from hyperadmin.core.registry import site

# 1. Define your models
class Product(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    name: str
    price: float

# 2. Create a FastAPI app and an admin instance
app = FastAPI()
admin = Admin(app=app)

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
