# SDD: Dashboard Builder with Widgets

| Field | Value |
|---|---|
| Author | Claude Code |
| Status | Approved (architect) |
| Issue | #422 (epic), #455 (review gate) |
| Milestone | v0.5.4 — Reporting & Charts |
| Created | 2026-05-10 |
| Last updated | 2026-11-20 |

---

> **Revision 2 (2026-11-20, architect).** The 2026-05-10 draft put a `dashboard/` package into the
> core, added `count()` / `aggregate()` to `BaseAdapter` and a `hyperadmin_dashboard_layouts`
> table on `SQLModel.metadata`. Since then reports and charts shipped as the first-party plugin
> `hyperadmin-reports` (`docs/specs/olap-reporting.md`, `docs/specs/chart-components.md`) on the
> plugin UI seams (`docs/specs/plugin-registry.md`), and the v0.5.4 milestone describes the
> dashboard as "the widget/layout layer over `ReportView`". This revision moves the dashboard into
> that plugin, binds its data widgets to registered `ReportView`s, drops the adapter helpers and
> keeps the layout table out of the host's migrations. The Decision Log keeps the superseded
> decisions, marked as such.

## Problem

`Admin(app)` serves a static "Welcome to HyperAdmin Dashboard" page at `{prefix}/`. Hosts that
installed `hyperadmin-reports` have aggregated numbers and charts on `{prefix}/reports/{slug}/`,
but nothing puts them on the page people land on. Today a host has to:

1. leave the welcome page and send people to the reports index, or
2. override `dashboard.html` in its own templates and hand-wire HTMX calls to the report chart
   fragments, re-implementing the permission checks the reports pages already do.

Nor can a user put the numbers they care about first. The dashboard builder is the layer that puts
report numbers, report charts and shortcut links on the admin home page, lets each user order them,
and remembers that order.

## Goals

- **The admin home page is the dashboard** when `hyperadmin-reports` is installed and at least one
  widget is registered. Without widgets, or with `dashboard_home=False`, `{prefix}/` is unchanged.
- **Widgets bind to registered reports.** `StatWidget(report)` shows one total of a report
  aggregate; `ChartWidget(report)` embeds the report's existing chart fragment
  (`{prefix}/reports/{slug}/chart?embed=1`). `QuickActionsWidget` shows shortcut links. Custom
  widgets subclass `DashboardWidget`. Widgets are declared in code with `register_widget()`, in
  the same way as `register_report()`.
- **Permissions are the reports' permissions.** A report-bound widget is visible only to users
  who hold the report's codename (`view_report_{slug}` by default); a quick action can name its
  own codename. Users never see, load or save a widget they may not view.
- **Per-user order** persists in one plugin-owned table, `hyperadmin_reports_dashboard_layout`,
  on the plugin's own `MetaData`, never on `SQLModel.metadata`. Hosts that do not create the
  table get the default order and no reorder controls; nothing fails.
- **Reorder** by drag and drop (SortableJS, vendored as a static file of the plugin) and by
  "Move up" / "Move down" buttons that work from the keyboard and without JavaScript.
- **Failure isolation.** Every data widget loads in its own HTMX request; a widget that fails
  shows an error state with Retry, and the rest of the page renders.
- **No core data-layer change.** The only core change is one additive plugin seam:
  `PluginRegistry.set_home_page()`.

## Non-Goals

- Widgets bound directly to models (`CountWidget(Order)`, `RecentItemsWidget(Order)`). A model
  count is a `StatWidget` over a report with `Count()`. A "recent records" list needs a core read
  seam over the model views (permission plus `get_queryset` scoping) that does not exist yet; it is
  a follow-up story outside this epic. Hosts can write it today as a custom widget.
- New aggregation API on `BaseAdapter`. `ReportView` already aggregates (`Sum`, `Count`, `Min`,
  `Max`, ...) on any SQLAlchemy model.
- Row scoping (`ModelAdmin.get_queryset`, tenants) inside report-bound widgets. A widget shows what
  its report page shows; reports do not apply row scoping today (`docs/specs/olap-reporting.md`).
- Several dashboards per user, shared or org-wide layouts, a widget configuration UI, resizable
  tiles, per-widget settings stored in the database. The layout row has a `dashboard` column so a
  second dashboard needs no schema change later.
