# HyperAdmin: The Definitive Python Admin Framework Roadmap

## Context

HyperAdmin is a Pydantic-native, async-first admin interface for FastAPI powered by HTMX. Phase 2 is complete with full CRUD, dynamic forms (12+ widgets), FK/M2M relationships, custom actions, fieldsets, filtering, sorting, search, pagination, WCAG 2.1 AA accessibility, and theming. The goal: transform HyperAdmin into **the best, fastest, and most accessible Python auto-generated admin panel** — the framework developers choose *over* Django Admin, SQLAdmin, and Flask-Admin.

**Competitors to beat:**
| Feature | Django Admin | SQLAdmin | Flask-Admin | HyperAdmin (today) |
|---------|-------------|----------|-------------|-------------------|
| Async | No | Partial | No | **Full** |
| Pydantic-native | No | Minimal | No | **Yes** |
| Zero-config | Moderate | Good | Moderate | Good |
| i18n | Excellent | None | Some | None |
| Accessibility | Basic | Basic | Basic | **WCAG 2.1 AA** |
| Plugin ecosystem | Mature | None | Moderate | None |
| Real-time | No | No | No | No |

**Key differentiators to pursue:** Zero-config setup (3 lines), async-first performance (<100ms TTFB), WCAG 2.1 AA accessibility, type-safe developer experience, real-time capabilities, AI-ready features.

---

## v0.2.0 — "Ship It"
**Theme: Complete the foundation, make it installable and usable by real developers**
**Milestone: Phase 2: Core Feature Parity (CLOSED) + v0.2.1**

### Epic 2.5.1: Wire Authentication End-to-End
Auth models exist but aren't fully connected to endpoints.
- Wire `AuthenticationMiddleware` to all admin routes
- Complete session-based login/logout flow with tests
- Wire `PermissionChecker` to view-level enforcement (403 on denied)
- `createsuperuser` CLI command verified working
- E2E test: login -> CRUD -> logout flow

