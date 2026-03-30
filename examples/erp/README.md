# Bookkeeping ERP Example

A comprehensive, domain-driven reference application demonstrating **HyperAdmin** with relational
data, multi-module auto-discovery, and a custom Annual Profit & Loss report.

---

## Modules

| Module | Key Models | Description |
|--------|-----------|-------------|
| `contacts` | `Contact` | Customers and suppliers |
| `sales` | `Invoice`, `InvoiceItem` | Customer invoices with line items |
| `purchases` | `Bill`, `BillItem` | Supplier bills with line items |
| `accounting` | `Account`, `JournalEntry`, `JournalLine` | Chart of accounts and double-entry ledger |
| `auth` | `User`, `Group`, `Permission` | Built-in HyperAdmin RBAC |

Custom report: **Annual Profit & Loss** — aggregates revenue and expense journal lines for any
calendar year and renders a formatted HTML report at `/admin/reports/profit-loss`.

---

## Running the example

### Docker (recommended — zero setup)

```bash
docker compose -f examples/erp/docker-compose.yml up --build
```

Open [http://localhost:8000/admin](http://localhost:8000/admin).

### Local (uv)

```bash
# Install all extras (faker, aiosqlite, etc.)
uv sync --all-extras

# Start the dev server — DB is created and seeded automatically on first run
uv run fastapi dev examples/erp/main.py
```

Open [http://127.0.0.1:8000/admin](http://127.0.0.1:8000/admin).

Login with **`admin`** / **`admin`**.

---

## Seeding

The database is seeded automatically on every cold start (when the DB is empty). The seed script
creates:

- 1 superuser (`admin` / `admin`)
- 100 contacts (mix of customers and suppliers)
- 500+ invoices with line items and journal entries
- 800+ bills with line items and journal entries
- A complete chart of accounts

To re-seed, delete the SQLite file and restart:

```bash
rm erp.db
uv run fastapi dev examples/erp/main.py
```

---

## Screenshot

<!-- TODO: replace with actual screenshot after first run -->
![HyperAdmin ERP admin interface](../../docs/assets/erp-screenshot.png)

---

## Custom P&L report

The report is mounted at `/admin/reports/profit-loss` and a link appears in the sidebar. It
queries `JournalLine` records joined to `Account` and `JournalEntry` for the selected year and
groups them by account type (Revenue / Expense).

Navigate to **Profit & Loss Report** in the sidebar, or visit:
[http://127.0.0.1:8000/admin/reports/profit-loss](http://127.0.0.1:8000/admin/reports/profit-loss)
