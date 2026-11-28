# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/),
and this project adheres to [Semantic Versioning](https://semver.org/).
Version numbers follow [PEP 440](https://peps.python.org/pep-0440/) (for example
`0.5.0a1`); while the major version is `0`, breaking changes bump the minor version.

## [Unreleased]

### Fixed
- **Slow concurrent search on SQLite.** List search, autocomplete and record search ran
  `lower(column) LIKE lower(?)` on SQLite, and `lower()` stops concurrent scans of a large
  table from running in parallel: on 900,000 rows one search scan took 89 ms alone and 1.4 s
  each with five at once, and the slow searches held pool connections so list and detail
  pages queued behind them. On SQLite the search is now a plain `LIKE`, which ignores ASCII
  case just as `lower()` does (5 scans at once: 45 ms each). PostgreSQL keeps `ILIKE`. With
  `PRAGMA case_sensitive_like = ON`, SQLite search becomes case-sensitive.
- **"Create" button for read-only users.** The list page hid nothing when the user lacked
  `add_<model>`, so a read-only user saw "Create <model>" and got a 403. The button now follows
  the same permission the create routes check (and `AdminOptions.can_create`). The ERP example's
  dashboard quick actions follow each `add_<model>` permission too.
- **Second select under an autocomplete after a failed submit.** A 422 form re-render was
  written into the page a second time with raw `innerHTML`, after htmx had swapped and enhanced
  it, so the autocomplete came back un-enhanced: its native `<select>` showed under the search
  box and the search no longer fetched choices. htmx now does the only swap.
- **Autocomplete list gap** (#1130). A single-value autocomplete's options list opened 40px below
  its field; it now starts at the field's edge and flips above the field near the viewport bottom.
  A multi-value autocomplete's list joins its search field.
- **Empty "All reports" page in the ERP example.** The example registered no `ReportView`, so the
  reports plugin's index said "No reports available"; it now registers "Invoices by status" and
  "Bills by status". `hyperadmin-reports` now shows an enum dimension by its value ("Paid")
  instead of the member ("InvoiceStatus.PAID") in the grid, charts and exports.
- **Phone navbar and touch targets** (#1018, #1014, #1026). Below 640px the language and theme
  controls move into the account menu and the brand shrinks to its mark (the link keeps the site
  name as its label), so pages no longer scroll sideways at 360px. Sidebar group toggles, pin
  buttons, the rail toggle and list sort links reach 44px under a coarse pointer. Sidebar pin
  buttons now show only on hover, focus, the current page and pinned items; on touch devices
  (no hover) they stay tappable on every row, dimmed until current, focused or pinned.

### Added
- **Claude Code skills and agents for HyperAdmin users.** The repository now ships, in
  top-level `skills/` and `agents/` folders and as a Claude Code plugin (`.claude-plugin/`),
  six skills (`hyperadmin-getting-started`, `hyperadmin-define-ui`, `hyperadmin-extend-ui`,
  `hyperadmin-new-plugin`, `hyperadmin-migrate-from-django`, `hyperadmin-migrate-from-flask`)
  and two agents (`django-migration-agent`, `flask-migration-agent`) that inventory a Django or
  Flask-Admin project, report the mapping and the gaps, and generate the HyperAdmin app after
  approval. Install steps: [Claude Code Skills](docs/guides/ai-skills.md). A unit test checks
  their frontmatter, code blocks and `hyperadmin` imports.
- **Database comparison load test** (#989). `scripts/loadtest_scale.py` seeds 1.2 million rows
  into SQLite, PostgreSQL 17 (a throwaway Docker container) and PostgreSQL 17 with a `pg_trgm`
  GIN index on the searched column, then measures reads (list, detail, search) and writes
  (create, update, delete) separately, twice each, only on an idle host. The scalability test
  app reads `E2E_SCALABILITY_DATABASE_URL` to run on a database seeded elsewhere. Results are in
  the load-testing section of the compatibility guide.
- **Collapsible filter panel** (#1130). The Filters button in a list's search row collapses the
  filter panel so the table takes the whole content width. The panel starts expanded from 1440px,
  collapsed below; each viewer's choice is kept in `localStorage`, and the button shows the active
  filter count while the panel is collapsed. No new option.
- `hyperadmin.adapters.filtering.build_clauses(model, conditions)` is public: it turns typed
  `FilterCondition` objects into SQLAlchemy clauses, so a plugin that queries a model itself can
  apply the list page's filters. `hyperadmin-reports` uses it instead of the private
  `hyperadmin.adapters._filter_clause`, which still imports (st-v100-freeze-03).
- **Report filters** (#883). A `hyperadmin-reports` `ReportView` can declare `filters` (field
  names or `hyperadmin.filters` definitions, as in `list_filter`). They are applied before the
  aggregate, on the fact table when the report has a `cache`, and the report page gets the list
  view's filter sidebar. The grid, the chart and the CSV / XLSX exports read the same
  querystring, and the XLSX "Filters used" sheet lists what was applied.
  `ReportView.run(filters=..., binding=...)` does the same from code.

- **Dashboard** (#422). With `hyperadmin-reports` installed, `register_widget(...)` puts report
  numbers (`StatWidget`), report charts (`ChartWidget`) and shortcut links
  (`QuickActionsWidget`) on the admin home page; custom cards subclass `DashboardWidget`. A card
  shows only to users who hold its report's permission, a failing card shows an error state
  with Retry, and each user can reorder the cards by drag and drop or with keyboard "Move up" /
  "Move down" buttons. The order is kept in a table the plugin owns
  (`hyperadmin_reports_dashboard_layout`), which hosts create on purpose with
  `create_layout_table()`; without it the default order is shown. Without registered widgets
  nothing changes. Plugin settings: `dashboard_home`, `dashboard_layouts`, `dashboard_prefix`
  (`HYPERADMIN_REPORTS_*`). New plugin seam: `PluginRegistry.set_home_page()`.
- **OAuth sign-in with Google and GitHub** (#420). `Admin(oauth_backend=OAuthBackend(providers=...))`
  adds "Sign in with ..." buttons to the built-in login page, with PKCE, a single-use state,
  tokens encrypted at rest (`HYPERADMIN_OAUTH_TOKEN_SECRET`), a token refresh middleware, MFA
  after the OAuth step and link/unlink at `{prefix}/oauth/settings`. Accounts are never linked by
  email. Opt-in: needs `pip install 'hyper-admin[oauth]'` and the new `hyperadmin_oauth_tokens`
  table (`hyperadmin init-db` or your migrations); without `oauth_backend` nothing changes and no
  existing table is altered. See the OAuth Sign-In guide.
- **Estimated list totals** (#211). `AdminOptions(count_estimate_threshold=1_000_000)` makes an
  unfiltered list of a table the database estimates at that many rows or more skip `count(*)`
  and show the planner estimate, marked `~4200000` in the pager. Filtered and searched lists,
  tables below the threshold, stale estimates (0 or less) and databases without row estimates
  still count exactly. Off by default, so existing totals do not change.
- **Rate limiting** (#233, #234, #235). `rate_limit_requests`, `rate_limit_login_requests`
  and `rate_limit_window_seconds` on `HyperAdminSettings` (`HYPERADMIN_RATE_LIMIT_*`) make
  the admin answer `429` with `Retry-After` once one client passes the limit. Static assets
  are never counted. Off by default. A `RateLimiter` protocol and a per-process
  `InMemoryRateLimiter` live in `hyperadmin.core.rate_limit`; pass
  `Admin(app, rate_limiter=...)` to share one limit across workers.
- **Record search in the command palette** (st-v059-nav-05). `AdminOptions(palette_search=True)` lets
  Cmd/Ctrl+K find a model's records through its `search_fields`, under a new "Records" section. One
  endpoint, `GET {prefix}/nav/search`, checks `view_<model>`, applies `get_queryset()` and returns at
  most 5 records per model and 6 models per search; the browser debounces typing by 250 ms. Off by
  default, so no table is queried unless the host opts in.
- **Table readability** (st-ux-erp-04, -13, -14, -08). List cells format decimals with thousands separators and right-align
  numeric columns (`ha_number`), enum columns can render as status pills (`__ha_tones__`, `ha_pill`), phone cards get a
  title/status/amount hierarchy, and tablet tables show scroll shadows.
- **Form UX fixes** (st-ux-erp-01, -06, -07, -11). Models with a relationship named
  `items`, `keys` or `values` save again; `date` fields render a native date input;
  validation errors use plain wording ("Enter a date") with an error summary that takes
  focus and links to each field; list and create pages use verbose names ("Journal lines",
  "Create journal line") and foreign-key labels drop `_id`.
- **Connection pool settings** (#231, #232). `database_pool_size`, `database_max_overflow`,
  `database_pool_timeout`, `database_pool_recycle` and `database_pool_pre_ping` on
  `HyperAdminSettings` (`HYPERADMIN_DATABASE_POOL_SIZE` and so on) tune the engine
  HyperAdmin builds from `database_url`. Unset, SQLAlchemy's defaults apply as before.
  `hyperadmin.db.build_engine(url, engine_kwargs)` forwards the same arguments for an
  engine you pass yourself and drops pool sizing for in-memory SQLite.
- **Sidebar groups and icons, data layer** (v0.5.9, st-v059-nav-01). `NavGroup` and
  `Admin(nav_groups=[...])`, plus `nav_group`, `nav_order` and a documented `icon` on
  `ModelAdmin`. The new `nav_tree` template global groups models (falling back to
  `app_label`) and merges plugin sections into the group with the same label. `nav_items`
  keeps its shape. 24 Lucide icons added for domains and navigation.
- **Grouped, collapsible sidebar with an icon rail** (v0.5.9, st-v059-nav-02). The sidebar
  renders `nav_tree` with AppShell markup: a heading toggle per group, collapsed groups kept
  in the `ha-nav-collapsed` cookie, a desktop icon rail (`ha-sidebar-rail` cookie), both
  read on the server so the first paint is right. The active item matches by URL segment
  (`/order/42/edit` activates Orders, not Order lines). Groups whose items the user may not
  view are not rendered. Links appended to `nav_items` after `mount()` still show, in the
  top group. New template globals `visible_nav_tree()`, `nav_collapsed_groups()`,
  `sidebar_rail()` and `nav_is_active(item)`; test ids `nav-<key>`, `nav-group-<slug>`,
  `sidebar-rail-toggle`.
- **Pinned pages in the sidebar** (v0.5.9, st-v059-nav-03). With auth configured, each
  user can pin models and plugin pages; they show in a "Pinned" group at the top of the
  sidebar on every device. New `hyperadmin.navigation` package (`NavPin`, table
  `hyperadmin_nav_pin`, and `NavPinService`), endpoints `POST {prefix}/nav/pins` and
  `DELETE {prefix}/nav/pins/{target}`, and `HyperAdminSettings.nav_pins_max` (default 20,
  `HYPERADMIN_NAV_PINS_MAX`). Pins are filtered by permission when the page renders. A
  missing table is logged once and hides the feature. Template global
  `nav_pinned_items()`; test ids `nav-pinned`, `nav-pin-<key>`.
- **Built-in auth models in the "Access" sidebar group** (v0.5.9). User, Group and
  Permission get their own icons and join the permission matrix in "Access" instead of the
  unnamed top group. The `list-checks` icon is added for the tasks plugin's sidebar entry.
- **ERP example shows the v0.5.9 navigation and list features** with sidebar groups, icons
  and rendered screenshots (`scripts/erp_screenshots.py`). Its Profit & Loss report is now a
  plugin page at `/admin/erp/profit-loss` (was `/admin/reports/profit-loss`) in the Reports
  group.
- **Plain SQLAlchemy models** (#719, #725–#730). Models built on SQLAlchemy 2.0
  `DeclarativeBase` or the legacy `declarative_base()` register with
  `site.register(Model)`, with no SQLModel base class. HyperAdmin builds a Pydantic schema
  from the mapper (`hyperadmin.core.schema_for` / `dump_instance`), and every view reads
  fields through it. New `examples/sqlalchemy/` app with a Playwright smoke test.
  Auto-discovery still finds SQLModel models only (#716).
- **Command palette** (v0.5.9, st-v059-nav-04). Cmd/Ctrl+K, or the "Search… ⌘K" navbar
  button, opens a dialog that finds models, groups and plugin pages by name, lists recent
  pages and records (localStorage `ha-recent`) and offers "New …" where the user may add.
  It matches in the browser over a permission-filtered `ha-nav-data` island, so it sends no
  request per keystroke. New `static/js/shortcuts.js` registry (`window.haShortcuts`) with an
  off switch for single-key shortcuts (localStorage `ha-shortcuts`); `/` still focuses the
  list search, while Cmd/Ctrl+K no longer does. New template global `ha_nav_palette()`.
- **Unsaved-changes guard, sticky save bar and Cmd/Ctrl+S** (v0.5.9, st-v059-kbd-01). New
  `static/js/form_guard.js`: once a create, edit or popup create form has changes (inline
  rows included), leaving the page or an htmx request that would replace the form asks
  first. Saving never asks, and a delete from the edit page asks only in the delete dialog.
  The form actions stick to the bottom of the screen (`data-testid="form-actions"`), and
  Cmd/Ctrl+S submits the form. Turn the prompt off per model with
  `AdminOptions(warn_unsaved_changes=False)`.
- **List keyboard navigation and shortcuts overlay** (v0.5.9, st-v059-kbd-02). On lists, `j`/`k`
  focus the next or previous row link, Enter opens it, `x` selects the focused row and `c`
  opens the create form. `?` (or Cmd/Ctrl+/, which stays on) opens
  `components/shortcuts_overlay.html` (`data-testid="shortcuts-overlay"`), which lists every
  registered shortcut and holds the "Single-key shortcuts" switch (`shortcuts-toggle`).
- **Compatibility & Performance docs page** (`docs/compatibility.md`): supported stacks,
  results of running HyperAdmin unmodified on Polar, Langflow, Mealie and Open WebUI
  (epic #701), timings on 237,757 rows, and known limitations.
- **Load-test matrix** (`scripts/loadtest_matrix.sh`): runs the ERP Locust suite across
  database, app CPUs, users and realtime backend, stops a row once the app log shows overload,
  and writes a summary table. Results (about 300 req/s at a median of 21 ms for 400 users on 9
  CPUs) are in the README and on the Compatibility & Performance page. The ERP example reads
  `DB_POOL_SIZE` / `DB_MAX_OVERFLOW` / `DB_POOL_TIMEOUT`, and `LOADTEST_LOGIN_SESSIONS` shares
  logins between Locust users.
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
- **Plugin lifecycle hooks fire.** `on_model_register`, `on_before/after_create`,
  `on_before/after_update`, `on_before/after_delete` and `on_before/after_adapter_call` are now
  called by the admin, and two hooks are new in `LIFECYCLE_HOOKS`: `on_validation_error` (field
  error types only, never input values) and `on_auth_event` (`login_success`, `login_failure`,
  `logout`, `permission_denied`; never the password). A failing hook is logged and does not
  affect the request. `hyperadmin plugins list` prints the discovered plugins and whether each is
  disabled.
  See [the hook reference](docs/plugins/hooks.md) and the new plugin author guide.

### Changed
- **The "h:" mark everywhere outside the `classic` preset.** The docs site logo, favicon
  (`.ico` with 16/32/48 px), 16/32 px PNG favicons, Apple touch icon and Android icons now show
  the terminal mark, and the README shows a new wordmark
  (`static/img/terminal/hyperadmin-wordmark.svg` and `-dark.svg`: the mark plus "HyperAdmin"
  outlined from JetBrains Mono). The ERP example's login page follows `theme_preset` like the
  built-in one. The `classic` preset keeps its teal files in `static/img/`.
- **New default look: the "terminal" theme preset** (#1132). `HyperAdminSettings.theme_preset`
  (`HYPERADMIN_THEME_PRESET`) picks the visual theme: `"terminal"` (the new default: near-black
  ground, acid-green accent, square corners, flat cards, JetBrains Mono for headings, labels and
  buttons, status pills told apart by shape) or `"classic"` (the earlier teal look with rounded
  corners). It works with every light / dark `theme`, and token names are the same in both, so
  host CSS overrides keep working; overrides aimed at the terminal preset must match
  `:root[data-ha-preset="terminal"]`. Set `theme_preset="classic"` to keep the old look.
- `HyperAdminModel.before_save()` and `after_save()` now run on every create and update made
  through `SQLModelAdapter` and `SQLAlchemyAdapter` (forms, inline rows, quick-create and
  list-editable cells): `before_save` just before the commit, `after_save` once the row is
  committed and refreshed. The never-called `before_delete()` and `after_delete()` were removed.
  `HyperAdminModel` stays outside the documented API; plugin lifecycle hooks are the supported
  extension point (st-v100-freeze-03).
- `HyperAdminSettings.items_per_page` (`HYPERADMIN_ITEMS_PER_PAGE`) now sets the rows a list
  page shows when the URL has no `page_size` parameter; it was accepted but never read. Its
  default is now `10`, the page size lists already used, so nothing changes unless you set it.
  Values above 100 are capped at 100 (st-v100-freeze-03).
- `action(requires_selection=...)` is annotated `bool | None` and defaults to `None` (derive
  it from `bulk`), so the public signature no longer shows an `object()` sentinel. Behaviour is
  unchanged (st-v100-freeze-03).
- **BREAKING: list pages no longer load every relation** (#215, #216, #217, #218).
  `SQLModelAdapter.list()` used to `selectinload` every relationship, one extra query per
  relation on every request. It now loads none unless asked: the admin loads the relations named
  in `column_list` (`"category"` or `"category.name"`; turn off with
  `AdminOptions(auto_select_related=False)`) plus `AdminOptions(list_select_related=[...])`. Add
  any other relation your list template or `__str__` reads to `list_select_related`, or it raises
  `DetachedInstanceError`. `adapter.list()` and `adapter.get()` take `load_relations=[...]`
  (`SQLAlchemyAdapter` honours it too); an unknown name raises `ValueError`. Detail pages are
  unchanged unless you set `AdminOptions(detail_select_related=[...])` (`[]` loads none).
- **List cell display** (st-ux-erp-04, -13). Every `float`/`Decimal` list cell now shows locale grouping and at least two
  decimals (`4.5` reads `4.50`, up to six places), and every `Enum` list cell renders as a status pill whose tone comes
  from the enum's `__ha_tones__` or a built-in table keyed on the member name. Detail, edit and CSV export are unchanged.
  The pager gained a rows-per-page selector (10, 25, 50, 100). A per-field currency code is not wired yet; `ha_number`
  accepts one for a future option.
- **Clickable list rows** (v0.5.9, st-v059-list-02). The View and Edit row buttons are gone:
  the title cell (the first column that is not inline-editable) is a `<th scope="row">` link
  that opens the edit page for users who may change the record and the detail page for
  read-only users, and the whole row is clickable. The detail page gains Edit and Delete,
  the edit page gains View and Delete. **Test ids:** `row-view-link` and `row-edit-link` are
  removed; E2E suites that click them should use `row-link` (new: `detail-edit-link`,
  `detail-delete-btn`, `form-view-link`, `form-delete-btn`). Hosts that override
  `components/table_body.html` keep their own row buttons.
- **Delete confirms in a dialog** (v0.5.9, st-v059-list-03). The row Delete is a red ghost
  icon button (`trash-2`, labelled "Delete {object}", tooltip), shown only to users who
  may delete. It and the detail and edit pages' Delete open one shared
  `components/confirm_delete_dialog.html` (`role="alertdialog"`, focus on Cancel,
  `data-testid="dialog-confirm-delete"`) instead of the browser's `confirm()`, so E2E
  suites that accept a native `page.on("dialog")` prompt should click the dialog's Delete
  button instead. A refused delete (409 when other rows still reference the record) closes
  the dialog and shows the error toast.
- **Locale catalogs refreshed** (v0.5.9). All 20 catalogs now list every UI string, including
  the v0.5.9 sidebar, palette, list, delete dialog, unsaved-changes and shortcut strings, and
  the strings added since v0.5.2. `uk` translations are compiled; the other 18 locales get
  machine drafts marked `#, fuzzy`, so they keep rendering English until a native speaker
  reviews them (`docs/specs/i18n-top-20-locales.md`). `poe i18n:extract` now also extracts
  `gettext_lazy` strings, which picks up the "Plugins" and "Access" sidebar groups.
- **Permissions are read once per request** (#1057). `ModelPermissionChecker` reads a user's
  direct and group permissions the first time they are needed and remembers the set on that
  user object, so a page costs two permission queries however many models are registered
  (it was two per check). Nothing is kept between requests: a grant or revocation shows on
  the next request. If you change permissions and keep checking the same user object, call
  `hyperadmin.auth.permissions.forget_user_permissions(user)` (the permissions matrix does).

### Deprecated
- `hyperadmin.PDFStreamPanel` is deprecated and will be removed in 0.6. It was the same
  function as `pdf_stream_panel` under a class-style name, so `isinstance` and subclassing never
  worked; calling it now emits a `DeprecationWarning`. Use `hyperadmin.pdf_stream_panel`
  (st-v100-freeze-03).

### Removed
- **Agentic delivery tooling.** The local autopilot (`ops/autopilot/` and its `autopilot:*` poe
  tasks and `just` recipes), the AI reviewer, architect, project-manager and triage agent
  definitions, the planning workflows and their slash commands, the Claude Code container, the
  triage audit script (`triage:audit` task) and the "Agentic Workflow" section of the docs site
  are gone. `.meta/` and GitPM stay. No library change.

### Fixed
- Built-in auth now creates the permissions custom actions and detail panels check. At startup
  `PermissionSyncService` adds one `action_<name>_<model>` codename per `@action` method and
  the codename of every detail panel (`view_<model>_panel_<slug>`, or its `permission=`), next
  to the four CRUD codenames and `ModelAdmin.permissions`; before, only a superuser could run a
  custom action or open a panel unless the codename was added by hand. `ModelAdmin.permissions`
  is now declared and documented. The docs named the action codename `action_<name>`; the views
  have always checked `action_<name>_<model>`. Upgrade note: if your app inserts these
  codenames into `hyperadmin_permissions` itself after the admin has started, drop that code,
  or the second insert fails on the unique `codename` (st-v100-freeze-03).
- A dotted `list_display` accessor such as `"customer.name"` now shows the related value in
  the list cell; the relation was loaded but the cell stayed empty. A hop the list did not load
  and a sensitive related field both show an empty cell (st-v100-freeze-03).
- A foreign-key field keeps its stored value on the edit form even when the related row
  falls outside the 50 preloaded options (st-ux-erp-02, #1023); before, the select showed
  `---------` and saving failed with "Input should be a valid integer".
- A single-value FK field is now one ARIA combobox instead of a search box plus a select
  (st-ux-erp-12, #1024): the input shows the chosen label with the placeholder
  "Choose a customer…" and lists the options in a popup, operable by keyboard.
- Inline formsets label the model in words and in the request locale: "Add invoice item"
  and a default title of "Invoice items", instead of "Add InvoiceItem" and "InvoiceItems";
  the "Actions" column header is translated too.
- SQLAlchemy 2.0 declarative models now get an adapter (#715).
- Joined-eager collection loads are de-duplicated (#718).
- Deferred columns are left out of generated schemas and inferred list and search fields (#719).
- JSON columns stay out of default list columns and show a one-line preview in list cells (#767).
- Schemas build on Python 3.14 when relationship types are imported only under
  `TYPE_CHECKING` (#770).
- Columns annotated with a SQLAlchemy `TypeDecorator` work in detail and edit views (#772).
- `get_display_name` skips attributes that can't load on a detached row (#773).

### Documentation
- **Roadmap rewritten for 1.0.** The Roadmap page now lists what 1.0 includes, what it leaves
  out (the dropped JSON REST API and multi-tenancy, and unscheduled work such as record
  history) and the known gaps it ships with (per-field form options, extra stylesheets, host
  translation catalogs, fuzzy locale drafts, MySQL, an MFA guide). `ROADMAP.md` points to it.
  Compatibility & Performance says which real-app runs and the MySQL check were not done,
  Examples lists the background tasks app, the migration guides mention plugin lifecycle
  hooks next to the missing per-admin save hooks, the existing-app guide no longer points at
  internal design documents, the design system notes that it describes the `classic` preset,
  and `CONTRIBUTING.md` gains the public API snapshot section from the docs site.
- **The ERP invoice list fits next to the filter panel.** The example's Invoices list drops the
  Date Issued column (Date Due, its filter and the detail and edit pages keep the dates), so the
  README hero shot and the other invoice-list screenshots show Total Amount whole instead of a
  clipped, scrolling table. The ERP load test no longer sorts invoices by issue date.
- **Demo load-test card re-recorded after the SQLite search fix.** The demo video and the
  load-test screenshot show the current SQLite figures (1.2 million rows, 20 users, 30 s, second
  of two runs): reads 46 req/s with list and detail at a 9 ms median, search 110 ms median and
  130 ms p95; writes 112 req/s at a 38 ms median and 110 ms p95. Demo Tour quotes them, "How it is
  verified" drops its note about the outdated card, and Compatibility & Performance gives the
  macOS CI Python versions per trigger (pull requests: 3.11 and 3.14).
- **Reference fixes before 1.0.** The Views reference lists the `ModelAdmin` attributes and the
  ten `AdminOptions` fields it was missing (`enforce_occ`, `palette_search`, `pagination_mode`,
  `count_cache_ttl`, `count_estimate_threshold`, `filter_cache_ttl`, `list_select_related`,
  `auto_select_related`, `detail_select_related`, `preload_threshold`), and the Application
  reference the `oauth_backend` argument. New **List Filters** guide: every built-in filter in
  `hyperadmin.filters` and how to write a `FilterDef` subclass; the built-in filters join the
  API reference and the public API snapshot. The plugin guide documents
  `PluginRegistry.set_home_page()`. Getting Started says per-model template overrides need
  `site.register(..., app_label=...)`. The migration guides point `list_per_page` / `page_size`
  at the global `items_per_page` setting. The hook reference no longer presents
  `HyperAdminModel.before_save()` / `after_save()` as an extension point.
- **Public API audit** (st-v100-freeze-03). A snapshot test (`tests/unit/test_public_api.py`)
  records the public API defined in the versioning policy and fails on any change to it. New
  API reference pages for authentication and permissions, plugins, uploads and realtime; the
  core and views pages now cover settings, actions, fieldsets, inlines, concurrency errors,
  rate limiting, panels, filters and `admin_url_for`. The docs now say plainly that plugin
  lifecycle hooks are reserved but not fired yet. Every `HyperAdminSettings` field has a row in
  a settings table (a test keeps it that way); `date_format` and `site_header` are marked as not
  used by the built-in pages. The realtime guide installs `hyper-admin[realtime]` and
  `hyper-admin[redis]` (it named the wrong distribution).
- README and docs list the shipped features, supported stacks and real-app results.
- **Screenshots in the pages they illustrate, and pages for reports, Logfire and languages.**
  The current screenshots now sit in the realtime, performance, OAuth, tasks, navigation,
  widgets, frontend, auth and ERP pages. New pages: Reports & Dashboard
  (`hyperadmin-reports`), Logfire Traces (`hyperadmin-logfire`) and Languages & RTL, which says
  plainly that Ukrainian is the only reviewed catalog and the other locales show English until
  reviewed. New sections: bulk actions, conflicting saves (`enforce_occ`), the permissions
  matrix and small screens; the widget auto-selection table lists upload, relation, autocomplete
  and date widgets. The docs build now enables `attr_list`, so image widths apply instead of
  showing as text. README lists OAuth, concurrency, rate limits, the large-table features and
  the plugins.
- Fixed code samples that called `Admin()` with settings that are not constructor
  arguments (`discover_apps=`, `template_dirs=`): these go through `HyperAdminSettings`.
- Replaced the `ModelView` attribute table, which listed attributes HyperAdmin never read,
  with the `ModelAdmin` / `AdminOptions` fields.
- Quickstarts pass `create_tables=True`, because tables are no longer created by default.
- Install lines use the distribution name `hyper-admin`.
- New **Versioning & Deprecation Policy** page (`docs/versioning.md`): what the public API is,
  what a major, minor and patch release may change before and after 1.0, how a feature is
  deprecated and removed, and the supported Python and dependency versions.
- New **migration guides** from Django admin, SQLAdmin and Flask-Admin (`docs/migration/`,
  RFC #274): concept mapping tables, a blog admin ported step by step, the auth and permission
  mapping, and what has no equivalent yet.
- New **How it is verified** page (`docs/how-it-works.md`): the unit, plugin and E2E suites
  with their counts, the CI matrix (Python versions with highest and lowest-direct dependency
  resolution), the 100% changed-line coverage gate, the visual-regression baselines, the public
  API snapshot, the translation catalog checks, the load tests and the generated demo tour, each
  linked to the code that runs it.

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