- A server-side render cache. Each widget is a report run; slow reports use `FactTableSource`.
- Live updates over WebSocket, deltas and sparklines on stat cards (the StatCard design's optional
  parts), drill-down.
- Anonymous dashboards. The page sits behind the admin's authentication like every admin page.

## BDD Scenarios

The scenarios of each story are the definition of done; this list is their union.

```
Scenario: dashboard replaces the welcome page when widgets are registered
  Given hyperadmin-reports is installed
  And   a StatWidget over the "orders-revenue" report is registered before Admin(...) is built
  When  a signed-in user opens {prefix}/
  Then  the page contains data-testid "dashboard-grid"
  And   the page does not contain the text "Welcome to HyperAdmin Dashboard"

Scenario: welcome page stays when no widget is registered
  Given hyperadmin-reports is installed and no widget is registered
  When  a signed-in user opens {prefix}/
  Then  the welcome page is shown
  And   the page does not contain data-testid "dashboard-grid"

Scenario: dashboard_home=False keeps the welcome page and adds a sidebar link
  Given widgets are registered and plugin_settings={"reports": {"dashboard_home": False}}
  When  a signed-in user opens {prefix}/
  Then  the welcome page is shown
  And   the sidebar has a "Dashboard" link to {prefix}/dashboard/

Scenario: stat widget shows the grand total of its report aggregate
  Given the "orders-revenue" report sums Order.amount and Orders have amounts 100, 200 and 300
  And   a StatWidget over "orders-revenue" is registered
  When  the dashboard loads
  Then  the card data-testid "stat-orders-revenue" shows "600"
  And   the card links to {prefix}/reports/orders-revenue/

Scenario: stat widget over a report without rows shows an em dash
  Given a StatWidget over "orders-revenue" and no Order rows
  When  the dashboard loads
  Then  the stat card shows "—" and a muted "No data" line

Scenario: chart widget embeds the report chart fragment
  Given a ChartWidget over the chartable report "orders-by-month" is registered
  When  the dashboard loads
  Then  the card loads {prefix}/reports/orders-by-month/chart?embed=1
  And   the card contains data-testid "report-chart"

Scenario: quick actions widget shows only the actions the user may use
  Given a QuickActionsWidget with "New order" (permission add_order) and "All reports" (no permission)
  And   user "viewer" lacks add_order
  When  viewer opens the dashboard
  Then  the widget shows the "All reports" link
  And   the widget does not show the "New order" link

Scenario: widgets the user may not view are not shown
  Given StatWidgets over "orders-revenue" and "payroll-total"
  And   user "viewer" holds view_report_orders_revenue but not view_report_payroll_total
  When  viewer opens the dashboard
  Then  the card "widget-stat-orders-revenue" is shown
  And   the card "widget-stat-payroll-total" is not in the page

Scenario: loading a widget the user may not view is refused
  Given user "viewer" lacks view_report_payroll_total
  When  viewer requests GET {prefix}/dashboard/widgets/stat-payroll-total
  Then  the response is 403

Scenario: user with no visible widgets sees an empty state
  Given widgets are registered and user "viewer" may view none of them
  When  viewer opens the dashboard
  Then  the page shows data-testid "dashboard-empty"

Scenario: failing widget shows an error state and the others render
  Given a custom widget whose render() raises RuntimeError and a StatWidget over "orders-revenue"
  When  the dashboard loads
  Then  the failing card shows data-testid "widget-error" with a Retry button
  And   the card "stat-orders-revenue" shows its value
  And   the error is logged at ERROR with its traceback

Scenario: drag and drop saves the new order
  Given user alice sees widgets in the order [A, B, C]
  When  alice drags C onto the first position
  Then  a POST to {prefix}/dashboard/layout carries widgets=[C, A, B]
  And   after a reload alice sees [C, A, B]

Scenario: move up button reorders without drag and drop
  Given user alice sees widgets in the order [A, B, C]
  When  alice activates "Move up" on B from the keyboard
  Then  the grid shows [B, A, C]
  And   focus stays on B's "Move up" button
  And   after a reload alice sees [B, A, C]

Scenario: layout is per user
  Given alice saved the order [C, A, B]
  When  bob opens the dashboard
  Then  bob sees the default order [A, B, C]

Scenario: reset returns to the default order
  Given alice saved the order [C, A, B]
  When  alice activates "Reset layout"
  Then  alice sees [A, B, C]
  And   alice has no saved layout row

Scenario: saving an order that is not a permutation of the visible widgets is rejected
  Given user alice sees widgets [A, B, C]
  When  POST {prefix}/dashboard/layout with widgets=[A, B, payroll]
  Then  the response is 400
  And   alice's saved order is unchanged

Scenario: saving a layout without a signed-in user is refused
  Given the admin has no authentication configured
  When  POST {prefix}/dashboard/layout with widgets=[A, B, C]
  Then  the response is 403

Scenario: missing layout table hides reordering and keeps the dashboard working
  Given the hyperadmin_reports_dashboard_layout table does not exist
  When  alice opens the dashboard
  Then  the widgets render in the default order
  And   the page has no drag handles and no move buttons
  And   one warning naming the table is logged per admin

Scenario: a widget registered after a layout was saved appears at the end
  Given alice saved [B, A] and widget C is registered later
  When  alice opens the dashboard
  Then  alice sees [B, A, C]

Scenario: second plugin claiming the home page is refused
  Given plugin "reports" already set the admin home page
  When  plugin "other" calls admin.plugins.set_home_page(...) in its on_register
  Then  PluginError is raised and "other" is skipped with reason "register_error"

Scenario: home page endpoint that raises falls back to the welcome page
  Given a plugin home page endpoint that raises RuntimeError
  When  a signed-in user opens {prefix}/
  Then  the welcome page is shown with status 200
  And   the error is logged with the plugin name
```

