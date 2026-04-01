# Roadmap

HyperAdmin is a Pydantic-native, async-first admin interface for FastAPI powered by HTMX. This roadmap outlines what has shipped and what is coming next.

---

## What's shipped

### v0.2.0 — Foundation

- Full CRUD operations (list, detail, create, update, delete)
- Dynamic forms with 12+ widgets (text, number, select, checkbox, datetime, textarea, and more)
- Foreign key and many-to-many relationship support
- Configurable search across model fields
- Sorting, filtering, and pagination
- Form validation with field-level error display
- Delete confirmation dialogs
- WCAG 2.1 AA accessibility (keyboard navigation, skip-to-content, ARIA live regions, focus management, color contrast)
- Theme system with light/dark mode toggle and system preference detection
- `prefers-reduced-motion` support and high-contrast mode
- Custom model actions with bulk and single-object support

---

## Coming next

### v0.3.0 — Developer Love

**Theme: Make developers productive in minutes, not hours**

#### Zero-Config Admin (3 Lines of Code)

The killer feature — beat every competitor on setup speed:

```python
from hyperadmin import Admin
admin = Admin(app, engine=engine)
admin.mount("/admin")  # auto-discovers all SQLModel models
```

- Auto-register all SQLModel/SQLAlchemy models without explicit `admin.py`
- Smart defaults: infer `list_display`, `search_fields`, `list_filter` from model fields
- Convention-over-configuration: sensible defaults that work 90% of the time

#### File Upload System

- `FileField`, `ImageField` support in forms
- Storage backends: local filesystem + S3-compatible
- Image preview widget with drag-and-drop
- Thumbnail generation for image fields

#### Export / Import

- CSV and JSON export from list view (respects current filters)
- CSV/JSON import with validation preview
- Background processing for large datasets

#### Advanced Filtering

- Date range and numeric range filters
- Multi-value select filters
- Saved filter presets per user
- Filter builder UI (AND/OR conditions)

---

### v0.4.0 — Responsive Design

**Theme: Best-in-class mobile admin experience**

- Mobile-first CSS architecture with standardized breakpoints (sm/md/lg/xl)
- Collapsible sidebar with hamburger menu toggle (Alpine.js)
- Responsive data tables (stacked card layout on mobile)
- Touch-friendly forms, pagination, and filter controls
- Responsive navbar optimizations
- Comprehensive E2E viewport tests

**Spec:** [`docs/specs/responsive-design.md`](specs/responsive-design.md)

---

### v0.4.1 — i18n

**Theme: Full internationalization support**

- Translation system using Python `gettext` + Babel + Jinja2 i18n extension
- Pluggable `TranslationProvider` protocol with gettext default
- Ship with 7 locales: English, Spanish, French, German, Chinese, Japanese, Ukrainian
- Locale middleware (cookie → settings → Accept-Language → fallback)
- CSS logical properties for RTL readiness
- Locale switcher UI

**Proposal:** [`docs/agentic-workflow/issue-proposals/v0.4.1-i18n.md`](agentic-workflow/issue-proposals/v0.4.1-i18n.md)

---

### v0.5.0 — Enterprise Ready

**Theme: Features that make HyperAdmin viable for production enterprise apps**

#### Audit / Activity Log

- Track all CRUD operations (who, what, when, old/new values)
- Audit trail view per object (timeline UI)
- Configurable per model via `AdminOptions`

#### Row-Level Security & Multi-Tenancy

- Object-level permissions (e.g., "user can only see their own records")
- `get_queryset(request)` hook for dynamic filtering
- Tenant-aware adapter filtering

#### SSO & OAuth2 Authentication

- OAuth2 / OpenID Connect backend (Google, GitHub, Azure AD)
- SAML2 backend for enterprise SSO
- MFA support (TOTP)

#### Dashboard Builder

- Customizable admin dashboard with widget cards
- Built-in widgets: count, chart, recent items, quick actions
- Per-user dashboard layout (drag & drop)
- Widget protocol for custom dashboard widgets

#### Inline Editing

- Inline formsets for related objects
- Inline table editing (click cell -> edit in place)
- Nested relationship creation from FK dropdown

---

### v0.6.0 — Real-Time Layer

**Theme: WebSocket infrastructure and live CRUD notifications**

- WebSocket endpoint and connection manager with PubSub backends (InMemory, Redis)
- CRUD event broadcasting via HTMX `hx-ws`
- Live updates: new/updated/deleted rows appear without refresh
- Optimistic concurrency control with conflict resolution

### v0.6.1 — Presence

- Presence tracking with heartbeat-based TTL
- Banner on edit forms showing other editors

---

### v0.7.0 — Scalability

**Theme: Make HyperAdmin work with 10M+ records and 100 req/s**

- Adapter query performance (`selectinload`, cursor-based pagination, count estimation)
- Connection pool tuning and rate limiting
- FK preload thresholds and filter caching
- Benchmark suite and performance regression CI

---

### v0.8.0 — The Future

**Theme: AI-powered, extensible**

#### Plugin & Extension System

- Formal plugin registry with entry points (`hyperadmin.plugins`)
- Plugin hooks: `on_model_register`, `on_before_create`, `on_after_delete`, etc.
- Plugin scaffold command: `hyperadmin create-plugin`

#### AI-Powered Features

- Natural language search ("show me orders over $1000 from last month")
- AI-assisted data entry (auto-fill fields from context)
- Smart suggestions for filter combinations

#### Additional ORM Adapters

- Tortoise ORM, Piccolo ORM, MongoDB (via Motor/Beanie)
- Generic REST API adapter (connect to any API as data source)

#### Custom Pages & Views

- Register custom pages beyond CRUD (reports, charts, settings)
- Custom view decorators with admin navigation integration
