# ERP (Bookkeeping) Example

The ERP example is a full, domain-driven reference application that demonstrates HyperAdmin
in a realistic multi-module setup. It is the recommended starting point for adopters building
admin interfaces over relational data.

Source: [`examples/erp/`](https://github.com/yevheniidehtiar/hyper-admin/tree/master/examples/erp)

---

## What it demonstrates

- **Multi-module auto-discovery** — each domain (`contacts`, `sales`, `purchases`, `accounting`)
  is a standalone Python package; `Admin(discover_apps=[...])` wires them all automatically.
- **Relational data** — invoices belong to contacts, invoice items belong to invoices, journal
  lines belong to journal entries. HyperAdmin handles all FK list/detail views out of the box.
- **Built-in RBAC** — `hyperadmin.auth` is added as a discovered app; a `SessionAuthBackend` and
  `ModelPermissionChecker` guard every route.
- **Custom report** — the Annual Profit & Loss view shows how to add a custom FastAPI router and
  Jinja2 template that integrate with the admin sidebar and base layout.
- **Large seed dataset** — 100 contacts, 500+ invoices, 800+ bills give meaningful pagination,
  search, and sort behaviour under realistic load.

---

## Modules

| Module | Key Models | Description |
|--------|-----------|-------------|
| `contacts` | `Contact` | Customers and suppliers |
| `sales` | `Invoice`, `InvoiceItem` | Customer invoices with line items |
| `purchases` | `Bill`, `BillItem` | Supplier bills with line items |
| `accounting` | `Account`, `JournalEntry`, `JournalLine` | Chart of accounts, double-entry ledger |
| `auth` | `User`, `Group`, `Permission` | Built-in HyperAdmin RBAC |

---

## Quick start

### Docker (zero setup)

```bash
docker compose -f examples/erp/docker-compose.yml up --build
```

Open [http://localhost:8000/admin](http://localhost:8000/admin) — login `admin` / `admin`.

### Local (uv)

```bash
uv sync --all-extras
uv run fastapi dev examples/erp/main.py
```

Open [http://127.0.0.1:8000/admin](http://127.0.0.1:8000/admin) — login `admin` / `admin`.

### Seed command

The database is seeded automatically on first start. To reseed from scratch:

```bash
rm erp.db
uv run fastapi dev examples/erp/main.py
```

---

## Key files

| File | Purpose |
|------|---------|
| `main.py` | FastAPI app, Admin wiring, lifespan seeding |
| `db.py` | Async SQLite engine |
| `seed.py` | Faker-based seed script (contacts, invoices, bills, accounts) |
| `*/models.py` | SQLModel table definitions per module |
| `*/admin.py` | `ModelAdmin` registrations per module |
| `reports/views.py` | Custom Annual P&L FastAPI router |
| `templates/reports/profit_loss.html` | Custom Jinja2 report template |

---

## Custom P&L report

The report extends HyperAdmin with a plain FastAPI `APIRouter`:

```python
# examples/erp/main.py (excerpt)
app.include_router(reports_router)

admin.templates.env.globals["nav_items"].append(
    {"name": "Profit & Loss Report", "url": "/reports/profit-loss", "icon": "ha-icon-chart"}
)
```

The template at `templates/reports/profit_loss.html` extends `{% extends "base.html" %}` so it
inherits the sidebar, header, and HTMX bindings without any extra setup.

Visit `/admin/reports/profit-loss?year=2024` (or leave `year` blank for the current year).

---

Next: [Frontend Overview](../frontend/overview.md)