## Design

### Architecture

```
core (src/hyperadmin)                          plugin (plugins/hyperadmin-reports/src/hyperadmin_reports)
─────────────────────                          ──────────────────────────────────────────────────────────
core/plugins.py  PluginRegistry.set_home_page ◄── plugin.py  ReportsPlugin.on_register
routing.py       GET {prefix}/ ── home_page? ──►     │  (claims the home page when widgets exist)
                   └─ else dashboard.html            ▼
                                               dashboard/routes.py   GET /dashboard/, /widgets/{key},
                                                     │               POST /layout, /layout/move, /reset
                                                     ▼
                                               dashboard/service.py  DashboardService
                                                 │            │
                                                 ▼            ▼
                                     dashboard/widgets.py   dashboard/layout.py
                                     DashboardWidget,       LayoutStore + table on the plugin's MetaData
                                     StatWidget,
                                     ChartWidget,           admin_context.py
                                     QuickActionsWidget ──► session_source(admin), has_permission(...)
                                       │
                                       ▼
                                     view.py ReportView.run()  /  routes.py report-chart fragment
```

Dependency direction: the plugin imports the core (`hyperadmin.core.adapters.open_session`,
`hyperadmin.views.urls.admin_url_for`); the core never imports the plugin. Inside the plugin,
`dashboard/` imports `view.py`, `chart_data.py`, `aggregates.py` and `admin_context.py`;
`routes.py` (reports) never imports `dashboard/`. The plugin's `__init__.py` re-exports the public
widget API.

New and changed files:

```
src/hyperadmin/core/plugins.py              (mod) set_home_page(), home_page, PluginHomePage
src/hyperadmin/routing.py                   (mod) GET {prefix}/ delegates to the home page if set
src/hyperadmin/core/app.py                  (mod) one keyword: pass the home page to HyperAdminRouter

plugins/hyperadmin-reports/src/hyperadmin_reports/
├── admin_context.py      (new) session_source(admin), permission_checker(admin), has_permission()
├── routes.py             (mod) use admin_context instead of its private helpers
├── settings.py           (new) ReportsSettings (plugin settings_model)
├── plugin.py             (mod) settings_model, dashboard page, home page claim, nav entry
├── __init__.py           (mod) re-export the dashboard API
├── dashboard/
│   ├── __init__.py       (new) public names of the subpackage
│   ├── widgets.py        (new) DashboardWidget, WidgetBody, StatWidget, ChartWidget,
│   │                           QuickActionsWidget, QuickAction, the widget registry
│   ├── layout.py         (new) dashboard_metadata(), layout table, LayoutStore,
│   │                           create_layout_table(), LayoutUnavailableError
│   ├── service.py        (new) DashboardService, LayoutRejectedError
│   └── routes.py         (new) build_dashboard_router(admin, settings)
├── templates/dashboard/
│   ├── index.html        (new) page: header, reset button, grid include, scripts
│   ├── _grid.html        (new) the grid (HTMX swap target of move / reset)
│   ├── _card.html        (new) card frame: title, drag handle, move buttons, body slot
│   ├── _stat.html        (new) StatWidget body (StatCard design)
│   ├── _actions.html     (new) QuickActionsWidget body
│   ├── _error.html       (new) error state with Retry
│   └── _forbidden.html   (new) 403 fragment
└── static/hyperadmin_reports/
    ├── dashboard.css     (new)
    ├── dashboard.js      (new) Sortable init + save over htmx.ajax
    ├── vendor/sortable-1.15.6.min.js   (new, vendored, MIT)
    └── vendor/LICENSE-sortablejs.txt   (new)
```

