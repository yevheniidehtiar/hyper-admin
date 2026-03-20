# Bookkeeping ERP Example

This is a comprehensive example demonstrating **HyperAdmin** in a modular, domain-driven (FastAPI) application. It models a Bookkeeping ERP system with domains for:

- **Contacts** (Customers, Suppliers)
- **Sales** (Invoices, Items)
- **Purchases** (Bills, Items)
- **Accounting** (Accounts, Journal Entries)
- **Auth** (Built-in hyper-admin RBAC)

## Running the Example

Run it from the project root using `uv`:

```bash
uv run fastapi dev examples/erp/main.py
```

The database (`erp.db`) will be automatically seeded with thousands of realistic records on the first run, using `Faker`.

Visit [http://127.0.0.1:8000/admin](http://127.0.0.1:8000/admin) to explore the system.
