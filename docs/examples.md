# Examples

Five runnable example apps ship with HyperAdmin.

## simple — Basic CRUD

Shows a small admin (users, countries, cities, uploads) wired through `discover_apps` and async SQLite.

```python
# examples/simple/main.py (excerpt)
from fastapi import FastAPI
from sqlalchemy.ext.asyncio import create_async_engine
from hyperadmin import Admin
from hyperadmin.core.settings import HyperAdminSettings

engine = create_async_engine("sqlite+aiosqlite:///simple_app.db")

# examples/simple/admin.py registers the models; discover_apps imports it
settings = HyperAdminSettings(discover_apps=["examples.simple"])

app = FastAPI(lifespan=lifespan)  # the lifespan creates and seeds the tables
admin = Admin(app, engine=engine, settings=settings, storage=upload_storage)
admin.mount("/admin")
```

**Run locally:**

```bash
uv run fastapi dev examples/simple/main.py
```

Open [http://localhost:8000/admin/](http://localhost:8000/admin/)

---

## erp — Bookkeeping ERP (Modular)

Shows a complex, domain-driven ERP system with multiple modules (Contacts, Sales, Purchases,
Accounting) and built-in RBAC. Sample data is seeded automatically with thousands of records.

[Full ERP example documentation →](examples/erp.md)

**Run with Docker** (recommended — zero setup):

```bash
docker compose -f examples/erp/docker-compose.yml up --build
```

Open [http://localhost:8000/admin/](http://localhost:8000/admin/)

**Run locally:**

```bash
uv sync --all-extras
uv run fastapi dev examples/erp/main.py
```

### Features

- **Double-entry bookkeeping**: Automatic journal entries created for invoices and bills.
- **Role-Based Access Control**: Built-in `hyperadmin.auth` integration.
- **Custom Reports**: Includes a custom Annual Profit & Loss report.
- **Large Dataset**: Demonstrates performance and pagination with 1000+ seeded records.

### Models overview

| Module | Key Models |
|--------|------------|
| `contacts` | `Contact` (Customers, Suppliers) |
| `sales` | `Invoice`, `InvoiceItem` |
| `purchases` | `Bill` (Expenses), `BillItem` |
| `accounting` | `Account`, `JournalEntry`, `JournalLine` |
| `auth` | `User`, `Group`, `Permission` |

---

## byoa — Bring your own app

An existing FastAPI app with its own lifespan, `/static` mount, `session` cookie, JWT-protected
`/api` and a UUID-keyed user model, with HyperAdmin added through
`Admin(auth=ExternalAuth(...), session_factory=...)`. Walkthrough:
[Add HyperAdmin to an existing FastAPI app](guides/existing-app.md).

**Run locally:**

```bash
HYPERADMIN_DEBUG=true uv run uvicorn examples.byoa.main:app --reload
```

`HYPERADMIN_DEBUG=true` lets the admin start with its default secret key for local development;
without it, set `HYPERADMIN_SECRET_KEY`, or the admin refuses to start. The host's own
`BYOA_SESSION_SECRET` and `BYOA_JWT_SECRET` fall back to demo values and log a warning.

Open [http://localhost:8000/admin/](http://localhost:8000/admin/) and sign in as `ada` / `lovelace`
(superuser) or `grace` / `hopper` (staff, view-only).

!!! warning "Demo data"
    The seeded `ada` and `grace` accounts have published passwords, and the fallback secrets are
    public. Delete the accounts and set real secrets before deploying anything built from this
    example.

---

## sqlalchemy — Plain SQLAlchemy 2.0

HyperAdmin on a plain SQLAlchemy 2.0 `DeclarativeBase`, with no SQLModel. The models are
registered explicitly, and HyperAdmin builds each model's form and list schema from its
mapper. It shows enums (`SAEnum` and an enum behind a `TypeDecorator`), a JSON column, a foreign
key, a `server_default` timestamp and a sensitive column that is hidden on the detail page.

**Run locally:**

```bash
uv sync --all-extras
uv run uvicorn examples.sqlalchemy.main:app
```

Open [http://localhost:8000/admin/](http://localhost:8000/admin/)

---

## full-demo — Every feature together

One app that exercises the features together, with framework-neutral models (`Supplier`,
`Variant`, `Product`, `Order`, `OrderItem`, `Invoice`): inline rows with per-row errors, bulk
actions, detail panels with a PDF, the filter sidebar and saved views, a dependent
foreign key with a "+" popup, image uploads, a report with a chart and CSV / XLSX export, and
the permissions matrix. A Playwright qualification suite (`uv run poe test:e2e:qualification`)
checks each of them.

**Run locally:**

```bash
uv sync --all-extras
uv run examples/full-demo/main.py
```

Open [http://localhost:8000/admin/](http://localhost:8000/admin/) and sign in as `alice` /
`secret123` (superuser), or as `viewer` / `secret123` (limited permissions).

---

Next: [Frontend](frontend/overview.md)