**Status:** Partial — Phase 1 auth epic (#77) closed, E2E wiring still needed
**Files:** `auth/middleware.py`, `auth/views.py`, `auth/session.py`, `auth/permissions.py`, `core/app.py`

### Epic 2.5.2: Configurable Search
~~Search is hardcoded to `name` and `email` fields.~~
- ~~Add `search_fields` to `ModelAdmin` / `AdminOptions`~~
- ~~Adapter: build dynamic search across configured fields~~
- ~~Support partial match (ILIKE) and exact match modes~~

**Status: DONE** — `search_fields` implemented in `AdminOptions`, adapter supports dynamic ILIKE search.

### Epic 2.5.3: Documentation & Examples
- Complete "Getting Started" tutorial (install -> 3-line admin -> customize)
- API reference for `Admin`, `ModelAdmin`, `AdminOptions`, `BaseAdapter`
- Finalize ERP example as a complete runnable demo
- Add screenshot/GIF to README

**Status:** In progress under **v0.2.1 — Developer Experience & Examples** milestone (#172, #192–#196)
**Files:** `docs/`, `examples/`, `README.md`

### Epic 2.5.4: Polish & Bug Fixes
- ~~Form validation error display (field-level + non-field errors)~~
- ~~Confirmation dialogs for delete actions~~
- Flash messages / toast notifications for success/error feedback
- Mobile-responsive sidebar (hamburger menu)

**Status:** Partial — validation errors and delete confirmation done. Flash messages and responsive sidebar remain.
**Files:** `templates/components/`, `templates/widgets/`, `static/hyperadmin.css`

---

## v0.3.0 — "Developer Love"
**Theme: Make developers productive in minutes, not hours**
**Milestone: v0.3.0 — Zero-Config & Auth**

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

**Status:** Not started
**Files:** `discover.py`, `core/registry.py`, `core/model.py`, `core/options.py`

### Epic 3.2: File Upload System
- `uploads/` module: `FileField`, `ImageField` support in forms
- Storage backends: local filesystem + S3-compatible (via protocol)
- Image preview widget with drag-and-drop
- Thumbnail generation for image fields (Pillow already a dependency)

**Status:** Not started
**Milestone: v0.3.1 — File Uploads**
**Files:** `uploads/storage.py`, `uploads/fields.py`, `views/forms.py`, `templates/widgets/file_input.html`

### Epic 3.3: Custom Model Actions
- ~~`actions/` module: register custom actions per model~~
- ~~Bulk actions on list view (select rows -> action dropdown)~~
- ~~Single-object actions on detail view~~
- ~~Built-in actions: export selected, delete selected~~
- ~~Action confirmation dialogs via HTMX~~

**Status: DONE** — `ActionDef`, `@action` decorator, POST endpoint, E2E tests all complete (#41, #184–#187 closed).

### Epic 3.4: Export / Import
- CSV and JSON export from list view (respects current filters)
- CSV/JSON import with validation preview
- Background processing for large datasets (async task)

**Status:** Not started
**Files:** `actions/export.py`, `actions/import_data.py`, `templates/components/export_bar.html`

### Epic 3.5: Advanced Filtering
- Date range filters
- Numeric range filters (min/max)
- Multi-value select filters
- "Save filter" presets per user
- Filter builder UI (AND/OR conditions)

**Status:** Not started
**Files:** `core/filters.py`, `views/dynamic.py`, `templates/components/filter_bar.html`

---

## v0.4.0 — "Accessible & Beautiful"
**Theme: WCAG 2.1 AA compliance + modern design system — become THE most accessible admin**
**Milestone: v0.4.0 — i18n & Responsive**

### Epic 4.1: WCAG 2.1 AA Accessibility Audit & Fix
No Python admin panel currently claims WCAG compliance — this is a unique differentiator.
- ~~Full keyboard navigation (Tab, Enter, Escape, Arrow keys)~~
- ~~Skip-to-content links~~
- ~~Focus management on HTMX swaps (focus trap in modals, restore after swap)~~
- ~~`aria-live` regions for all dynamic content updates~~
- ~~Color contrast ratios >= 4.5:1 for text, >= 3:1 for large text~~
- ~~Form error announcements for screen readers~~
- ~~Automated a11y testing with axe-core in Playwright E2E suite~~

**Status: DONE** — #72 closed. WCAG 2.1 AA improvements shipped.

### Epic 4.2: Theme System & Dark Mode
- ~~CSS custom properties (variables) for all colors, spacing, typography~~
- ~~Light/dark mode toggle with system preference detection~~
- ~~`prefers-reduced-motion` support~~
- ~~Theme configuration via `Admin(theme="dark")` or `Admin(theme=CustomTheme(...))`~~
- ~~High-contrast mode for accessibility~~

**Status: DONE** — #73 closed. Theme system with dark mode shipped.

### Epic 4.3: Responsive Design Overhaul
- Mobile-first responsive grid system
- Collapsible sidebar with swipe gestures (Alpine.js)
- Responsive data tables (card layout on small screens)
- Touch-friendly action buttons and form controls

**Status:** Not started
**Files:** `static/hyperadmin.css`, `templates/components/`, `templates/base.html`

### Epic 4.4: Internationalization (i18n)
Django Admin's i18n is excellent — match and exceed it.
- Translation system using Python `gettext` or lightweight alternative
- Extract all UI strings to message catalogs
- Ship with English, Spanish, French, German, Chinese, Japanese, Ukrainian
- RTL layout support (Arabic, Hebrew)
- `Admin(locale="uk")` configuration
- Community contribution workflow for new translations

**Status:** Not started
**Files:** `core/i18n.py`, `locale/`, all templates (wrap strings in `_()`)

---

## v0.5.0 — "Enterprise Ready"
**Theme: Features that make HyperAdmin viable for production enterprise apps**

### Epic 5.1: Audit / Activity Log
- Track all CRUD operations (who, what, when, old/new values)
- `AuditLog` model with JSON diff storage
- Audit trail view per object (timeline UI)
- Configurable: enable/disable per model via `AdminOptions`

**Status:** Not started
**Milestone: v0.5.1 — Audit & Row-Level Security**
**Files:** `audit/models.py`, `audit/middleware.py`, `adapters/sqlmodel.py`, `templates/components/audit_trail.html`

### Epic 5.2: Row-Level Security & Multi-Tenancy
- Object-level permissions (e.g., "user can only see their own records")
- `get_queryset(request)` hook on `ModelAdmin` for dynamic filtering
- Tenant-aware adapter filtering (multi-tenant SaaS support)
- Permission predicates: `has_object_permission(request, obj, action)`

**Status:** Not started
**Milestone: v0.5.1 — Audit & Row-Level Security**
**Files:** `auth/permissions.py`, `core/model.py`, `adapters/sqlmodel.py`

### Epic 5.3: SSO & OAuth2 Authentication
- OAuth2 / OpenID Connect backend (Google, GitHub, Azure AD)
- SAML2 backend for enterprise SSO
- Pluggable auth backend protocol (already exists, extend it)
- MFA support (TOTP via `pyotp`)

**Status:** Not started
**Milestone: v0.5.2 — SSO & Dashboard**
**Files:** `auth/oauth.py`, `auth/saml.py`, `auth/mfa.py`, `auth/backend.py`

### Epic 5.4: Dashboard Builder
- Customizable admin dashboard with widget cards
- Built-in widgets: count, chart (bar/line/pie), recent items, quick actions
- Per-user dashboard layout (drag & drop via HTMX + SortableJS)
- Widget protocol for custom dashboard widgets
- Data aggregation helpers in adapters

**Status:** Not started
**Milestone: v0.5.2 — SSO & Dashboard**
**Files:** `dashboard/widgets.py`, `dashboard/layout.py`, `templates/dashboard.html`, `views/dashboard.py`

### Epic 5.5: Inline Editing & Related Object Management
- Inline formsets for related objects (edit child objects on parent form)
- Inline table editing (click cell -> edit in place -> save via HTMX)
- Nested relationship creation (create related object from FK dropdown)

**Status:** Not started — #68 (inline models) open under v0.2.1
**Files:** `views/forms.py`, `views/dynamic.py`, `templates/components/inline_formset.html`

### Epic: UI/UX Polish
- ~~Improve the visual design of the admin interface~~
- ~~Add support for themes~~
- ~~Improve the accessibility of the admin interface~~
- Remaining polish items (Epic 2.4, #45)

**Status:** Mostly done — #72, #73, #74 closed. #45 open for remaining polish.
**Milestone: v0.5.0 — Advanced UX**

---

## v0.6.0 — "Real-Time Layer"
**Theme: WebSocket infrastructure and live CRUD notifications**
**Milestone: v0.6.0 — Real-Time Layer (23 issues)**

### Epic 6.2.1: WebSocket Infrastructure & PubSub Backends (#330)
- WebSocket endpoint and connection manager
- PubSub protocol with InMemory and Redis backends
- Channel-based message routing

### Epic 6.2.2: Real-Time Notifications (#331)
- CRUD event broadcasting via HTMX `hx-ws`
- Live updates: new/updated/deleted rows appear without refresh
- Real-time dashboard widgets

### Epic 6.2.3: Optimistic Concurrency Control (#332)
- Version-based conflict detection
- Conflict resolution dialog

**Status:** Not started — 23 issues planned, 0 closed

---

## v0.6.1 — "Presence"
**Theme: Who is viewing/editing which record**
**Milestone: v0.6.1 — Presence (9 issues)**

### Epic 6.2.4: Presence Tracking (#333)
- InMemoryPresence + RedisPresence backends
- Heartbeat-based with TTL expiry
- Banner on edit forms showing other editors
- Collaborative editing indicators

**Status:** Not started — 9 issues planned, 0 closed

---

## v0.7.0 — "High-Volume & High-Load Scalability"
**Theme: Make HyperAdmin work with 10M+ records and 100 req/s**
**Milestone: v0.7.0 — High-Volume & High-Load Scalability (34 issues)**

### Epic: Adapter Query Performance (#211)
- `selectinload` optimization, cursor-based pagination, count estimation, full-text search

### Epic: Engine & Connection Management (#212)
- Pool tuning, rate limiting, connection lifecycle

### Epic: Filter & Choice Scalability (#213)
- FK preload threshold, filter cache, lazy loading

### Epic: E2E Scalability Validation & Documentation (#214)
- Benchmark suite, performance regression CI, documentation

**Status:** Not started — 34 issues planned, 0 closed

---

## v0.7.1 — "Load Testing & Synthetic Data"
**Theme: Prove scalability with real benchmarks**
**Milestone: v0.7.1 — Load Testing & Synthetic Data (20 issues)**

### Epic: Synthetic Data Generator (#246)
- Faker + SQLAlchemy Core bulk inserts for 10M+ records

### Epic: Locust Load Testing Suite (#247)
- 100 req/s target against 10M+ records

**Status:** Not started — 20 issues planned, 0 closed

---

## v0.8.0 — "The Future"
**Theme: AI-powered, extensible — the admin panel of 2027**
**Milestone: v0.8.0 — Plugins & AI**

### Epic 6.1: Plugin & Extension System
- Formal plugin registry with entry points (`hyperadmin.plugins`)
- Plugin hooks: `on_model_register`, `on_before_create`, `on_after_delete`, etc.
- Plugin marketplace/directory (docs site)
- Plugin template: scaffold a new plugin with `hyperadmin create-plugin`

**Status:** Not started
**Files:** `plugins/registry.py`, `plugins/hooks.py`, `core/app.py`

### Epic 6.3: AI-Powered Features
- Natural language search ("show me orders over $1000 from last month")
- AI-assisted data entry (auto-fill fields from context)
- Smart suggestions for filter combinations
- Anomaly detection highlights on dashboards
- Optional — requires LLM API key, degrades gracefully without

**Status:** Not started
**Files:** `ai/search.py`, `ai/suggestions.py`, `core/options.py`

### Epic 6.5: Additional ORM Adapters
- Tortoise ORM adapter
- Piccolo ORM adapter
- MongoDB adapter (via Motor/Beanie)
- Generic REST API adapter (connect to any API as data source)

**Status:** Not started
**Files:** `adapters/tortoise.py`, `adapters/piccolo.py`, `adapters/mongodb.py`, `adapters/rest.py`

### Epic 6.6: Custom Pages & Views
- Register custom pages beyond CRUD (reports, charts, settings)
- Custom view decorators with admin navigation integration
- Embedded iframe/component support for external tools

**Status:** Not started
**Files:** `views/custom.py`, `core/registry.py`, `templates/custom_page.html`

---

## JSON RESTful API (TBD)
**Theme: Machine-readable RESTful JSON API for all registered models**
**Milestone: JSON RESTful API (TBD) — may not ship**

### Epic: JSON RESTful API for HyperAdmin (#76)
- `JsonApiAdapter` protocol and response envelope schema (done: #197 merged)
- `JsonApiRouter` generating 5 CRUD endpoints per registered model
- Auth integration for JSON API (session + optional bearer token)
- Integration tests with permission checks
- Usage guide with curl examples

**Status:** Protocol layer done, router and auth not started — 7 issues, 0 closed

---

## Verification Strategy

Each phase has a clear verification approach:

| Phase | Verification |
|-------|-------------|
| v0.2.x | `poe test` passes, E2E login->CRUD->logout, docs build, example runs |
| v0.3.x | Zero-config demo works, file upload E2E, export CSV verified |
| v0.4.x | axe-core 0 violations, i18n renders correctly, mobile screenshots |
| v0.5.x | Audit log populated after CRUD, row-level filter verified, OAuth login flow E2E, dashboard renders widgets |
| v0.6.x | WebSocket live update E2E, presence banner E2E |
| v0.7.x | Benchmark suite runs in CI, 10M rows <100ms TTFB, 100 req/s sustained |
| v0.8.x | Plugin loads from entry point, NL search returns results |

## Architecture Compliance

All phases follow CONSTITUTION.md:
- **Bottom-up ordering**: Models -> Core logic -> Adapters -> Views -> Templates (per planning-playbook.md)
- **Module boundaries**: New features get their own modules (`audit/`, `dashboard/`, `plugins/`, `realtime/`, `ai/`)
- **Dependency direction**: views/ -> core/ -> adapters/ (inward only)
- **TDD-first**: Every epic starts with failing tests
- **300 LOC guardrail**: Large modules split proactively

## Priority & Impact Matrix

| Epic | Impact | Effort | Priority | Status |
|------|--------|--------|----------|--------|
| Wire Auth E2E | High | Medium | P0 | Partial |
| Zero-Config Admin | **Critical** | Low | P0 | Not started |
| WCAG 2.1 AA | **Critical** | High | P0 | **DONE** |
| File Uploads | High | Medium | P1 | Not started |
| Dark Mode | High | Low | P1 | **DONE** |
| i18n | High | High | P1 | Not started |
| Custom Actions | High | Medium | P1 | **DONE** |
| Audit Log | High | Medium | P2 | Not started |
| Dashboard Builder | High | High | P2 | Not started |
| Plugin System | Medium | High | P2 | Not started |
| SSO/OAuth | Medium | Medium | P2 | Not started |
| Real-Time | Medium | High | P3 | Not started (23 issues planned) |
| Presence | Medium | Medium | P3 | Not started (9 issues planned) |
| Scalability | High | High | P3 | Not started (34 issues planned) |
| Load Testing | Medium | Medium | P3 | Not started (20 issues planned) |
| AI Features | Medium | High | P3 | Not started |
| Additional ORMs | Medium | Medium | P3 | Not started |
| JSON REST API | Medium | Medium | TBD | Partial (protocol done) |

---

## The Vision

> **HyperAdmin: The admin your FastAPI app deserves.**
>
> 3 lines to start. WCAG 2.1 AA accessible. Async-first.
> Type-safe. Real-time. AI-ready. Plugin-extensible.
> The last admin framework you'll ever need.
