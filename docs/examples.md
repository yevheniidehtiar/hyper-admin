# Examples

Three runnable example apps ship with HyperAdmin.

## simple — Basic CRUD

Shows a single-model admin with auto-discovery and async SQLite.

```python
# examples/simple/main.py
from fastapi import FastAPI
from sqlalchemy.ext.asyncio import create_async_engine
from sqlmodel import SQLModel, Field
from hyperadmin.main import Admin

engine = create_async_engine("sqlite+aiosqlite:///simple_app.db")

class User(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    name: str
    email: str

app = FastAPI()
admin = Admin(app, engine=engine, discover_apps=["examples.simple"])
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

Next: [Frontend](frontend/overview.md)