`dashboard/` is a subpackage because it has five files with distinct concerns (CONSTITUTION §1);
it is two levels under the plugin package. `admin_context.py` is named for what it holds: the
plugin's reads of the `Admin` object (session source, permission checker). No module exceeds
~300 LOC by design; `routes.py` (reports) shrinks.

### Data Model Changes

One plugin-owned table, declared with SQLAlchemy Core on a `MetaData` the plugin owns. It is not a
SQLModel table and is never registered on `SQLModel.metadata` or `hyperadmin.auth.metadata()`, so
a host's Alembic autogenerate never sees it unless the host adds it on purpose.

```python
# plugins/hyperadmin-reports/src/hyperadmin_reports/dashboard/layout.py
_metadata = MetaData()

layout_table = Table(
    "hyperadmin_reports_dashboard_layout",
    _metadata,
    Column("id", Integer, primary_key=True),
    Column("user_key", String(255), nullable=False, index=True),   # request.state.user_key, str()
    Column("dashboard", String(64), nullable=False, default="home"),
    Column("widgets", JSON, nullable=False),                       # ordered list of widget keys
    Column("updated_at", DateTime, nullable=False),                # naive UTC, core utc_now()
    UniqueConstraint("user_key", "dashboard", name="uq_hyperadmin_reports_dashboard_layout"),
)

def dashboard_metadata() -> MetaData: ...          # for Alembic target_metadata (opt-in)
async def create_layout_table(bind) -> None: ...   # one-off helper for hosts without Alembic
```

Hosts opt in with `await create_layout_table(engine)` or the hand-written Alembic operation
documented in the plugin README. Without the table the dashboard works in the default order.

Widget configuration lives in code, not in the database. The row stores only the order of keys.

### API / Protocol Changes

**Core seam** (`core/plugins.py`), additive:

```python
HomePageEndpoint = Callable[[Request], Awaitable[Response]]

@dataclass(frozen=True)
class PluginHomePage:
    plugin: str
    endpoint: HomePageEndpoint

class PluginRegistry:
    def set_home_page(self, plugin: Plugin, endpoint: HomePageEndpoint) -> PluginHomePage:
        """Serve ``endpoint`` at the admin index ``{prefix}/`` (one plugin per admin).

        Raises PluginError if another plugin already set it, or outside on_register().
        """
    @property
    def home_page(self) -> PluginHomePage | None: ...
```

It is stored in `_Contributions`, so a plugin whose `on_register` fails loses its claim like its
other contributions. `HyperAdminRouter` receives `home_page: Callable[[], PluginHomePage | None]`
(a lookup, read per request). The `GET {prefix}/` handler (`admin-dashboard`, unchanged name)
awaits `home_page.endpoint(request)` when set; an `HTTPException` propagates, any other exception
is logged (`logger.exception("plugin %r home page raised", ...)`) and the welcome page is
rendered. The endpoint runs inside the admin route, so it has the session, `request.state.user`,
CSRF and the admin error pages. `PluginHomePage` is not added to `hyperadmin.__init__`.

**Plugin public API** (`hyperadmin_reports.__init__`, additive):

