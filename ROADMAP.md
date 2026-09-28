# HyperAdmin Product Roadmap

> **Thesis:** HyperAdmin is the admin you add to an existing FastAPI app in 10 minutes
> without it taking over — your models, your UUID keys, your migrations, your auth.
> Then Django-admin parity plus enterprise features. HTMX-only, no JS build. Every
> feature proven on real apps.

The roadmap is ordered by **adoption value**: what unblocks a team from putting
HyperAdmin on a real app comes first. Nothing from the previous roadmap was cut —
it was only re-ordered (re-cut 2026-09-28). The source of truth is
[`.meta/roadmap/roadmap.yaml`](.meta/roadmap/roadmap.yaml); the detailed view with
per-milestone scope lives in [`docs/roadmap.md`](docs/roadmap.md).

---

## Shipped

| Milestone | Highlights |
|-----------|-----------|
| Phase 1 / Phase 2 | CRUD, list/filter/search/sort, fieldsets, inlines, actions, select & multiselect widgets, themes, WCAG 2.1 AA |
| v0.2.1 — Developer Experience | Bookkeeping ERP reference app, examples refactor |
| v0.3.0 — Zero-Config & Auth | 3-line auto-discovery with smart defaults, `HyperAdminSettings`, session auth end-to-end |
| v0.3.1 — File Uploads | `StorageBackend`, file/image fields, upload/delete endpoints |
| v0.4.0 — Responsive Design | Mobile-first layout, collapsible sidebar, stacked-card tables |
| v0.4.1 — i18n | gettext + Babel, RTL, locale switcher (now top-20 locales) |
| v0.5.0 — Advanced UX | UI polish, dark mode, inline cell editing |
| v0.5.1 — Object Permissions & MFA | `ObjectPermissionChecker`, `get_queryset` row-level security, email-OTP MFA |

Also on `develop` ahead of their milestones: H2 inline row-error highlighting,
bulk-action endpoint and `@action` bulk/form params, relation config + create-popup
view, SSE/WebSocket connection foundation, `JsonApiAdapter` protocol, synthetic
data generator.

---

## Next, in order

| # | Milestone | Why here |
|---|-----------|----------|
| 1 | **v0.5.8 — Bring Your Own App (dogfood-1)** — *new, top priority* | Mount into an existing app: PK-agnostic routes (UUID/str), no DDL on the host DB, plain SQLAlchemy `DeclarativeBase` + host engine reuse, bring-your-own auth, 10-minute guide. Closes only after running on a real app. |
| 2 | v0.5.5 — Bulk Actions & Autocomplete (finish) | Half-merged; finish the list-view bulk toolbar and `AutocompleteWidget`. |
| 3 | v0.7.0a — Scale Core | N+1-free relation loading, configurable `search_fields` in both adapters, COUNT cache, FK preload threshold + filter cache. |
| 4 | v0.6.0a — Optimistic Concurrency Control | Lost-update protection for live apps; no dependency on pub/sub. |
| 5 | v0.5.2 — OAuth SSO | Google / GitHub OIDC, composing with (not replacing) host auth. |
| 6 | v0.5.3 — Multi-Tenancy | Tenant middleware + `TenantAwareAdapter` on the shipped `get_queryset` hook. |
| 7 | v0.5.6 — Detail Panels & Filter Library | Tabbed detail panels; date-range / multi-FK / boolean filters, saved views. |
| 8 | v0.5.7 — Permissions Matrix | Model × action grid editor, `examples/full-demo/` qualification suite. |
| 9 | v0.5.4 — Reporting & Charts | `ReportView` aggregates/crosstab, CSV/XLSX export, SVG + Chart.js widgets, dashboard layer. |
| 10 | v0.3.2 — Advanced File Uploads | S3 config, thumbnails + EXIF, drag-and-drop, progress + retry. |
| 11 | v0.6.0b — Real-Time Pub/Sub | InMemory/Redis pub/sub, live CRUD notifications over HTMX. |
| 12 | v0.6.1 — Presence | Who is viewing / editing a record. |
| 13 | v0.7.0b — Scale Advanced | Keyset pagination, pool tuning + rate limiting, E2E scalability suite (measured by v0.7.1 Locust + synthetic data). |
| 14 | JSON REST API | `JsonApiRouter`, auth, docs on top of the shipped protocol. |
| 15 | v0.8.0 — Plugins & AI | Plugin registry + lifecycle hooks, `hyperadmin-logfire`, AI-assisted features. |
| 16 | v1.0 — Stable Release | API freeze, semver + deprecation policy, migration guides. |

Version numbers are identifiers, not release order — milestones ship in the order above.
