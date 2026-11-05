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

### Sidebar groups and icons

Group models by domain and give each one an icon on its admin class:

```python
from hyperadmin import Admin, NavGroup
from hyperadmin.core.model import ModelAdmin


class InvoiceAdmin(ModelAdmin):
    nav_group = "Accounting"  # sidebar group; plain or gettext_lazy label
    nav_order = 1  # position inside the group; ties sort by label
    icon = "receipt"  # a Lucide name from hyperadmin/static/icons


site.register(Invoice, InvoiceAdmin)

admin = Admin(
    app,
    engine=engine,
    nav_groups=[
        NavGroup("Sales", icon="shopping-cart", order=0),
        NavGroup("Accounting", icon="receipt", order=1, collapsed=True),
    ],
)
```

- Without `nav_group`, a model joins the group named by the `app_label` it was registered with,
  and otherwise the unnamed group at the top of the sidebar.
- Plugin pages join the group whose label matches their section.
- `nav_groups` sets the order, icon and initial collapsed state of groups. Groups you do not
  declare still appear, after the declared ones, sorted by label.
- A model without `icon` gets the generic `layout-grid` icon.
- Each group heading collapses its group, and the button at the top of the sidebar shrinks it
  to an icon rail on wide screens. Both choices are kept in cookies, per browser.
- Users only see the models they may view; a group with nothing visible is left out.

#### Pinned pages

With auth configured, every sidebar item gets a pin button (on hover or focus). Pinned
pages show in a "Pinned" group at the top of the sidebar, are stored per user in the
`hyperadmin_nav_pin` table, and follow the user to any device. A user can pin up to
`HyperAdminSettings.nav_pins_max` pages (20 by default). Pins of a page the user may no
longer view stay stored but are hidden. Without auth there are no pins.

### Keyboard shortcuts and unsaved changes

Press `?` on any admin page to list the shortcuts. On macOS, Cmd replaces Ctrl.

| Keys | Where | What it does |
|---|---|---|
| `?` or Ctrl+/ | everywhere | Show the shortcuts and the "Single-key shortcuts" switch |
| Ctrl+K | everywhere | Open the command palette |
| `/` | lists | Focus the search box |
| `j` / `k` | lists | Focus the next / previous row; Enter opens it |
| `x` | lists | Select the focused row for a bulk action |
| `c` | lists | Create a new record |
| Ctrl+S | forms | Save the form (or the open "+" popup form) |

- Single-key shortcuts do nothing while you type in a field. The switch in the `?` overlay
  turns them off in this browser (localStorage `ha-shortcuts`). Ctrl+K, Ctrl+S and Ctrl+/
  keep working.
- Create and edit forms keep Save in view at the bottom of the screen while you scroll.
- When a form has unsaved changes, leaving the page asks first. Saving does not ask, and
  deleting the record from its edit page asks only in the delete dialog. Turn the prompt off
  for a model with `AdminOptions(warn_unsaved_changes=False)`.

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