```python
class WidgetBody(NamedTuple):
    template: str                     # e.g. "dashboard/_stat.html"
    context: dict[str, Any]

class DashboardWidget(ABC):
    key: str                          # [a-z0-9][a-z0-9_-]*, unique; the layout identity
    title: str
    span: int = 1                     # grid columns, 1..4
    lazy: bool = True                 # True: body loads over HTMX from fragment_url()

    def permission(self) -> str | None: ...          # codename, None = everyone
    def fragment_url(self, request: Request) -> str: # default: dashboard-widget route for key
    def detail_url(self, request: Request) -> str | None: ...  # "Open" link, default None
    @abstractmethod
    async def render(self, request: Request, admin: Any) -> WidgetBody: ...

class StatWidget(DashboardWidget):
    def __init__(self, report: type[ReportView], *, value: str | None = None,
                 key: str | None = None, title: str | None = None, span: int = 1) -> None: ...
    # key "stat-{slug}", title = aggregate label, permission = report.get_permission(),
    # value = aggregate name (default: the report's first aggregate with totals=True),
    # render(): runs the report, folds the aggregate with Aggregate.total(); None -> "—".

class ChartWidget(DashboardWidget):
    def __init__(self, report: type[ReportView], *, key: str | None = None,
                 title: str | None = None, span: int = 2) -> None: ...
    # key "chart-{slug}", fragment_url = report-chart route + "?embed=1", render() unused.

@dataclass(frozen=True)
class QuickAction:
    label: str
    url_name: str                       # resolved in the hyperadmin: namespace
    url_params: Mapping[str, Any] = field(default_factory=dict)
    permission: str | None = None
    icon: str | None = None

class QuickActionsWidget(DashboardWidget):
    lazy = False                        # rendered inline, no query
    def __init__(self, actions: Sequence[QuickAction], *, key: str = "quick-actions",
                 title: str = "Quick actions", span: int = 1) -> None: ...

def register_widget(widget: DashboardWidget) -> DashboardWidget: ...
def unregister_widget(widget: DashboardWidget | str) -> None: ...
def registered_widgets() -> list[DashboardWidget]: ...    # registration order = default order
```

Validation (`ValueError` at construction or `register_widget`, never on the first request): key
not URL-safe or taken by another widget; `span` outside 1..4; the report of a `StatWidget` /
`ChartWidget` not registered with `register_report()` (`get_report(slug) is report`); `value`
naming no aggregate of the report, or an aggregate with `totals=False`; a `ChartWidget` report that
is not `chartable()`. Registering the same instance twice is a no-op. Widgets are registered before
`Admin(...)` is built, as reports are.

**Service** (`dashboard/service.py`):

```python
class DashboardService:
    def __init__(self, admin: Any, store: LayoutStore | None) -> None: ...
    @property
    def can_persist(self) -> bool: ...    # store set and table usable
    async def visible(self, request) -> list[DashboardWidget]: ...   # permission filter
    async def layout_for(self, request) -> list[DashboardWidget]:    # saved order ∩ visible,
        ...                                                          # then new ones in default order
    async def save_order(self, request, keys: Sequence[str]) -> None: ...  # LayoutRejectedError
    async def move(self, request, key: str, direction: Literal["up", "down"]) -> list[DashboardWidget]: ...
    async def reset(self, request) -> None: ...
    async def render_body(self, request, widget) -> WidgetBody: ...  # error isolation lives here
```

**Layout store** (`dashboard/layout.py`): `LayoutStore(engine=None, *, session_factory=None)` with
`load(user_key, dashboard="home") -> list[str] | None`, `save(user_key, keys, dashboard="home")`
(update-or-insert; an `IntegrityError` from a concurrent insert retries as an update, last writer
wins) and `reset(user_key, dashboard="home") -> bool`. A `SQLAlchemyError` from a missing table
raises `LayoutUnavailableError`; the service logs it once per admin and turns persistence off.

**Endpoints** (plugin page at `settings.dashboard_prefix`, default `/dashboard`; route names in the
`hyperadmin:` namespace):

| Method | Path | Name | Response |
|---|---|---|---|
| GET | `{prefix}/` (core) | `admin-dashboard` | the dashboard when the home page is claimed |
| GET | `{prefix}/dashboard/` | `dashboard-index` | the dashboard page; `_grid.html` for HTMX |
| GET | `{prefix}/dashboard/widgets/{key}` | `dashboard-widget` | card body; 404 unknown key; 403 fragment; render errors are a 200 error state |
| POST | `{prefix}/dashboard/layout` | `dashboard-layout` | form field `widgets` (repeated); 204 for HTMX, 303 to the index otherwise; 400 / 403 / 503 |
| POST | `{prefix}/dashboard/layout/move` | `dashboard-layout-move` | fields `key`, `direction`; `_grid.html` for HTMX, 303 otherwise |
| POST | `{prefix}/dashboard/reset` | `dashboard-reset` | `_grid.html` for HTMX, 303 otherwise; idempotent |

