# HyperAdmin: The Definitive Python Admin Framework Roadmap

## Context

HyperAdmin (v0.1.0) is a Pydantic-native, async-first admin interface for FastAPI powered by HTMX. Phase 2 is ~90% complete with full CRUD, dynamic forms (12+ widgets), FK/M2M relationships, filtering, sorting, search, pagination, and partial auth. The goal: transform HyperAdmin into **the best, fastest, and most accessible Python auto-generated admin panel** — the framework developers choose *over* Django Admin, SQLAdmin, and Flask-Admin.

**Competitors to beat:**
| Feature | Django Admin | SQLAdmin | Flask-Admin | HyperAdmin (today) |
|---------|-------------|----------|-------------|-------------------|
| Async | No | Partial | No | **Full** |
| Pydantic-native | No | Minimal | No | **Yes** |
| Zero-config | Moderate | Good | Moderate | Good |
| i18n | Excellent | None | Some | None |
| Accessibility | Basic | Basic | Basic | Partial (ARIA) |
| Plugin ecosystem | Mature | None | Moderate | None |
| Real-time | No | No | No | No |

**Key differentiators to pursue:** Zero-config setup (3 lines), async-first performance (<100ms TTFB), WCAG 2.1 AA accessibility, type-safe developer experience, real-time capabilities, AI-ready features.

---

## Phase 2.5 — "Ship It" (v0.2.0)
**Theme: Complete the foundation, make it installable and usable by real developers**

### Epic 2.5.1: Wire Authentication End-to-End
Auth models exist but aren't fully connected to endpoints.
- Wire `AuthenticationMiddleware` to all admin routes
- Complete session-based login/logout flow with tests
- Wire `PermissionChecker` to view-level enforcement (403 on denied)
- `createsuperuser` CLI command verified working
- E2E test: login → CRUD → logout flow

**Files:** `auth/middleware.py`, `auth/views.py`, `auth/session.py`, `auth/permissions.py`, `core/app.py`

### Epic 2.5.2: Configurable Search
Search is hardcoded to `name` and `email` fields.
- Add `search_fields` to `ModelAdmin` / `AdminOptions`
- Adapter: build dynamic search across configured fields
- Support partial match (ILIKE) and exact match modes

**Files:** `core/options.py`, `adapters/sqlmodel.py`, `adapters/sqlalchemy.py`, `views/dynamic.py`

### Epic 2.5.3: Documentation & Examples
- Complete "Getting Started" tutorial (install → 3-line admin → customize)
- API reference for `Admin`, `ModelAdmin`, `AdminOptions`, `BaseAdapter`
- Finalize ERP example as a complete runnable demo
- Add screenshot/GIF to README

**Files:** `docs/`, `examples/`, `README.md`

### Epic 2.5.4: Polish & Bug Fixes
- Form validation error display (field-level + non-field errors)
- Confirmation dialogs for delete actions
- Flash messages / toast notifications for success/error feedback
- Mobile-responsive sidebar (hamburger menu)

**Files:** `templates/components/`, `templates/widgets/`, `static/hyperadmin.css`

---

## Phase 3 — "Developer Love" (v0.3.0)
**Theme: Make developers productive in minutes, not hours**

### Epic 3.1: Zero-Config Admin (3 Lines of Code)
The killer feature — beat every competitor on setup speed:
```python
from hyperadmin import Admin
admin = Admin(app, engine=engine)
admin.mount("/admin")  # auto-discovers all SQLModel models
```
- Auto-register all SQLModel/SQLAlchemy models without explicit `admin.py`
- Smart defaults: infer `list_display`, `search_fields`, `list_filter` from model fields
- Convention-over-configuration: sensible defaults that work 90% of the time

**Files:** `discover.py`, `core/registry.py`, `core/model.py`, `core/options.py`

### Epic 3.2: File Upload System
- `uploads/` module: `FileField`, `ImageField` support in forms
- Storage backends: local filesystem + S3-compatible (via protocol)
- Image preview widget with drag-and-drop
- Thumbnail generation for image fields (Pillow already a dependency)

**Files:** `uploads/storage.py`, `uploads/fields.py`, `views/forms.py`, `templates/widgets/file_input.html`

### Epic 3.3: Custom Model Actions
- `actions/` module: register custom actions per model
- Bulk actions on list view (select rows → action dropdown)
- Single-object actions on detail view
- Built-in actions: export selected, delete selected
- Action confirmation dialogs via HTMX

**Files:** `actions/registry.py`, `actions/builtin.py`, `views/dynamic.py`, `templates/components/action_bar.html`

### Epic 3.4: Export / Import
- CSV and JSON export from list view (respects current filters)
- CSV/JSON import with validation preview
- Background processing for large datasets (async task)

