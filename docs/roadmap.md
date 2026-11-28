# Roadmap

HyperAdmin is the admin you add to an existing FastAPI app without it taking over: your
models, your keys, your migrations, your auth. This page says what 1.0 contains, what it
leaves out, and the gaps we know about. Release-by-release detail is in the
[Changelog](changelog.md); what may change after 1.0 is in
[Versioning & Deprecation](versioning.md).

## What 1.0 includes

**Fits into your app**

- SQLModel `table=True` models and plain SQLAlchemy 2.0 / 2.1 models (`DeclarativeBase` or
  legacy `declarative_base()`), with a schema built from the mapper
- An isolated sub-application mount: its own static files, route namespace and cookie
- `int`, UUID and natural `str` primary keys, your engine or `session_factory`, and no tables
  created unless you ask
- Your own auth through `ExternalAuth`, or the built-in session auth with users, groups,
  permissions and email-OTP MFA; optional Google / GitHub sign-in (`[oauth]` extra)
- Zero-config auto-discovery of SQLModel models with smart defaults
- Shown on real apps: Polar, Langflow, Mealie and Open WebUI run with their models unchanged
  ([Compatibility & Performance](compatibility.md))

**CRUD and data entry**

- List, detail, create, edit and delete, with search, sorting and pagination
- Fieldsets, form layouts, inline formsets and inline cell editing
- Foreign-key and many-to-many selects, async autocomplete, dependent selects and a create
  popup
- Bulk actions with a result per row, and `@action`s that take a form
- File and image uploads: local or S3-compatible storage (`[s3]` extra), thumbnails, EXIF
  rotation, drag-and-drop, progress and retry

**Navigation and finding data**

- A sidebar grouped by domain, with icons, an icon rail and per-user pinned pages
- A <kbd>⌘K</kbd> command palette, with opt-in record search
- Clickable rows, a delete confirmation dialog, keyboard shortcuts and an unsaved-changes guard
- A filter sidebar with built-in filters, per-user saved views and tabbed detail panels

**Security**

- CSRF protection that works behind a TLS proxy, and sensitive fields hidden by default
- Object permissions and row scoping through `get_queryset`, and a permissions matrix with an
  audit trail
- Optimistic concurrency: a stale save gets a conflict dialog (`enforce_occ`)
- Rate limits for the admin and its login

**Collaboration**

- Live CRUD notifications over SSE or WebSocket, with in-memory or Redis pub/sub
  (`[realtime]`, `[redis]` extras)
- Presence: who else is editing a record

**Large tables**

- Relations loaded only for the columns shown, cursor pagination, cached and estimated
  totals, lazy foreign-key options, cached filter metadata and connection-pool settings
- A synthetic data generator (`hyperadmin seed`) and a Locust load-test suite

**Interface**

- Two theme presets (`terminal` by default, `classic`), each in light and dark
- A responsive layout for phones, WCAG 2.1 AA
- 20 locale catalogs with right-to-left layout for Arabic and Hebrew

**Plugins**

- A plugin registry for pages, navigation, templates, static files, permissions and the home
  page, with lifecycle hooks that observe CRUD, adapter calls, validation errors and sign-in
  events ([Hook Reference](plugins/hooks.md))
- First-party plugins, installed from the repository for now:
  [`hyperadmin-reports`](plugins/reports.md) (crosstab reports, SVG charts, CSV / XLSX
  export, a home-page dashboard), [`hyperadmin-tasks`](plugins/tasks.md) (background task
  dashboard on pgtask, experimental) and [`hyperadmin-logfire`](plugins/logfire.md)
  (request, adapter and SQL spans)

**For teams moving over**

- [Migration guides](migration/index.md) from Django admin, SQLAdmin and Flask-Admin
- [Claude Code skills and agents](guides/ai-skills.md) for setup and migration

## Not in 1.0

Dropped from the plan:

- **A JSON REST API.** The `JsonApiAdapter`, `ListEnvelope` and `PaginationMeta` protocol
  types stay, but there is no JSON router.
- **Multi-tenancy.** Scope rows per tenant with `ModelAdmin.get_queryset`.

Not built, and not scheduled:

- A change history for records (who changed what, with field diffs)
- More ORM backends (Tortoise, Piccolo, MongoDB)
- AI-assisted admin features
- PyPI releases of the three plugins

## Known gaps

These are the limits that 1.0 ships with:

- **Forms.** `AdminOptions` has no per-field widget, label, help text or read-only option, so
  forms follow the model. There is no SQLModel many-to-many form field, and a JSON `dict`
  column has no form input.
- **Theming.** There is no setting for an extra stylesheet or a `<head>` block; override a
  template to add one.
- **Translations.** Host apps cannot add their own translation catalogs. English is the source
  language; of the other 19 catalogs, Ukrainian is mostly reviewed and German in part, and the
  other 17 are machine drafts
  marked fuzzy, which show English until a native speaker reviews them
  ([Languages & RTL](guides/i18n.md)).
- **Databases.** CI runs on SQLite; PostgreSQL is covered by the load tests and real-app runs.
  MySQL is not verified.
- **Docs.** There is no guide for email-OTP MFA; the `otp_service` argument is listed in the
  [Application reference](api/application.md#parameters).
- **Real-app runs** found smaller gaps that are still open, such as auto-discovery of plain
  SQLAlchemy models and `hybrid_property` columns; see
  [known limitations](compatibility.md#known-limitations).

## Suggest a change

Open an issue on
[GitHub](https://github.com/yevheniidehtiar/hyper-admin/issues). A proposal is easier to
weigh when it names the app that needs it.