All POSTs go through the admin's CSRF guard (the `hx-headers` token on `<body>`, the hidden token
field for plain forms). Views only parse input, call the service and pick a template.

**Front end.** Each lazy card body is `<div hx-get="{{ widget.fragment_url }}" hx-trigger="load"
hx-swap="innerHTML">` with a skeleton (`aria-busy="true"`) and a plain "Open report" link as the
no-JavaScript fallback. `dashboard.js` initialises SortableJS on `[data-dashboard-grid]` with
`handle: "[data-drag-handle]"` and, on `onEnd`, posts the keys in DOM order with
`htmx.ajax("POST", saveUrl, {values: {widgets: keys}, swap: "none"})`. The move buttons are a
`<form method="post">` upgraded with `hx-post` / `hx-target="#dashboard-grid"` /
`hx-swap="outerHTML"`; after the swap the script restores focus to the moved card's same button
and an `aria-live="polite"` region announces "Moved {title} to position {n} of {total}". Drag
handles and move buttons render only when `service.can_persist` and the request has a `user_key`.
Grid: 4 columns from `ha-bp-lg`, 2 from `ha-bp-md`, 1 below; `span` maps to
`grid-column: span min(span, columns)`. Stat cards follow `docs/design/system/components/StatCard`.

New `data-testid`s (added to the CLAUDE.md table): `dashboard-grid`, `dashboard-empty`,
`dashboard-reset`, `widget-{key}` (card), `stat-{key}` (stat value), `widget-error`,
`widget-move-up`, `widget-move-down`, `widget-drag-handle`.

### Configuration Changes

No core `Admin()` or `HyperAdminSettings` changes. The reports plugin gains a `settings_model`:

```python
class ReportsSettings(BaseSettings):        # env prefix HYPERADMIN_REPORTS_
    dashboard_home: bool = True             # serve the dashboard at {prefix}/
    dashboard_layouts: bool = True          # per-user order; False = default order, no controls,
                                            # no table access, no warning
    dashboard_prefix: str = "/dashboard"    # plugin page prefix (rename on a model slug clash)
```

Supplied as `Admin(..., plugin_settings={"reports": {...}})` or environment variables.

Usage:

```python
from hyperadmin_reports import (ChartWidget, QuickAction, QuickActionsWidget, StatWidget,
                                register_report, register_widget)

register_report(OrderRevenueReport)
register_report(OrdersByMonthReport)
register_widget(StatWidget(OrderRevenueReport))
register_widget(ChartWidget(OrdersByMonthReport))
register_widget(QuickActionsWidget([
    QuickAction("New order", "order-create-form", permission="add_order"),
    QuickAction("All reports", "reports-index"),
]))
admin = Admin(app, engine=engine)
```

`ReportsPlugin.on_register` adds the dashboard page, `dashboard.css` / `dashboard.js` (through the
existing static dir) and, only if `registered_widgets()` is non-empty: the home page claim when
`dashboard_home`, else a "Dashboard" nav entry in the "Reports" section (`testid="nav-dashboard"`).

## Edge Cases & Error Handling

