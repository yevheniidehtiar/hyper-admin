# Examples

Two runnable example apps ship with HyperAdmin.

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

Shows a complex, domain-driven ERP system with multiple modules (Contacts, Sales, Purchases, Accounting) and built-in RBAC. Sample data is seeded automatically with thousands of records.

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

Next: [Frontend](frontend/overview.md)