**Files:** `actions/export.py`, `actions/import_data.py`, `templates/components/export_bar.html`

### Epic 3.5: Advanced Filtering
- Date range filters
- Numeric range filters (min/max)
- Multi-value select filters
- "Save filter" presets per user
- Filter builder UI (AND/OR conditions)

**Files:** `core/filters.py`, `views/dynamic.py`, `templates/components/filter_bar.html`

---

## Phase 4 — "Accessible & Beautiful" (v0.4.0)
**Theme: WCAG 2.1 AA compliance + modern design system — become THE most accessible admin**

### Epic 4.1: WCAG 2.1 AA Accessibility Audit & Fix
No Python admin panel currently claims WCAG compliance — this is a unique differentiator.
- Full keyboard navigation (Tab, Enter, Escape, Arrow keys)
- Skip-to-content links
- Focus management on HTMX swaps (focus trap in modals, restore after swap)
- `aria-live` regions for all dynamic content updates
- Color contrast ratios ≥ 4.5:1 for text, ≥ 3:1 for large text
- Form error announcements for screen readers
- Automated a11y testing with axe-core in Playwright E2E suite

**Files:** All templates, `static/hyperadmin.css`, `tests/e2e/`

### Epic 4.2: Theme System & Dark Mode
- CSS custom properties (variables) for all colors, spacing, typography
- Light/dark mode toggle with system preference detection
- `prefers-reduced-motion` support
- Theme configuration via `Admin(theme="dark")` or `Admin(theme=CustomTheme(...))`
- High-contrast mode for accessibility

**Files:** `static/hyperadmin.css`, `templates/base.html`, `core/app.py`, `core/theme.py`

### Epic 4.3: Responsive Design Overhaul
- Mobile-first responsive grid system
- Collapsible sidebar with swipe gestures (Alpine.js)
- Responsive data tables (card layout on small screens)
- Touch-friendly action buttons and form controls

**Files:** `static/hyperadmin.css`, `templates/components/`, `templates/base.html`

### Epic 4.4: Internationalization (i18n)
Django Admin's i18n is excellent — match and exceed it.
- Translation system using Python `gettext` or lightweight alternative
- Extract all UI strings to message catalogs
- Ship with English, Spanish, French, German, Chinese, Japanese, Ukrainian
- RTL layout support (Arabic, Hebrew)
- `Admin(locale="uk")` configuration
- Community contribution workflow for new translations

**Files:** `core/i18n.py`, `locale/`, all templates (wrap strings in `_()`)

---

## Phase 5 — "Enterprise Ready" (v0.5.0)
**Theme: Features that make HyperAdmin viable for production enterprise apps**

### Epic 5.1: Audit / Activity Log
- Track all CRUD operations (who, what, when, old/new values)
- `AuditLog` model with JSON diff storage
- Audit trail view per object (timeline UI)
- Configurable: enable/disable per model via `AdminOptions`

**Files:** `audit/models.py`, `audit/middleware.py`, `adapters/sqlmodel.py`, `templates/components/audit_trail.html`

### Epic 5.2: Row-Level Security & Multi-Tenancy
- Object-level permissions (e.g., "user can only see their own records")
- `get_queryset(request)` hook on `ModelAdmin` for dynamic filtering
- Tenant-aware adapter filtering (multi-tenant SaaS support)
- Permission predicates: `has_object_permission(request, obj, action)`

**Files:** `auth/permissions.py`, `core/model.py`, `adapters/sqlmodel.py`

### Epic 5.3: SSO & OAuth2 Authentication
- OAuth2 / OpenID Connect backend (Google, GitHub, Azure AD)
- SAML2 backend for enterprise SSO
- Pluggable auth backend protocol (already exists, extend it)
- MFA support (TOTP via `pyotp`)

**Files:** `auth/oauth.py`, `auth/saml.py`, `auth/mfa.py`, `auth/backend.py`

### Epic 5.4: Dashboard Builder
- Customizable admin dashboard with widget cards
- Built-in widgets: count, chart (bar/line/pie), recent items, quick actions
- Per-user dashboard layout (drag & drop via HTMX + SortableJS)
- Widget protocol for custom dashboard widgets
- Data aggregation helpers in adapters

**Files:** `dashboard/widgets.py`, `dashboard/layout.py`, `templates/dashboard.html`, `views/dashboard.py`

### Epic 5.5: Inline Editing & Related Object Management
- Inline formsets for related objects (edit child objects on parent form)
- Inline table editing (click cell → edit in place → save via HTMX)
- Nested relationship creation (create related object from FK dropdown)

**Files:** `views/forms.py`, `views/dynamic.py`, `templates/components/inline_formset.html`

---

## Phase 6 — "The Future" (v1.0.0)
**Theme: AI-powered, real-time, extensible — the admin panel of 2027**

