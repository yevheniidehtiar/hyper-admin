# Demo: v0.2.1 — Developer Experience & Examples

| Field | Value |
|-------|-------|
| Milestone | v0.2.1 — Developer Experience & Examples |
| Completed | Before 2026-04-01 |
| Demo Date | 2026-04-01 |
| Issues Closed | 9 |
| Squad | Squad 1 — Core Platform |

---

## What Shipped

This milestone focused on improving developer experience and building the ERP reference example
that is now used in all subsequent milestone demos.

### ERP Example Application

The `examples/erp/` directory provides a full-featured ERP demo with:

- `accounting/` — Chart of accounts, journal entries, invoices
- `contacts/` — Customers and vendor management
- `purchases/` — Purchase orders, line items
- `reports/` — Summary views
- `sales/` — Sales orders, quotes
- `seed.py` — Database seeding with realistic demo data
- Docker Compose setup for local development

### Developer Experience Improvements

- Clearer error messages for misconfigured `AdminOptions`
- Type hints throughout the public API surface
- Improved IDE autocompletion support

---

## ERP Example

```bash
cd examples/erp
docker-compose up
# Visit http://localhost:8000/admin/
```

---

## Notes

This milestone predates the agent-memory system. Summary compiled from milestone #5 closed issues.
