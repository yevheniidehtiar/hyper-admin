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

### v0.5.5 — Bulk Actions & Autocomplete

- List-view checkbox column and action toolbar, bulk-action endpoint with a result for each row,
  `@action` bulk / form parameters
- Autocomplete widget with dependent filtering and create popup, `relation_filters` /
  `relation_display`, inline-row error highlighting

### v0.5.6 — Detail Panels & Filter Library

- `@panel` tabbed detail panels with lazy loading and a streamed PDF panel
- Six built-in filters, the filter sidebar and per-user saved views

### v0.5.7 — Permissions Matrix

- Model × action grid with conflict handling and an audit trail
- `examples/full-demo/` and its qualification suite

### v0.3.2 — Advanced File Uploads

- S3-compatible storage, thumbnails, EXIF auto-rotation, drag-and-drop preview, upload progress and retry

### v0.6.1 — Presence

- In-memory and Redis presence backends, WebSocket heartbeat and the "someone else is editing" banner

### v0.7.1 — Load Testing & Synthetic Data

- Synthetic data generator (`hyperadmin seed`) and Locust suite with baselines and a CI smoke run

### Landed ahead of their milestones

These features are merged on `develop`, but their milestones are still open: each one closes
when its remaining stories, demo or real-app proof are done.

- **Bring your own app (v0.5.8, 43 of 46 stories):** isolated sub-application mount; int, UUID and
  `str` primary keys; `session_factory=`; `ExternalAuth`; CSRF; no DDL by default; a guide and the
  `examples/byoa/` app. **Plain SQLAlchemy 2.0 / 2.1 models** work through a schema built from
  the mapper (`schema_for`), with an `examples/sqlalchemy/` app
- **Real-app proof (dogfood):** Polar, Langflow, Mealie and Open WebUI run unmodified and
  every model's pages render; see [Compatibility & Performance](compatibility.md)
- **Navigation & list UX (v0.5.9, 5 of 6 epic stories):** sidebar grouped by domain (`NavGroup`,
  `nav_group`, `nav_order`, icons), icon rail, per-user pinned pages, a <kbd>⌘K</kbd> command
  palette, clickable list rows, a red delete icon with a shared confirmation dialog, keyboard
  shortcuts with a `?` overlay, and an unsaved-changes warning with a sticky save bar; see
  [Navigation, Lists & Keyboard](guides/navigation.md). Left: opt-in record search in the palette
- **Reporting & charts (v0.5.4, dashboard builder left):** the `hyperadmin-reports` plugin with
  aggregates, crosstab and time bucketing, report pages, server-rendered SVG charts and
  CSV / XLSX export
- **Real-time (v0.6.0b):** `PubSubBackend` (in-memory and Redis), `RealtimeEvent`, CRUD events
  emitted through an adapter proxy, SSE and WebSocket transport. Left: toasts and live list
  updates in the list templates, and the two-session E2E test
- **Plugins (v0.8.0, v0.8.1):** plugin registry wired into `Admin` (pages, static files,
  templates, navigation, permissions, hooks); `hyperadmin-tasks` with a `TaskBackend` port,
  in-memory and experimental pgtask backends, and a monitoring UI (dashboard, tasks, workers,
  schedules). Left: in-process worker, transactional enqueue, example app and docs
- **ERP showcase UX:** number formatting, status pills with an overdue variant, phone card rows,
  page-size selector, invoice and bill filters with bulk Mark paid, and an ERP dashboard in the
  bookkeeping example
- **Scale core (v0.7.0a, partly):** first adapter query performance work, such as loading the
  current user without eager-loading groups and permissions
- `JsonApiAdapter` / `ListEnvelope` protocol (JSON REST API)

---

## What's next, in order

Percentages are stories done, from `./scripts/gitpm.sh status`.

### 1. Close the nearly done milestones

- **v0.5.8 Bring Your Own App (93%)** — the milestone closes only after the admin runs on a real
  existing app and the last blocking gaps are fixed
- **v0.5.9 Navigation & List UX (91%)** — opt-in record search in the command palette
- **v0.6.0b Real-Time (88%)** — live list updates and toasts over HTMX
- **v0.8.1 Tasks plugin (81%, due 2026-11-13)** — app integration: in-process worker,
  transactional enqueue, example app, docs

### 2. v0.7.0a — Scale Core (30%)

- Configurable `selectinload` (no N+1 on list/detail)
- Configurable `search_fields` in both adapters
- COUNT caching with TTL
- FK preload threshold and filter-metadata caching

### 3. v0.6.0a — Optimistic Concurrency Control (0%)

- Version column detection, `StaleRecordError`, hidden version field on update forms
- Conflict dialog when two people edit the same record

### 4. v0.5.2 — OAuth SSO (11%)

- OAuth2 / OIDC backend (Google, GitHub), provider configuration, token refresh
- Login buttons; composes with bring-your-own auth

### 5. v0.5.3 — Multi-Tenancy (0%)

- Tenant resolution middleware, `TenantAwareAdapter`, tenant options on `AdminOptions`

### 6. v0.5.4 — Dashboard Builder (0 of 10 stories)

- `DashboardWidget` protocol and built-in widgets on top of `ReportView`, dashboard view and
  template, drag-and-drop reordering

### 7. v0.7.0b — Scale Advanced (0%)

- Keyset (cursor) pagination
- Engine pool configuration and rate limiting
- E2E scalability validation and configuration guide
- Measured with the v0.7.1 Locust suite and seeder

### 8. JSON REST API (33%)

- `JsonApiRouter` with CRUD endpoints per model, session / bearer auth, docs

### 9. v0.8.0 — Plugins & AI (38%)

- Plugin registry lifecycle hooks (60%); `hyperadmin-logfire` as the first official plugin (9%)
- AI-assisted features, more ORM adapters and custom pages afterwards

### 10. v1.0 — Stable Release

- Public API audit and freeze, semver and deprecation policy
- Migration guides from other Python admin frameworks
- Every feature proven on at least one real app