### Epic 6.1: Plugin & Extension System
- Formal plugin registry with entry points (`hyperadmin.plugins`)
- Plugin hooks: `on_model_register`, `on_before_create`, `on_after_delete`, etc.
- Plugin marketplace/directory (docs site)
- Plugin template: scaffold a new plugin with `hyperadmin create-plugin`

**Files:** `plugins/registry.py`, `plugins/hooks.py`, `core/app.py`

### Epic 6.2: Real-Time Updates (WebSocket)
- WebSocket channel per model list view
- Live updates: new/updated/deleted rows appear without refresh
- Real-time dashboard widgets
- Collaborative editing indicators ("User X is editing this record")
- Built on Starlette WebSocket support (already in FastAPI)

**Files:** `realtime/channels.py`, `realtime/broadcast.py`, `views/websocket.py`, `templates/components/live_table.html`

### Epic 6.3: AI-Powered Features
- Natural language search ("show me orders over $1000 from last month")
- AI-assisted data entry (auto-fill fields from context)
- Smart suggestions for filter combinations
- Anomaly detection highlights on dashboards
- Optional — requires LLM API key, degrades gracefully without

**Files:** `ai/search.py`, `ai/suggestions.py`, `core/options.py`

### Epic 6.4: Performance & Benchmarks
- Benchmark suite: measure TTFB, query count, memory usage per operation
- Target: <100ms TTFB for list views (1M rows with pagination)
- Query optimization: automatic `select_related` / `selectinload` analysis
- Response caching with HTMX-aware cache invalidation
- Virtual scrolling for large lists (HTMX + Intersection Observer)
- Published benchmark comparison vs. Django Admin, SQLAdmin

**Files:** `benchmarks/`, `core/caching.py`, `adapters/sqlmodel.py`

### Epic 6.5: Additional ORM Adapters
- Tortoise ORM adapter
- Piccolo ORM adapter
- MongoDB adapter (via Motor/Beanie)
- Generic REST API adapter (connect to any API as data source)

**Files:** `adapters/tortoise.py`, `adapters/piccolo.py`, `adapters/mongodb.py`, `adapters/rest.py`

### Epic 6.6: Custom Pages & Views
- Register custom pages beyond CRUD (reports, charts, settings)
- Custom view decorators with admin navigation integration
- Embedded iframe/component support for external tools

**Files:** `views/custom.py`, `core/registry.py`, `templates/custom_page.html`

---

## Verification Strategy

Each phase has a clear verification approach:

| Phase | Verification |
|-------|-------------|
| 2.5 | `poe test` passes, E2E login→CRUD→logout, docs build, example runs |
| 3 | Zero-config demo works, file upload E2E, bulk action E2E, export CSV verified |
| 4 | axe-core 0 violations in E2E suite, dark mode toggle works, i18n renders correctly, mobile screenshots |
| 5 | Audit log populated after CRUD, row-level filter verified, OAuth login flow E2E, dashboard renders widgets |
| 6 | Benchmark suite runs in CI, WebSocket live update E2E, plugin loads from entry point, NL search returns results |

## Architecture Compliance

All phases follow CONSTITUTION.md:
- **Bottom-up ordering**: Models → Core logic → Adapters → Views → Templates (per planning-playbook.md)
- **Module boundaries**: New features get their own modules (`audit/`, `dashboard/`, `plugins/`, `realtime/`, `ai/`)
- **Dependency direction**: views/ → core/ → adapters/ (inward only)
- **Phase 3 domains**: `auth/`, `actions/`, `uploads/` only touched in their designated phase
- **TDD-first**: Every epic starts with failing tests
- **300 LOC guardrail**: Large modules split proactively

## Priority & Impact Matrix

| Epic | Impact | Effort | Priority |
|------|--------|--------|----------|
| Wire Auth E2E | High | Medium | P0 |
| Zero-Config Admin | **Critical** | Low | P0 |
| WCAG 2.1 AA | **Critical** (unique differentiator) | High | P0 |
| File Uploads | High | Medium | P1 |
| Dark Mode | High | Low | P1 |
| i18n | High | High | P1 |
| Custom Actions | High | Medium | P1 |
| Audit Log | High | Medium | P2 |
| Dashboard Builder | High | High | P2 |
| Plugin System | Medium | High | P2 |
| Real-Time | Medium | High | P3 |
| AI Features | Medium | High | P3 |
| SSO/OAuth | Medium | Medium | P2 |
| Additional ORMs | Medium | Medium | P3 |

---

## The Vision

> **HyperAdmin: The admin your FastAPI app deserves.**
>
> 3 lines to start. WCAG 2.1 AA accessible. Async-first.
> Type-safe. Real-time. AI-ready. Plugin-extensible.
> The last admin framework you'll ever need.
