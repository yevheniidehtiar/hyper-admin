# Roadmap

## Strategy

**HyperAdmin is the admin you add to an existing FastAPI app in 10 minutes without it
taking over** — your models, your UUID keys, your migrations, your auth. Then
Django-admin parity plus enterprise features. HTMX-only, no JS build. Every feature
proven on real apps.

Milestones are ordered by **adoption value**: whatever stops a team from putting
HyperAdmin on a real, existing application comes first. The 2026-09-28 re-cut kept
every item from the previous roadmap and only changed the order. Version numbers are
identifiers, not release order.

The source of truth is `.meta/roadmap/roadmap.yaml` in the repository (GitPM); epics
and stories live under `.meta/epics/`.

---

## What's shipped

### Foundation (Phase 1 / Phase 2)

- Full CRUD (list, detail, create, update, delete) with dynamic Pydantic forms and 12+ widgets
- FK / M2M relations, select & multiselect widgets, dependent (cascading) selects
- Search, sorting, filtering, pagination; fieldsets; inline formsets; custom actions
- Light/dark themes, WCAG 2.1 AA accessibility

### v0.2.1 — Developer Experience & Examples

- Bookkeeping ERP reference app, examples restructure, onboarding docs

### v0.3.0 — Zero-Config & Auth

- Auto-discovery of models with smart defaults (`list_display`, `search_fields`, `list_filter`)
- `HyperAdminSettings` (pydantic-settings), session authentication end-to-end

### v0.3.1 — File Uploads

- `StorageBackend` protocol, file / image fields, upload and delete endpoints, validation

### v0.4.0 — Responsive Design

- Mobile-first layout, collapsible sidebar, stacked-card tables, touch-friendly forms

### v0.4.1 — i18n

- gettext + Babel, RTL layouts, locale switcher; expanded to the top-20 locales

### v0.5.0 — Advanced UX

- UI polish, dark mode, inline cell editing in list view

### v0.5.1 — Object Permissions & MFA

- `ObjectPermissionChecker`, `get_queryset` row-level security, email-OTP MFA

### Landed ahead of their milestones

- H2 inline formset row-level error highlighting (v0.5.5)
- `@action` bulk/form parameters and the bulk-action endpoint with per-row outcomes (v0.5.5)
- `relation_filters` / `relation_display` options and the create-popup view (v0.5.5)
- SSE + WebSocket connection foundation with `ConnectionRegistry` (v0.6.0b)
- `JsonApiAdapter` / `ListEnvelope` protocol (JSON REST API)
- Synthetic data generator (`hyperadmin seed`) (v0.7.1)

---

## What's next, in order

### 1. v0.5.8 — Bring Your Own App (dogfood-1) · *new, top priority*

Make HyperAdmin a guest in someone else's app.

- **Your keys** — primary-key-agnostic routes: UUID, string and int PKs end-to-end
- **Your migrations** — no DDL against the host database unless explicitly requested
- **Your models / engine** — plain SQLAlchemy 2.0 `DeclarativeBase` models; reuse the host `AsyncEngine` / sessionmaker
- **Your auth** — bring-your-own-auth adapter mapping the host's user/session to admin permissions
- A "10-minute" guide and an example app with Alembic, UUID keys and its own auth
- **Dogfood-1:** the milestone closes only after the admin runs on a real existing app and blocking gaps are fixed

### 2. v0.5.5 — Bulk Actions & Autocomplete (finish)

- List-view checkbox column, action selector and run button
- `AutocompleteWidget` template with dependent filtering and inline "+" create
- Playwright suites for both

### 3. v0.7.0a — Scale Core

- Configurable `selectinload` (no N+1 on list/detail)
- Configurable `search_fields` in both adapters
- COUNT caching with TTL
- FK preload threshold and filter-metadata caching

### 4. v0.6.0a — Optimistic Concurrency Control

- Version column detection, `StaleRecordError`, hidden version field on update forms
- Conflict dialog when two people edit the same record

### 5. v0.5.2 — OAuth SSO

- OAuth2 / OIDC backend (Google, GitHub), provider configuration, token refresh
- Login buttons; composes with bring-your-own auth

### 6. v0.5.3 — Multi-Tenancy

- Tenant resolution middleware, `TenantAwareAdapter`, tenant options on `AdminOptions`

### 7. v0.5.6 — Detail Panels & Filter Library

- Tabbed detail panels with HTMX lazy-load and streaming (PDF) panels
- Date-range, multi-FK, multi-choice, boolean and owner filters; URL-shareable state; saved views

### 8. v0.5.7 — Permissions Matrix

- Model × action permission grid for groups/roles, object-permission column, audit logging
- `examples/full-demo/` umbrella app and qualification suite

### 9. v0.5.4 — Reporting & Charts

- `ReportView` with aggregates, crosstab and time bucketing; CSV / XLSX export
- SVG chart primitives and a Chart.js widget; dashboard widgets on top of `ReportView`

### 10. v0.3.2 — Advanced File Uploads

- S3-compatible backend configuration, Pillow thumbnails, EXIF auto-rotate
- Drag-and-drop preview widget, upload progress bar, error recovery with retry

### 11. v0.6.0b — Real-Time Pub/Sub & Live Notifications

- `PubSubBackend` (InMemory + Redis), `RealtimeEvent` emission from adapters
- Live list updates and toasts over HTMX

### 12. v0.6.1 — Presence

- Heartbeat-based presence (InMemory + Redis), "someone else is editing" banner

### 13. v0.7.0b — Scale Advanced

- Keyset (cursor) pagination
- Engine pool configuration and rate limiting
- E2E scalability validation and configuration guide
- Measured with **v0.7.1 — Load Testing & Synthetic Data** (Locust suite + seeder)

### 14. JSON REST API

- `JsonApiRouter` with CRUD endpoints per model, session / bearer auth, docs

### 15. v0.8.0 — Plugins & AI

- Plugin registry with lifecycle hooks; `hyperadmin-logfire` as the first official plugin
- AI-assisted features, more ORM adapters and custom pages afterwards

### 16. v1.0 — Stable Release

- Public API audit and freeze, semver and deprecation policy
- Migration guides from other Python admin frameworks
- Every feature proven on at least one real app
