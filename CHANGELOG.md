# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/),
and this project adheres to [Semantic Versioning](https://semver.org/).
Version numbers follow [PEP 440](https://peps.python.org/pep-0440/) (for example
`0.5.0a1`); while the major version is `0`, breaking changes bump the minor version.

## [Unreleased]

### Added
- **Plain SQLAlchemy models** (#719, #725–#730). Models built on SQLAlchemy 2.0
  `DeclarativeBase` or the legacy `declarative_base()` register with
  `site.register(Model)`, with no SQLModel base class. HyperAdmin builds a Pydantic schema
  from the mapper (`hyperadmin.core.schema_for` / `dump_instance`), and every view reads
  fields through it. New `examples/sqlalchemy/` app with a Playwright smoke test.
  Auto-discovery still finds SQLModel models only (#716).
- **Compatibility & Performance docs page** (`docs/compatibility.md`): supported stacks,
  results of running HyperAdmin unmodified on Polar, Langflow, Mealie and Open WebUI
  (epic #701), timings on 237,757 rows, and known limitations.
- **Live CRUD notifications through an adapter proxy and shared pub/sub** (#311).
- **Presence**: `PresenceBackend` with in-memory and Redis implementations, WebSocket
  heartbeat and the "someone else is editing" banner (#323–#328).
- **Detail panels and filter library** (v0.5.6): `PanelDef` / `@panel` tabbed panels with lazy
  loading and `pdf_stream_panel`; the `hyperadmin.filters` package with six built-in filters,
  the filter sidebar and per-user saved views.
- **Permissions matrix** (v0.5.7): model × action grid for each group, conflict handling,
  audit trail, object-permission popover; `examples/full-demo/` with a qualification suite.
- **Reports plugin** (v0.5.4): `hyperadmin-reports` with aggregates, crosstab, time bucketing,
  report pages, server-rendered SVG charts and CSV / XLSX streaming exports.
- **Advanced uploads** (v0.3.2): S3-compatible storage (`[s3]` extra), image metadata, EXIF
  auto-rotation, cached thumbnails in preview, list and detail views, drag-and-drop, upload
  progress and retry.
- **Bulk-action toolbar and autocomplete widget** in the list and form views (v0.5.5).
- **Plugin registry** wired into `Admin` (pages, static files, templates, navigation,
  permissions, hooks; `disabled_plugins=` / `plugin_settings=`), and the `hyperadmin-tasks`
  plugin scaffold (`TaskBackend` port, `InMemoryTaskBackend`, `TasksSettings`).
- **Design system Wave 1 building blocks** (`docs/design/system/components/`):
  Menu, Combobox (async, single and multiple), Progress, Banner and Popover
  / Tooltip, each with guidelines, every state in a live preview (light,
  dark, RTL) and reference CSS in `components/bundle.css`. New
  `--ha-z-popover` layer token and ten Lucide icons (`ellipsis`, `download`,
  `upload`, `copy`, `mail`, `refresh-cw`, `clock`, `circle-help`,
  `columns-3`, `sparkles`) available through `icon(name)`.
- **Design system Wave 2 flow designs** (v0.5.4 – v0.5.7): BulkActionFlow,
  AutocompleteStates, ReportPage with the CrosstabTable, FilterSidebar,
  SavedViews, PanelStates, PermissionMatrix and ObjectPermissionPopover, each
  with guidelines (template, view contract, test ids, don'ts), every state in a
  live preview (light, dark, RTL, compact, 375px) and reference CSS in the
  "Wave 2" section of `components/bundle.css`. Six more Lucide icons
  (`bookmark`, `external-link`, `history`, `rotate-ccw`, `shield-check`,
  `sliders-horizontal`) available through `icon(name)`.

### Fixed
- SQLAlchemy 2.0 declarative models now get an adapter (#715).
- Joined-eager collection loads are de-duplicated (#718).
- Deferred columns are left out of generated schemas and inferred list and search fields (#719).
- JSON columns stay out of default list columns and show a one-line preview in list cells (#767).
- Schemas build on Python 3.14 when relationship types are imported only under
  `TYPE_CHECKING` (#770).
- Columns annotated with a SQLAlchemy `TypeDecorator` work in detail and edit views (#772).
- `get_display_name` skips attributes that can't load on a detached row (#773).

### Documentation
- README and docs list the shipped features, supported stacks and real-app results.
- Fixed code samples that called `Admin()` with settings that are not constructor
  arguments (`discover_apps=`, `template_dirs=`): these go through `HyperAdminSettings`.
- Replaced the `ModelView` attribute table, which listed attributes HyperAdmin never read,
  with the `ModelAdmin` / `AdminOptions` fields.
- Quickstarts pass `create_tables=True`, because tables are no longer created by default.
- Install lines use the distribution name `hyper-admin`.

## [0.5.0a1] - not yet published

First PyPI pre-release: `pip install hyper-admin==0.5.0a1` (import name
`hyperadmin`). Every entry in this section ships in it.

### Upgrade note

New: **bring your own app** (st-v058-byoa-51). Adding HyperAdmin to an existing
FastAPI app — its own models, engine, lifespan and login — is described in
`docs/guides/existing-app.md` and `docs/guides/external-auth.md`;
`examples/byoa/` is a runnable host app with UUID and natural-`str` keys, a JWT
API, its own `/static` and `session` cookie, and
`Admin(auth=ExternalAuth(...), session_factory=...)`. Existing installs should
check the points below before upgrading.

- **CSRF is enforced** whenever auth is configured (`auth_backend=`, `auth=` or
  app-level host dependencies). Every built-in page and HTMX request carries
  the token. A custom template with a raw `<form method="post">` needs
  `{{ csrf_input() }}`; your own scripts read `<meta name="csrf-token">` and send
  `X-CSRF-Token`. A rejected request gets 403 with `X-HyperAdmin-CSRF: failed`.
  Escape hatch for one release: `HYPERADMIN_CSRF_MODE=report` logs failures
  instead of refusing them. `HYPERADMIN_SECRET_KEY` is now required whenever
  CSRF is enforced.
- **Behind a TLS-terminating proxy.** The `Origin` rule compares the Origin's
  `host[:port]` with the request's `Host` (or `X-Forwarded-Host`) header; an
  `https` Origin on a request the app sees as plain `http` is accepted on the
  host alone, so a proxy that talks http to uvicorn does not turn every save into
  a 403. `Sec-Fetch-Site: same-origin` passes, `cross-site` fails. If the admin
  is reached through another hostname, list it in `csrf_trusted_origins`
  (`HYPERADMIN_CSRF_TRUSTED_ORIGINS='["https://admin.example.com"]'`). Cookies
  under the default `cookie_secure="auto"` are `Secure` only when the app sees
  `https`: set `HYPERADMIN_COOKIE_SECURE=true`, or let uvicorn trust the proxy
  with `--forwarded-allow-ips` (`forwarded_allow_ips`) so the app sees the real
  scheme. Origin rejections are logged at `WARNING` with the observed Origin
  and Host.
- **Bring-your-own-auth permissions are fail-safe.** Without
  `ExternalAuth(has_permission=...)`, superusers get every permission and every
  other user is view-only. `ExternalAuth(allow_full_access=True)` opts into full
  access for everyone who passes `can_access` (with a startup warning). A user
  who is not a superuser never gets `change_*`/`delete_*` on the host user
  model unless `has_permission` grants it.
- **Sensitive fields are hidden.** Text fields marked `hyperadmin_sensitive`,
  or named like `password|secret|token|hash`, leave search, sort, filters, list
  columns and detail pages, and are write-only on forms. Opt a field back in
  with `AdminOptions(sensitive_fields={"secret_name": False})`.
- **No tables are created by default** (`create_tables=False`) except in
  zero-config demo mode on SQLite. Use your migrations, `hyperadmin init-db`
  (built-in auth tables) or `HYPERADMIN_CREATE_TABLES=true`.
- **Compose `admin.lifespan()`** into your app's `lifespan=`. Startup has a
  first-request safety net, shutdown does not: with realtime enabled, SSE and
  WebSocket connections are drained only when the host runs `admin.lifespan()`
  (or `admin.shutdown()`).
- **The admin is an isolated sub-application**: its static files move to
  `{prefix}/static`, its route names become `hyperadmin:*`, uploads are served
  per record, and the built-in session cookie is renamed `hyperadmin_session`
  (users log in once more). See the entries below for each change.

### Release
- **Version `0.5.0a1` and a working release chain** (st-v058-byoa-50, SDD
  `docs/specs/bring-your-own-app.md` section E).
  - `hyperadmin.__version__` reads the installed distribution version through
    `importlib.metadata`.
  - Commitizen uses `version_scheme = "pep440"` and `major_version_zero = true`.
  - `release.yml` (manual dispatch on `master`) checks its `version` input
    against `pyproject.toml`, pushes the `v<version>` tag, creates the GitHub
    release (`--prerelease` for `a`/`b`/`rc` versions) and calls `publish.yml`
    in the same run. It no longer pushes a bump commit or targets `main`.
  - `publish.yml` is `workflow_call` + `workflow_dispatch` (no longer
    `on: release`). It builds from the tag, runs `twine check`, installs the
    wheel into a clean venv and requests `GET /admin/` from a zero-config
    `Admin(app).mount("/admin")` before uploading with PyPI trusted publishing.

### Added
- **Translated pydantic validation messages** (#531, st-v058-byoa-27, SDD
  `docs/specs/bring-your-own-app.md` section D.4). New
  `hyperadmin.i18n.translate_error(err)` maps a pydantic error's `type` (about
  30 types: `missing`, string length/pattern, numeric bounds, `multiple_of`,
  the `*_parsing` errors, `enum`/`literal_error`, collection length,
  `url_parsing`, `json_invalid`, `value_error`, `assertion_error`) to a gettext
  msgid with `%(ctx)s` placeholders and plural forms; unmapped types fall back
  to `gettext(err["msg"])`. Form, inline-row and bulk-action-form errors now use
  it, so they render in the active locale (`translate_error_lazy` keeps form
  errors re-translatable at render time). English output is unchanged. Ships
  Ukrainian translations, including the "or" joining `enum`/`literal_error`
  choices and pydantic-core's fixed date/time/URL parser details (`input is
  too short`, `relative URL without a base`, ...); interpolated details such as
  UUID's `invalid length: found 3` stay in English. `poe i18n:extract` now also collects
  `gettext_noop` / `ngettext_noop` markers.
- **`session_factory=` seam for bring-your-own-app hosts** (st-v058-byoa-21,
  SDD `docs/specs/bring-your-own-app.md` section C.3). A host that manages its
  own engine, connection pool and transaction scope can now pass a session
  factory instead of an engine:
  - `Admin(app, session_factory=async_sessionmaker(engine))` (keyword-only,
    alongside or instead of `engine=`).
  - `BaseAdapter(model, session_factory=...)` / `BaseAdapter.for_model(model)`
    — every built-in inline, FK-choices and row-scoped-FK adapter construction
    goes through `for_model`, so a `session_factory=`-only admin never needs
    an `engine`.
  - `SessionAuthBackend`, `PermissionSyncService` and `ModelPermissionChecker`
    gain the same `session_factory=` keyword and a `_session()` method.
  - New typing alias `hyperadmin.core.adapters.SessionFactory` and `Protocol`
    `AsyncSessionLike` describing the session shape a factory must yield.

- **Primary-key and datetime-kind introspection for ORM adapters** (st-v058-byoa-15).
  - `SQLModelAdapter` and `SQLAlchemyAdapter` now set `self.pk` to a
    `PrimaryKeyInfo` built from real mapper introspection (int/UUID/str,
    generated vs. natural, remapped `sa_column` attributes, composite keys)
    instead of the historical `int id` default.
  - Both adapters override `datetime_kind(field)` to inspect the mapped
    column (pydantic `AwareDatetime`/`NaiveDatetime` annotation,
    `hyperadmin_tz_aware`, sqlmodel `UTCDateTime`, `DateTime(timezone=True)`)
    rather than the annotation alone, still returning `None` for a
    non-datetime or unknown field per `BaseAdapter`'s contract.

### Changed
- **BREAKING: the admin session cookie is renamed and scoped to the admin**
  (st-v058-byoa-36, SDD `docs/specs/bring-your-own-app.md` section C.4). With
  built-in auth, `AdminSessionMiddleware` (`hyperadmin.auth.session_middleware`)
  stores the admin session in `hyperadmin_session` with `Path=<admin path>`
  (which honours a host `root_path`), and saves and restores a host
  `request.session`, so a host `SessionMiddleware` cookie is never overwritten.
  Users log in again once after upgrading. New settings: `session_cookie`,
  `session_max_age`, `session_same_site` and `cookie_secure` (`"auto"` default:
  `Secure` on https requests; `true`/`false` to force), env `HYPERADMIN_*`.
  Router mode keeps the legacy `session` cookie unless `session_cookie` is set.
  `AuthenticationMiddleware`'s login redirect uses the per-request admin path in
  router mode too.
- **Security: `SessionAuthBackend` rotates the session on login and logout**
  (st-v058-byoa-36). `login()` clears the session before storing `user_id`, and
  `logout()` clears it entirely (it used to pop only `user_id`), so pre-login
  state never survives a privilege change. In legacy router mode without a
  `session_cookie` setting the admin shares the `session` cookie with the host,
  so admin login/logout now also clear host keys in it; set `session_cookie`
  to keep them apart.
- **Security: the locale switcher no longer redirects off-site** (st-v058-byoa-36).
  `POST {prefix}/locale` follows the `Referer` only when it is a same-origin URL
  under the admin path, and otherwise redirects to the dashboard. Its cookie
  `Path` is now the admin path (it was hard-coded to `/admin`, so the locale was
  lost under `mount("/backoffice")`), and it is `Secure` per `cookie_secure`.
- **BREAKING: `Admin.mount()` mounts an isolated sub-application by default**
  (st-v058-byoa-35, SDD `docs/specs/bring-your-own-app.md` section C.1).
  `mount("/admin")` now builds a private FastAPI app (no OpenAPI/docs) and
  attaches it with `app.mount("/admin", ..., name="hyperadmin")`. Two new
  settings control it: `mount_mode` (`"isolated"` default, or `"router"`;
  env `HYPERADMIN_MOUNT_MODE`) and `route_namespace` (default `"hyperadmin"`;
  env `HYPERADMIN_ROUTE_NAMESPACE`). `mount("/")` always uses router mode.
  What changes for an existing host, and how to migrate:
  - HyperAdmin's static files move from `/static` to `{prefix}/static`
    (e.g. `/admin/static`), and the realtime WebSocket from `/realtime/ws` to
    `{prefix}/realtime/ws`. A host `/static` mount is no longer shadowed.
  - Admin route names are namespaced: `request.url_for("user-list")` or
    `app.url_path_for("user-list")` in host code now raises `NoMatchFound`.
    Use `app.url_path_for("hyperadmin:user-list")`, or
    `hyperadmin.views.urls.admin_url_for(request, "user-list")`, which tries
    the namespaced name first. Admin templates need no change.
  - The admin's session, authentication and locale middleware wrap admin
    requests only. Host routes no longer see `request.session`, the admin
    user or a `Content-Language` header. A host page that relies on the
    admin login moves inside the admin: `admin.asgi_app.include_router(...)`
    after `mount()` (as `examples/erp/main.py` does for its reports).
  - Admin routes leave the host's `/openapi.json`.
  - The sub-application shares the host's `dependency_overrides` and `state`.
  - Admin redirects and `{{ admin_prefix }}` template links follow the
    host's `root_path` (a host served at `/api` gets `/api/admin/...`).
- **Fixed: the auth prefix check is segment-safe** (st-v058-byoa-35). With
  auth at `/admin`, a host route such as `/administrator` is no longer
  treated as an admin path and redirected to the admin login.
- **The `sqlmodel<0.0.45` cap is lifted** (st-v058-byoa-48): the requirement is
  now `sqlmodel>=0.0.19`, so hosts can use sqlmodel's tz-aware `UTCDateTime`
  columns. The bundled example models stamp `created_at`/`release_date` with
  `hyperadmin.core.utc_now` (aware UTC) instead of `datetime.now`; host models
  on sqlmodel>=0.0.45 must do the same (or annotate `NaiveDatetime`).
- Constructing a `BaseAdapter` subclass, `SessionAuthBackend`,
  `PermissionSyncService` or `ModelPermissionChecker` with **neither**
  `engine=` **nor** `session_factory=` now raises `ValueError` (previously an
  engine-only `None` silently produced a broken, unusable instance).
- **Primary-key-aware display, FK filter choices and list_display fallback**
  (st-v058-byoa-23). `get_display_name`, `InlineModelSpec.get_display_fields`,
  `infer_list_display`'s fallback and the FK filter-choice builder in
  `core/discovery.py` now resolve the model's actual primary-key attribute
  (via the introspected `pk`/`FieldMeta.is_pk`) instead of hard-coding `"id"`.
- **HyperAdmin design system: brand palette, fonts and tokens** (docs/design/system).
  - New palette: HyperAdmin teal (`#0d9488` brand, `#0f766e` actions) and a
    violet "hyper" accent replace the borrowed FastAPI teal and Pydantic coral.
    Every text pair meets WCAG 2.2 AA in light and dark; ratios are listed per
    token in `docs/design/system/tokens.json`.
  - `_tokens.css` / `_dark-mode.css` carry the new values. All existing token
    names still work; new tokens add surfaces (overlay, hover, selected),
    `--ha-color-border-strong`, `--ha-color-focus-ring`, on-colours, chart
    colours, density sizes and z-index layers. Six names that partials used
    without a definition (`--ha-color-bg-subtle`, `--ha-color-muted`,
    `--ha-color-fg-muted`, `--ha-color-success-bg`, `--ha-color-danger-bg`,
    `--ha-color-danger-subtle`) are now defined.
  - Inter and JetBrains Mono are self-hosted as WOFF2 (`static/fonts`,
    `_fonts.css`); logo, favicon and the Lucide icon subset are in
    `static/img` and `static/icons`.
  - Component specs with live previews: open `docs/design/system/index.html`.
- **The admin UI now uses the design system.**
  - Every CSS partial is ported to the new look (navbar, sidebar with the
    active-item indicator, buttons, table, filter bar, forms, alerts,
    toasts, login, error page) under the existing class names, so forked
    templates keep working. No uppercase labels, 14px base, density tokens,
    one focus ring, 44px targets on touch.
  - The navbar and login page show the HyperAdmin mark next to `site_title`;
    the favicon is the mark.
  - Lucide icons through a new `icon(name)` Jinja macro
    (`components/_icons.html`): row actions, sort arrows, pagination,
    search, filters, theme toggle, toasts. A `ModelAdmin.icon` that names a
    Lucide icon renders it in the sidebar.
  - The detail view is a label/value list; list headings read
    "Invoice List" (they rendered as "InvoiceList").
  - No third-party requests: Google Fonts is gone (Inter is self-hosted and
    preloaded), HTMX 1.9.10 and Alpine.js 3.17.4 are vendored in
    `static/js/vendor/` instead of loaded from unpkg.
  - Visual baselines refreshed (rendered on Linux, like CI).

### Added
- **Bring-your-own-auth bridge primitives** (st-v058-byoa-25, docs/specs/bring-your-own-app.md
  section B.3). `hyperadmin.auth` now lazily exports `ExternalAuth`, `TokenCookie`,
  `CallablePermissionChecker`, `BridgeDefaultPermissionChecker`, `build_admin_dependency`
  and the `default_can_access` / `default_display_name` / `default_user_key` policies, for a
  host FastAPI app to plug its own authentication and permission model into HyperAdmin
  without the built-in `hyperadmin_*` user/group/permission tables. Without
  `ExternalAuth.has_permission`, the fail-safe default grants a superuser everything and
  every other user view-only access; `allow_full_access=True` opts a host into full access
  for everyone who passes `can_access`, and `BridgeDefaultPermissionChecker.protected_model`
  lets a host still deny `change_*`/`delete_*` on its own user model under that opt-in.
  `Admin(auth=...)` wiring these primitives into routes and views follows in a later story —
  nothing in this change is browser-observable yet.

### Security
- **Authorization and row scoping on every item handler** (st-v058-byoa-10).
  - Inline cell edit/save, inline add-row, update form, file delete/upload and
    single actions now enforce the model permission and, where an object is
    loaded, the object permission (`change`, or `action_<name>` for actions).
  - `ModelAdmin.get_queryset` row scoping is request-scoped (held in a
    `ContextVar`, not on the shared adapter) and applies to every item, bulk,
    inline and choices handler. Rows hidden from the user return 404, and
    concurrent requests can no longer see each other's filters.
  - `DELETE /{model}/{id}/file/{field}` only accepts file fields and never
    removes a file outside the storage root (absolute paths, `..` and symlinks
    are refused). Uploads also require a file field.
  - Inline formsets reject a submitted child pk that is not an existing child of
    the parent being saved (404, nothing written), and enforce the inline
    model's own `add` / `change` / `delete` permissions when that model is
    registered. An unregistered inline model has no permission rows, so the
    parent's `add` / `change` permission governs its rows.
  - Related rows need `view` on the target model wherever they are disclosed:
    the choices endpoint (403), list-page relation filters (omitted) and the
    create/edit relation widgets (only the selected key is kept, labelled
    `Model (pk)`). An unregistered target falls back to the source model's
    permission.
  - `POST /{model}/upload/{field}` ignores the client path: it stores the
    sanitised basename under a fresh random prefix, never overwrites an
    existing file, refuses names outside the storage root, and returns the
    stored name relative to the storage root (not an absolute server path).
  - Upgrade note for adapter authors: an adapter that implements
    `save_inline_rows` must also implement `inline_child_pks(spec, parent_pk)`.
    The default returns an empty set, so every save of a parent with existing
    inline rows is rejected (404) until it is implemented. See
    `docs/api/adapters.md`.
- **Query oracles on secret columns closed** (st-v058-byoa-53). A user who could
  list a model could previously probe a column such as `password_hash` one
  query at a time. All four oracles are closed:
  - **Filters:** URL `filter_<field>` parameters are honoured only for fields in
    `list_filter`; anything else is ignored.
  - **Search:** inferred search fields (and the adapters' fallback search, and
    the choices `q` search) skip sensitive fields, including fields made
    sensitive only through `AdminOptions.sensitive_fields` on the model's (or
    the choices target's) admin. An explicit `search_fields=[]` passed to an
    adapter now disables search instead of falling back to every text column.
  - **Sort:** `sort_by` is whitelisted against the displayed, non-sensitive
    columns. An unknown value falls back to the default sort (200, never 500).
  - **Choices:** `/{model}/choices/{field}` forwards only the cascade keys the
    relation widget declares (`dependent_on`, `dependent_fields`,
    `relation_filters`) and applies the target admin's `get_queryset`.
  - **Relation labels:** FK filter dropdowns, relation widgets, the choices
    endpoint, popup-create labels and list cells label related rows with the
    model's own `__str__` when it defines one, otherwise with the first
    non-sensitive of `name`, `title`, `label`, `username`, `email`, otherwise
    `Model (pk)`. SQLModel's default `__str__`, which prints every column
    (password hashes included), is never used.
  - **Writes:** a submitted FK value must be a row that the target admin's
    `get_queryset` exposes; otherwise the form is re-rendered with a field
    error (422) and nothing is written.
  - New `hyperadmin.core.sensitive`: a field is sensitive when it carries the
    `hyperadmin_sensitive` marker, or when it is a text (`str` / `bytes`) field
    whose name matches `(^|_)(password|secret|token|hash)(_|$)`;
    `AdminOptions.sensitive_fields` overrides this either way. With SQLModel,
    mark a field with
    `Field(schema_extra={"json_schema_extra": {"hyperadmin_sensitive": True}})`
    (SQLModel's `Field()` rejects a direct `json_schema_extra=` argument); with
    plain Pydantic use `Field(json_schema_extra={"hyperadmin_sensitive": True})`.
    Sensitive fields are hidden from the detail page and inferred list columns.
    Sensitive text fields are write-only on forms and inline rows (an empty
    submission keeps the stored value). A sensitive non-text field (a marked
    boolean or enum) is left out of the edit form and keeps its stored value.
    The built-in `User.password_hash` is marked.
  - Upgrade note: a text column such as `secret_name` now counts as sensitive.
    Opt it back in with `AdminOptions(sensitive_fields={"secret_name": False})`.
    The name heuristic does not apply to booleans, numbers or enums
    (`is_secret: bool`, `token_count: int`).
- **Uploaded files are no longer public** (st-v058-byoa-37, SDD C.5). The
  `/uploads` static mount at the host root is removed. Files are served per
  record at `{prefix}/{model}/{item_id}/file/{field}` (route `<model>-file`),
  which requires `view`, applies `get_queryset` and the object `view` check,
  and sends `nosniff`, `Content-Security-Policy: sandbox` and
  `Content-Disposition: attachment` for everything except PNG, JPEG, GIF and
  WebP (never SVG). Form uploads, like `upload_file_view`, are stored under a
  unique `<uuid4 hex>-<name>` so a same-name upload never overwrites another
  record's file. Upgrade note: links to `/uploads/<name>` stop working; set
  `HYPERADMIN_PUBLIC_UPLOADS_PATH=/uploads` to restore the public mount (a
  startup warning is logged).

### Deprecated
- `mount_mode="router"` (the legacy `include_router` mount, st-v058-byoa-35)
  emits a `DeprecationWarning` and will be removed in 0.6. It keeps the old
  behaviour: un-namespaced route names, `/static` at the host root, and admin
  middleware on the host app.

### Added
- **`ha_pk`, `ha_dom_token`, `ha_datetime_input`, `ha_display` template filters**
  (st-v058-byoa-33). `ha_pk` reads a row's primary key from a dict or model
  instance; `ha_dom_token` turns any key into a DOM-id/`data-testid`-safe
  token; `ha_datetime_input`/`ha_display` localise datetimes to the admin's
  configured `timezone` (overridable per request via
  `request.state.hyperadmin_timezone`) and format display with the
  existing `datetime_format` setting, which now actually drives `ha_display`.
- **`hyperadmin.views.urls.admin_url_for` / `admin_base_path`, and a
  namespace-aware Jinja `url_for` override** (st-v058-byoa-34).
  `admin_url_for` prefers an admin route's namespaced name when
  `request.scope["hyperadmin"]["namespace"]` is set, falling back to the
  plain name so host routes keep resolving; `Admin` installs it as the
  template env's `url_for` global, replacing Starlette's own. Both helpers
  are currently no-ops until the isolated sub-app mount (st-v058-byoa-35)
  starts setting `scope["hyperadmin"]`.
- Initial project scaffold