| Case | Handling |
|---|---|
| No widget registered | No dashboard route, no home claim; `{prefix}/` is the welcome page |
| Widget registered after `Admin(...)` was built | Not part of that admin's claim decision; documented like `register_report()` |
| Widget `render()` raises | Caught in `render_body`; `_error.html` (200) with Retry (`hx-get` of the same fragment); `logger.exception` with the widget key |
| Chart widget report fails | The report chart fragment's own error state (existing behaviour) |
| Stat aggregate has no rows | `Aggregate.total()` returns `None`; card shows "—" and "No data" |
| User lacks a widget's codename | Widget left out of the page, of `layout_for` and of the accepted save set; direct fragment GET is 403 |
| User may view no widget | `dashboard-empty` state, no reset button |
| No auth configured | Every widget visible (as reports); no `user_key`, so default order, no controls; POSTs answer 403 |
| Layout table missing | `LayoutUnavailableError` logged once per admin at WARNING with the table name; default order; controls hidden; POST `layout` / `move` answer 503 |
| `dashboard_layouts=False` | Store not created; no table access and no warning |
| Saved order names an unknown or no longer visible key | Dropped when rendering; the next save stores the visible keys only |
| Visible widget missing from the saved order | Appended in registration order |
| POST `layout` not a permutation of the visible keys (unknown, hidden, duplicate or missing key) | 400, nothing saved |
| POST `move` with unknown key or bad direction | 400 |
| Move up on the first card / down on the last | No-op, grid re-rendered unchanged |
| Reset without a saved row | No-op, same response |
| Concurrent saves of the same user | Unique `(user_key, dashboard)`; insert race retried as update; last writer wins |
| Plugin prefix clashes with a model slug `dashboard` | Model routes are mounted first and win; set `dashboard_prefix` |
| Second plugin calls `set_home_page` | `PluginError`; that plugin is skipped (`register_error`), the first keeps the page |
| Home endpoint raises a non-HTTP exception | Core logs it with the plugin name and renders the welcome page |
| `user_key` is not a string | Stored as `str(user_key)` (as pins and saved views) |
| Duplicate widget key / bad span / unregistered report / non-totalling aggregate / non-chartable report | `ValueError` at construction or registration |
| JavaScript disabled | Inline widgets render; lazy cards show the "Open report" link; move and reset work as plain form posts with 303 |

## Migration & Backward Compatibility

- **No breaking change.** `PluginRegistry.set_home_page()` / `home_page` are additive; the core
  `GET {prefix}/` route keeps its name and renders the welcome page unless a plugin claims it.
- **No migration forced on hosts.** The layout table is on the plugin's own `MetaData`; hosts
  create it only if they want saved orders (`create_layout_table()` or the README's Alembic
  operation). Upgrading `hyperadmin-reports` without registering widgets changes nothing.
- **No new runtime dependency.** SortableJS 1.15.6 (MIT) is vendored as a static file of the
  plugin with its licence, like htmx and Alpine in the core; no Python dependency changes.
- **Reports plugin internals:** `routes.py` moves `_permission_checker` / `_session_source` into
  `admin_context.py`; `can_view()` keeps its signature.

## Open Questions

None. All questions are resolved in the Decision Log.

## Decision Log

