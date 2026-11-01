<div align="center">
  <a href="https://yevheniidehtiar.github.io/hyper-admin/" target="_blank">
    <img src="assets/logo.svg" alt="HyperAdmin Logo" width="150"/>
  </a>
  <h1>HyperAdmin</h1>
  <p>The Django-admin experience for FastAPI, generated from your Pydantic, SQLModel or SQLAlchemy models.</p>
</div>

---

```bash
pip install hyper-admin==0.5.0a1
```

HyperAdmin is in pre-release, so pin the version. The distribution is `hyper-admin`; the import
name is `hyperadmin`.

**HyperAdmin** adds a full admin to the FastAPI app you already have. It reads your models,
generates list, detail, create and edit pages with search, filters and auth, and mounts them
at a path in your app. It uses **HTMX** for interactivity, so there is no JavaScript build step.

## Quick example

```python
from fastapi import FastAPI
from sqlalchemy.ext.asyncio import create_async_engine
from sqlmodel import SQLModel, Field
from hyperadmin import Admin
from hyperadmin.core.registry import site
from hyperadmin.core.settings import HyperAdminSettings

class Product(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    name: str
    price: float

engine = create_async_engine("sqlite+aiosqlite:///app.db")
app = FastAPI()
# create_tables=True is for a quick start; use your own migrations in production
admin = Admin(app, engine=engine, settings=HyperAdminSettings(create_tables=True))
site.register(Product)
admin.mount("/admin")
```

## Where to go next

- [Getting Started](getting-started.md): install HyperAdmin and build your first admin
- [Add HyperAdmin to an existing app](guides/existing-app.md): your models, keys, engine, migrations and auth
- [Compatibility & Performance](compatibility.md): supported stacks, results on real open-source apps, timings
- [Examples](examples.md): five runnable apps, from a single model to an ERP
- [Frontend](frontend/overview.md): templates, CSS tokens, widgets, HTMX patterns
- [API Reference](api/index.md): classes and methods
- [Roadmap](roadmap.md): what has shipped and what comes next

## Key features

**Works with your app**

- **Generated from your models.** SQLModel `table=True` models and plain SQLAlchemy 2.0 /
  2.1 models are both supported. Forms, filters and detail pages come from the model, so
  they stay in sync with it.
- **Mounts as an isolated sub-application.** The admin has its own static files, route
  namespace and cookie, and leaves your routes, `/static` and OpenAPI schema alone.
- **Your keys, engine and migrations.** Integer, UUID and string primary keys work. Pass in your
  own engine or `session_factory`. HyperAdmin creates no tables unless you ask it to.
- **Your auth, or ours.** Plug in your own login with `ExternalAuth`, or use the built-in
  session auth with users, groups, permissions and email-OTP MFA.
- **Tested on real apps.** Polar (138 models), Langflow, Mealie and Open WebUI run with
  their models unchanged, and every model's pages render without errors.

**CRUD and data entry**

- List, detail, create, update and delete, with search, sorting and pagination
- Fieldsets, multi-column form layouts and inline formsets for related rows
- Foreign-key and many-to-many selects, async autocomplete, dependent selects, and a popup
  to create a related record without leaving the form
- Inline cell editing in the list view
- Bulk actions with a result for each row, and custom `@action`s that can take a form
- File and image uploads: local or S3-compatible storage, thumbnails, EXIF auto-rotation,
  drag-and-drop, and a progress bar with retry

**Finding data**

- A filter sidebar with date-range, choice, boolean, relation and "mine only" filters
- Per-user saved views and filter state you can share by URL
- Tabbed detail panels that load lazily, including streamed PDF panels

**Security and permissions**

- CSRF protection that works behind a TLS proxy, and sensitive fields hidden by default
- Object-level permissions and row-level security through a `get_queryset` hook
- A permissions matrix to edit model × action grants for each group, with an audit trail

**Collaboration and reporting**

- Live CRUD notifications over SSE or WebSocket, with in-memory or Redis pub/sub
- Presence: see who else is editing a record
- The `hyperadmin-reports` plugin: crosstab reports, server-rendered SVG charts, CSV and XLSX
  export
- A plugin registry for adding pages, navigation, templates and permissions

**Interface**

- Light and dark themes, a responsive layout for mobile, WCAG 2.1 AA
- 20 locales with right-to-left support, and translated validation messages

---

Next: [Getting Started](getting-started.md)
