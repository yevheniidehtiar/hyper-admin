# Demo: v0.3.0 — Zero-Config & Auth

| Field | Value |
|-------|-------|
| Milestone | v0.3.0 — Zero-Config & Auth |
| Completed | 2026-03-31 |
| Demo Date | 2026-04-01 |
| Issues Closed | 23 |
| Squad | Squad 1 — Core Platform |
| Key PRs | #384, #385, #386 |

---

## What Shipped

### Zero-Config Auto-Discovery (#382, PR #386)

HyperAdmin can now auto-discover all SQLModel models registered in SQLModel metadata and
register them with smart defaults — no explicit `admin.register()` calls needed.

**Before (v0.2.x):**

```python
admin = Admin(engine=engine)
admin.register(Product, AdminOptions(list_display=["id", "name", "price"]))
admin.register(Customer, AdminOptions(list_display=["id", "name", "email"]))
# ... every model manually
```

**After (v0.3.0):**

```python
admin = Admin(engine=engine, auto_discover=True)
# Done — all models registered automatically with smart defaults
```

#### Features Delivered

| Issue | Feature |
|-------|---------|
| #363 | Model introspection utility — reads field metadata from SQLModel |
| #364 | Smart defaults: infer `list_display` from model structure |
| #365 | Smart defaults: infer `search_fields` from string/text fields |
| #366 | Smart defaults: infer `list_filter` from enum/bool fields |
| #367 | Auto-discovery: scan SQLModel metadata for registered models |
| #368 | `AdminOptions` accepts `None` to trigger smart defaults per field |
| #369 | Field labels inferred and displayed in list/detail views |
| #370 | Auto-register discovered models with smart defaults applied |
| #371 | `auto_discover` parameter added to `Admin()` constructor |
| #372 | 3-line zero-config demo verified with tests |
| #373 | E2E test: zero-config auto-discovery with mixed model types |

### Pydantic Settings — HyperAdminSettings (#383, PR #384)

Configuration is now first-class via `HyperAdminSettings`, backed by `pydantic-settings`.
Settings load from environment variables, `.env` files, and explicit constructor arguments.

```python
# Environment-driven configuration
# DATABASE_URL=postgresql://... ADMIN_SECRET_KEY=... in .env

admin = Admin()  # Reads from environment automatically
```

| Issue | Feature |
|-------|---------|
| #374 | SDD spec written and approved |
| #375 | `HyperAdminSettings` class with `pydantic-settings` |
| #376 | `Admin` class wired to use `HyperAdminSettings` |
| #377 | `db.py` hardcoded engine replaced with settings-driven engine |
| #378 | Secure `session_secret`: warns on default, enforced when auth enabled |
| #379 | Tests: settings loading, validation, environment variable override |
| #380 | ERP example updated to use `HyperAdminSettings` |

### Authentication End-to-End (#381, PR #385)

| Issue | Feature |
|-------|---------|
| #361 | Auth models (User/Group/Permission) auto-registered when `auth_backend` is set |
| #362 | E2E test: login → view protected model → logout flow |

---

## ERP Example Integration

The ERP example at `examples/erp/` demonstrates all v0.3.0 features:

- `db.py` uses `HyperAdminSettings` for database URL configuration
- `main.py` uses `auto_discover=True` to register all ERP models automatically
- Auth models auto-appear in the admin sidebar when `auth_backend` is configured
- Field labels are human-readable without explicit configuration (e.g., "Created At" from `created_at`)

Run the ERP example:

```bash
cd examples/erp
DATABASE_URL=sqlite:///./erp.db uv run uvicorn main:app --reload
# Visit http://localhost:8000/admin/
```

---

## Acceptance Checklist

- [x] All 23 issues closed
- [x] `area:docs` issues: #374 (SDD), #380 (examples docs) — both closed
- [x] ERP example updated to use new APIs (#380)
- [x] E2E tests passing for zero-config (#373) and auth flow (#362)
- [x] Settings validation with env override tested (#379)