| Decision | Rationale | Alternatives considered |
|---|---|---|
| (rev 2) Dashboard lives in the `hyperadmin-reports` plugin, subpackage `dashboard/` | The milestone defines it as the layer over `ReportView`; its data widgets need the report registry, aggregates and chart fragment; keeps the core free of a feature it cannot fill without the plugin | Core `src/hyperadmin/dashboard/` (the rev 1 design; the core would import or duplicate report logic); a new `hyperadmin-dashboard` plugin (new workspace member, CI and release unit for a thin layer that only works with reports installed) |
| (rev 2) One additive core seam `PluginRegistry.set_home_page()`; core `GET {prefix}/` delegates per request, falls back to the welcome page | The landing page is core-owned; plugin templates are searched after core ones, so a plugin cannot override `dashboard.html`; a seam is the conflict-avoidance answer | Redirect `{prefix}/` to `{prefix}/dashboard/` (changes the URL people bookmark, and still needs a core hook); host template override (manual, per host) |
| (rev 2) Widgets bind to registered reports: `StatWidget` folds a report aggregate with `Aggregate.total()`, `ChartWidget` embeds `report-chart?embed=1` | Reuses the shipped query, totals, permission and chart states; one source of truth for every number on the page | Widget-level query builders (duplicate `ReportView`); `count()` / `aggregate()` on `BaseAdapter` (rev 1) |
| (rev 2) Supersede story #459 (`count()` / `aggregate()` on `BaseAdapter`) | `ReportView` aggregates cover sum, count, min, max on every SQLAlchemy model; `adapter.list()` already returns totals; a core adapter API with no caller is surface to maintain | Keep it for custom widgets (no caller in this epic; add when a core feature needs it) |
| (rev 2) No model-bound widgets in this epic (`CountWidget`, `RecentItemsWidget`) | A model count is a `StatWidget` over `Count()`; a recent-records list needs a core read seam over model views (permission + `get_queryset`) that is out of scope; hosts can write it as a custom widget | A plugin-side query re-implementing model-view permission and row scoping (duplicated security logic); adding the core seam here (widens the epic into `views/dynamic/`) |
| (rev 2) Widget permissions = report codenames; quick actions name their own; hidden widgets are not rendered, loaded or saved | Same rule as the reports pages and nav entries, no new permission rows; a dashboard must not disclose a number its report page would refuse | One `view_dashboard` codename (coarser than the data); render hidden widgets as locked cards (leaks that the report exists) |
| (rev 2) Report-bound widgets do not apply `get_queryset` row scoping | Matches the reports pages today; scoping reports is a reports-plugin feature for every surface at once | Scope only the dashboard (the same number would differ between the card and its report) |
| (rev 2) Layout table `hyperadmin_reports_dashboard_layout` on the plugin's own `MetaData`, opt-in, missing table degrades | Hosts are never pushed into a migration by an upgrade; the degrade path copies pins / saved views (warn once, hide the feature) | SQLModel table on `SQLModel.metadata` like pins (shows up in every host's autogenerate as soon as the plugin is imported); reuse `hyperadmin_saved_view` with a fake model slug (overloads a table with a different meaning); cookie / localStorage (lost per device, not per user) |
| (rev 2) Row stores only the ordered widget keys; `dashboard` column fixed to `"home"` | Widget config stays typed in code; the column lets a second dashboard come without a schema change | One row per widget (rev 1 `WidgetConfig`; more writes per reorder, config drift in the DB); no column (later migration) |
| (rev 2) Each data widget loads in its own HTMX request | Failure and latency isolation for free; the page shell renders at once; the chart fragment already works this way | Server-side `asyncio.gather` render of every widget (one slow report delays the page; rev 1 story #460) |
| (rev 2) Drag and drop with SortableJS 1.15.6 vendored as a plugin static file, plus move-up / move-down buttons | Project rule: HTMX, no JS build step, vendored libraries; Sortable has no keyboard model, so buttons give keyboard and no-JS reordering (WCAG 2.1.1) | `@alpinejs/sort` (rev 1; an Alpine plugin must load before Alpine core in `_base.html`, a core hotspot); hand-written HTML5 DnD (no touch support); CDN script (rev 1 story #466; violates the vendoring rule and CSP) |
| (rev 2) Save the full order (`POST layout`) for drag, a relative `POST layout/move` for buttons | Drag knows the final order; buttons work as plain forms without JS | One endpoint taking the full order from the buttons too (needs JS to compute it) |
| (rev 2) Settings on the plugin (`ReportsSettings`: `dashboard_home`, `dashboard_layouts`, `dashboard_prefix`), not on `HyperAdminSettings` | The feature belongs to the plugin; typed plugin settings exist for this (`plugin-registry.md`); no core hotspot edit | `HyperAdminSettings.dashboard_*` and `Admin(dashboard=..., widgets=...)` (rev 1 / story #468; core API for a plugin feature) |
| (rev 2) Widgets are registered in code with `register_widget()` before `Admin(...)`; registration order is the default order | Mirrors `register_report()`, which the same hosts already use | `Admin(widgets=[...])` (core signature change); `settings.default_widgets` as dicts (stringly typed) |
| (rev 2) No server-side render cache | Each widget is one report query; `FactTableSource` is the reports' answer to slow queries; avoids per-user/tenant cache-key design | Per-widget in-process TTL cache (rev 1; cache key and invalidation design for little gain) |
| (rev 2) Grid of 4 / 2 / 1 columns with `span` 1..4 | Matches the StatCard design (at most four in a row); invalid spans fail at registration | 12-column grid with `grid_span` (rev 1; finer than any widget needs) |
| (rev 1, kept) Widget config in code, not in the database | Typed and refactorable; avoids an admin-of-the-admin UI | Persist widget configs as JSON |
| (rev 1, kept) Widget render failure is isolated to that widget | One bad widget must not blank the dashboard | Hard fail |
| (rev 1, kept) Reset endpoint | Lets users escape a bad order | No reset |
| (rev 1, kept) Server-rendered HTML fragments | HTMX-first stack | JSON plus a client renderer |
| (rev 1, superseded) `dashboard/` package in the core, `Admin(dashboard=True, widgets=[...])`, `BaseAdapter.count()` / `aggregate()`, `hyperadmin_dashboard_layouts` on `SQLModel.metadata`, `@alpinejs/sort`, in-process render cache | Replaced by the rev 2 rows above after reports moved into a plugin (2026-10-18) | — |
