---
type: story
id: UXyCPKJjTC9R
title: "RFC: Migration guides & examples (from Django Admin, SQLAdmin, Flask-Admin)"
status: todo
priority: medium
assignee: null
labels:
  - documentation
  - rfc
estimate: null
epic_ref:
  id: EGeVWNoBWlNq
github:
  issue_number: 274
  repo: yevheniidehtiar/hyper-admin
  last_sync_hash: sha256:c8f3ceab4f3237eaa37a5adeddecb0259b78e6f460287f2994936f0b8f391e87
  synced_at: 2026-04-05T09:13:33.559Z
created_at: 2026-03-27T09:04:59Z
updated_at: 2026-03-27T09:04:59Z
---

## Summary

Comprehensive migration guides with side-by-side code comparisons and concept mapping tables for developers moving from Django Admin, SQLAdmin, and Flask-Admin to HyperAdmin.

Parent: #270

## Motivation

The biggest barrier to adoption isn't features — it's familiarity. Developers won't switch unless they can see *exactly* how their existing admin concepts map to HyperAdmin. Every mature framework has migration guides; HyperAdmin needs them to convert users from the 3 major competitors.

## Concept Mapping Tables

### Django Admin → HyperAdmin

| Django Admin | HyperAdmin | Notes |
|---|---|---|
| `admin.site.register(Model, ModelAdmin)` | `site.register(Model, MyAdmin)` | Nearly identical |
| `list_display` | `column_list` on ModelAdmin | |
| `search_fields` | `search_fields` on ModelAdmin | Needs generalization (currently hardcoded) |
| `list_filter` | `AdminOptions.list_filter` | Supports bool, enum, FK filters |
| `inlines` (Tabular/Stacked) | **Not implemented** | Relationships via FK selects, not inline editing |
| `actions` (bulk) | **Not implemented** | Per-row delete only; bulk actions planned Phase 3 |
| `has_add/change/delete_permission` | `AdminOptions.can_create/can_edit/can_delete` + `PermissionChecker` | |
| `save_model()` / `delete_model()` | `HyperAdminModel.before_save()` / `after_save()` | Lifecycle hooks |
| `@admin.register(Model)` decorator | `class MyView(ModelView, model=Model)` | `__init_subclass__` auto-registration |
| Django ORM `models.Model` | `SQLModel` (table=True) | Pydantic + SQLAlchemy hybrid |
| `django.contrib.auth` | `hyperadmin.auth.models` | Similar structure, Argon2 hashing |
| `autodiscover_modules` | `Admin(discover_apps=["myapp"])` | Same concept |
| `readonly_fields` | **Not implemented** | |
| `fieldsets` | **Not implemented** | Forms are flat |
| `date_hierarchy` | **Not implemented** | |

### SQLAdmin → HyperAdmin

| SQLAdmin | HyperAdmin | Notes |
|---|---|---|
| `class UserAdmin(ModelView, model=User)` | `class UserAdmin(ModelView, model=User)` | **Identical syntax** |
| `column_list` | `column_list` | Same name |
| `form_columns` | `form_columns` | Same name |
| `column_searchable_list` | `search_fields` | Different name |
| `can_create/edit/delete` | `AdminOptions(can_create=...)` | |
| `name` / `name_plural` | `name` / `name_plural` | |
| `icon` | `icon` | |
| `Admin(app, engine)` | `Admin(app, engine=engine)` | Nearly identical |
| `on_model_change()` | `before_save()` / `after_save()` | On model, not view |

### Flask-Admin → HyperAdmin

| Flask-Admin | HyperAdmin | Notes |
|---|---|---|
| `admin.add_view(ModelView(Model, session))` | `site.register(Model, MyAdmin)` | No session needed |
| `column_list` | `column_list` | Same |
| `column_searchable_list` | `search_fields` | Different name |
| `column_filters` | `list_filter` | Different name |
| `form_columns` | `form_columns` | Same |
| `WTForms` | `PydanticForm` | Auto-generated from Pydantic schema |
| `column_editable_list` | **Not implemented** | No inline list editing |
| Flask-Login | `SessionAuthBackend` + `AuthenticationMiddleware` | |

## Key Migration Pain Points to Document

### 1. ORM Migration (Critical)
- Every model must be rewritten: `CharField` → `str = Field(max_length=...)`, `ForeignKey` → `int = Field(foreign_key="table.id")` + `Relationship()`
- Django's `makemigrations`/`migrate` → Alembic or `SQLModel.metadata.create_all`
- `QuerySet` chaining → SQLAlchemy `select()` statements

### 2. Async Paradigm Shift
- Django Admin is synchronous; HyperAdmin is fully async
- All DB operations use `async/await` with `AsyncEngine`
- `SQLModelAdapter` handles async session lifecycle

### 3. Auth Migration
- Similar User/Group/Permission structure but different tables and hashing (Argon2 vs PBKDF2)
- Permission codenames follow same `{action}_{model}` pattern
- No CSRF protection built in (yet)

### 4. Template System
- Both Jinja2-based, but HyperAdmin uses HTMX for partial updates (paradigm shift from full-page renders)
- Override hierarchy: `{app_label}/{model}/{view}.html` → `{app_label}/{view}.html` → `{view}.html`

## Recommended Example Projects

### Tier 1 (Must-have)

1. **Blog** — Post/Author/Category with FK, Enum filters (PostStatus), search on title/body. Universal starting point, maps to every framework's tutorial.

2. **E-commerce Catalog** — Product/Category/Order with M2M tags, FK cascading selects, image upload, computed properties. Covers most real-world patterns.

### Tier 2 (Valuable)

3. **CRM** — Extend existing `examples/erp/contacts/`. Shows permission-based access (sales vs support teams), custom template overrides.

4. **Multi-tenant SaaS** — Custom adapters (filter by tenant_id), middleware customization. Aspirational — needs features from Phase 5.

## Guide Structure (Per Source Framework)

```
1. Quick Reference Table (concept mapping)
2. Models: ORM Migration
   - Side-by-side: Django/Flask Model vs SQLModel
   - Fields, relationships, constraints, migrations
3. Admin Registration
   - Side-by-side: register patterns
   - ModelAdmin class attributes comparison
4. List View Configuration
   - column_list, search, filters, sorting
5. Form Configuration
   - form_columns, widgets, validation
6. Authentication & Permissions
   - User model, permission checking, middleware
7. Template Customization
   - Override hierarchy, HTMX patterns
8. Complete Migration Example (Blog app)
9. What's Not Yet Available (honest gap list)
```

**Key principle:** Be honest about gaps (inlines, bulk actions, fieldsets). This builds trust and helps users plan workarounds upfront.

## Deliverables

- [ ] `docs/migration/from-django-admin.md`
- [ ] `docs/migration/from-sqladmin.md`
- [ ] `docs/migration/from-flask-admin.md`
- [ ] `examples/blog/` — complete migrated Blog example
- [ ] `examples/ecommerce/` — complete E-commerce catalog example

## Open Questions

- [ ] Should migration guides live in docs site or as standalone pages?
- [ ] Video walkthroughs alongside written guides?
- [ ] Automated migration tool? (Parse Django `admin.py` → generate HyperAdmin equivalent via LLM — see #TBD)
- [ ] How to handle the "What's Not Available" section — link to roadmap issues for each gap?

---
https://claude.ai/code/session_01XktRz2PFThVGgPMoUmaEjc
