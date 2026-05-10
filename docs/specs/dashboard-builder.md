# SDD: Dashboard Builder with Widgets

| Field | Value |
|---|---|
| Author | Claude Code |
| Status | Draft |
| Issue | #422 (epic), #455 (review gate) |
| Milestone | v0.5.4 — Dashboard Builder |
| Created | 2026-05-10 |
| Last updated | 2026-05-10 |

---

## Problem

`Admin(app)` mounts a static welcome page at `/admin/`. There is no way to surface
operational insight on the landing page — counts, recent items, quick actions, alert
panels — and no way for users to customise what they see when they open the admin.

This forces every host application to either:

1. Live with the welcome page and link to a custom-built dashboard elsewhere, or
2. Override the entire `/admin/` route, losing the framework's auth/MFA/i18n wiring.

A first-class dashboard builder is also a prerequisite for several deferred niceties:
real-time count updates over WebSocket (v0.6.0), per-tenant homepages (v0.5.3), and the
plug-in marketplace direction in v0.8.0. The SDD scopes the **MVP** — composable widgets,
drag-drop reordering, and persisted layout — without overpromising charts, dashboards-as-
code, or live-updating tiles.

## Goals

- **Widget protocol.** A `DashboardWidget` Protocol with one async `render(request)`
  method returning an HTML fragment. Built-in widgets (count, recent items, quick actions)
  are implementations.
- **Layout persistence.** Per-user layout stored as `DashboardLayout` (user_id, name,
  widgets JSON). Replaces the welcome page when `Admin(dashboard=True)`.
- **Drag-drop reordering** via `@alpinejs/sort` (no new dependency — Alpine is already
  loaded by v0.4.0). Persisted via HTMX `POST` returning `204 No Content`.
- **Aggregation helpers.** `BaseAdapter.count(filter)` and `BaseAdapter.aggregate(field,
  op, filter)` where `op ∈ {"sum","avg","min","max"}`. Both honour
  `get_queryset()` filters (so v0.5.3 multi-tenancy applies automatically).
- **Server-side render cache.** Per-widget render output cached for `dashboard_cache_ttl_seconds`
  (default `60`, `0` disables). Keyed by `(user_id, tenant_id, widget_id)`.
- **i18n.** Widget titles wrap in `gettext_lazy`; built-in widget labels translate via the
  v0.4.1 catalog pipeline.
- **A11y.** Tab order follows visual order; drag-drop has keyboard fallback (move-up /
  move-down buttons reachable via `Tab`).
- **Tenant-scoped.** When v0.5.3 is enabled, layouts and widget data are filtered by tenant
  through the same `get_queryset()` seam — no special-casing.
- **Backward compatible.** `Admin(dashboard=False)` (default) ⇒ welcome page unchanged.

## Non-Goals

- Charts, sparklines, time-series. Built-in widgets are textual / list-based; chart widgets
  are user-supplied subclasses (or v0.8.0 plugin).
- Dashboard-per-page (multiple dashboards). Layout has a `name` field for forward
  compatibility but the MVP renders one named `"default"`.
- Drilldown modals, widget-specific configuration UI. Widgets are configured in code.
- Cross-user / org-wide shared dashboards. Each user owns their layout. (Sharing is a
  later epic.)
- Custom SQL widgets in the UI. Custom widgets are Python subclasses.
- Live data refresh via WebSocket. v0.6.0 adds a separate `LiveCountWidget` mixin.
- Public dashboards (anonymous viewers). Dashboards always require authentication.
- Widget size/layout primitives beyond a 12-column grid (no resizable tiles in MVP).

## BDD Scenarios

```
Scenario: dashboard renders when enabled
  Given Admin(dashboard=True) is configured with built-in widgets
  When  the user navigates to /admin/
  Then  the response renders the dashboard layout
  And   the page contains data-testid "dashboard-grid"
  And   the welcome page is NOT rendered

Scenario: dashboard is disabled by default
  Given Admin(dashboard=False) (default)
  When  the user navigates to /admin/
  Then  the response renders the welcome page
  And   the page does NOT contain data-testid "dashboard-grid"

Scenario: count widget renders the model count
  Given a CountWidget(model=Order) is registered
  And   there are 42 Order rows visible to the user
  When  the dashboard renders
  Then  the count widget shows "42"
  And   the widget container has data-testid "widget-count-order"

Scenario: count widget respects tenant filter
  Given v0.5.3 is enabled with Order.tenant_field="tenant_id"
  And   request.state.tenant_id = 1
  And   there are 5 Order rows for tenant 1 and 100 for tenant 2
  When  the dashboard renders
  Then  the count widget shows "5"

Scenario: recent items widget renders the n most recent rows
  Given a RecentItemsWidget(model=Order, n=3) is registered
  And   there are 10 Order rows
  When  the dashboard renders
  Then  the widget shows the 3 most recent items
  And   each item links to its detail page

Scenario: quick actions widget renders configured actions
  Given a QuickActionsWidget(actions=[("Create Order", "/admin/order/create"),
                                       ("View Reports", "/admin/reports")]) is registered
  When  the dashboard renders
  Then  the widget shows two action links with the correct hrefs

Scenario: drag-drop persists new widget order
  Given the user has widgets ["count-order", "recent-orders", "quick-actions"]
  When  the user drags "quick-actions" to the first position
  Then  the dashboard issues a POST to /admin/dashboard/layout
  And   the response is 204 No Content
  And   on next navigation the widget order is ["quick-actions", "count-order", "recent-orders"]

Scenario: layout is per-user
  Given alice has reordered her dashboard
  When  bob navigates to /admin/
  Then  bob sees the default order, not alice's order

Scenario: cached widget output is reused within TTL
  Given dashboard_cache_ttl_seconds = 60
  And   a CountWidget(model=Order) was rendered 30 seconds ago
  When  the same user reloads the dashboard
  Then  the widget renders from cache without invoking adapter.count()

Scenario: cache key partitions by user and tenant
  Given dashboard_cache_ttl_seconds = 60
  And   alice (tenant 1) just rendered the count widget
  When  bob (tenant 2) renders the same widget
  Then  adapter.count() is invoked again (different cache key)

Scenario: keyboard reorder works without drag-drop
  Given the user focuses the move-up button on the second widget
  When  the user presses Enter
  Then  the widget moves up by one position
  And   the new order is persisted

Scenario: aggregate helper computes sums over filtered rows
  Given Orders has rows with total in {10, 20, 30, 40} and tenant_id in {1, 1, 2, 2}
  And   request.state.tenant_id = 1
  When  adapter.aggregate("total", "sum") is called
  Then  the result is 30

Scenario: layout reset returns to defaults
  Given alice has a customised layout
  When  alice POSTs /admin/dashboard/reset
  Then  alice's DashboardLayout row is deleted
  And   the next dashboard render uses the configured default order

Scenario: missing widget id in saved layout is skipped gracefully
  Given alice's layout references widget "deprecated-widget"
  And   "deprecated-widget" is no longer registered
  When  the dashboard renders
  Then  the unknown widget is omitted
  And   no exception is raised
  And   a warning is logged once per process

Scenario: widget render failure isolates to that widget
  Given a custom widget raises in render()
  When  the dashboard renders
  Then  the failing widget shows an error placeholder with the widget id
  And   other widgets render normally
  And   the error is logged at ERROR with traceback
```

## Design

### Architecture

```
                  /admin/  (when dashboard=True)
                       │
                       ▼
               views/dashboard.py
                       │
                       ▼
            dashboard/service.py
                       │
            ┌──────────┴────────────┐
            ▼                       ▼
   dashboard/registry.py     core/cache.py (request-scoped LRU)
       │                            │
       ▼                            │
   widgets registered  ─────────────┘
   (CountWidget, RecentItemsWidget,
    QuickActionsWidget, custom)
            │
            ▼
   adapter.count() / adapter.aggregate() / adapter.list()
            │
            ▼
   get_queryset()  ←  v0.5.1 / v0.5.3 hooks (tenant filtering applies here)
```

Module layout:

```
src/hyperadmin/dashboard/
├── __init__.py          — public exports
├── models.py            — DashboardLayout SQLModel
├── protocols.py         — DashboardWidget Protocol
├── widgets.py           — CountWidget, RecentItemsWidget, QuickActionsWidget
├── registry.py          — WidgetRegistry, widget id resolution
├── service.py           — DashboardService (load, render, save, reset)
└── cache.py             — Per-process LRU + TTL keyed render cache

src/hyperadmin/views/
└── dashboard.py         — handler endpoints

src/hyperadmin/core/
├── adapters.py          — (mod) add count(), aggregate() to BaseAdapter
└── settings.py          — (mod) add dashboard config

src/hyperadmin/adapters/
├── sqlmodel.py          — (mod) implement count(), aggregate()
└── sqlalchemy.py        — (mod) implement count(), aggregate()

src/hyperadmin/templates/dashboard/
├── grid.html            — overall grid + sortable wiring
├── widget_card.html     — wrapper card with title + actions
├── widget_count.html    — count widget body
├── widget_recent.html   — recent items widget body
├── widget_actions.html  — quick actions widget body
└── widget_error.html    — error placeholder
```

Dependency direction: `dashboard/` → `core/` → `adapters/`. No reverse imports.
`views/dashboard.py` is the only `views/` consumer.

### Data Model Changes

Single new framework table:

```python
# src/hyperadmin/dashboard/models.py
class DashboardLayout(SQLModel, table=True):
    __tablename__ = "hyperadmin_dashboard_layouts"

    id: int | None = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="hyperadmin_users.id", index=True)
    name: str = Field(default="default", max_length=64)
    widgets: list[str] = Field(default_factory=list, sa_column=Column(JSON))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))

    __table_args__ = (UniqueConstraint("user_id", "name", name="uq_layout_user_name"),)
```

`widgets` is the ordered list of widget ids. Width / row spans are deferred — every widget
defaults to a 4-of-12 grid column on desktop, full-width on mobile.

`WidgetConfig` is **not** persisted as a row — widget configuration lives in code (Python),
not in the DB. Persisting it would invite a half-baked admin-UI-for-widget-configuration
that the MVP explicitly excludes.

### API / Protocol Changes

**`DashboardWidget` Protocol** in `dashboard/protocols.py`:

```python
@runtime_checkable
class DashboardWidget(Protocol):
    id: str
    title: str | LazyString
    grid_span: int  # 1..12, default 4

    async def render(self, request: Request) -> str:
        """Return the inner HTML for this widget. Wrapped by widget_card.html."""
```

**Built-in widgets** in `dashboard/widgets.py`:

```python
class CountWidget:
    def __init__(self, model: type[SQLModel], *, title: str | None = None,
                 filter: dict[str, Any] | None = None, grid_span: int = 3) -> None: ...

class RecentItemsWidget:
    def __init__(self, model: type[SQLModel], *, n: int = 5,
                 order_by: str = "-id", grid_span: int = 6) -> None: ...

class QuickActionsWidget:
    def __init__(self, actions: list[tuple[str, str]], *, grid_span: int = 3) -> None: ...
```

**Adapter additions** on `BaseAdapter`:

```python
async def count(self, filter: dict[str, Any] | None = None,
                request: Request | None = None) -> int: ...

async def aggregate(self, field: str, op: Literal["sum","avg","min","max"], *,
                    filter: dict[str, Any] | None = None,
                    request: Request | None = None) -> int | float | None: ...
```

Both honour `get_queryset(request)` — the request-scoped filter is merged on top of the
caller-supplied `filter` (caller wins on key conflict for dashboard widgets that need to
override). `count()` exists in v0.5.1's count-for-pagination path; this exposes it on the
public surface.

**`DashboardService`** in `dashboard/service.py`:

```python
class DashboardService:
    def __init__(self, registry: WidgetRegistry, cache: WidgetCache,
                 layout_repo: LayoutRepository) -> None: ...

    async def render_for(self, request: Request) -> str: ...
    async def save_layout(self, request: Request, widget_ids: list[str]) -> None: ...
    async def reset_layout(self, request: Request) -> None: ...
```

**Endpoints** registered when `dashboard=True`:

| Method | Path | Purpose |
|---|---|---|
| GET  | `/admin/`                   | Render dashboard (replaces welcome page) |
| POST | `/admin/dashboard/layout`   | Save reordered widget list |
| POST | `/admin/dashboard/reset`    | Delete user's saved layout |

**Public exports** added to `hyperadmin.__init__`:

```python
from hyperadmin.dashboard import (
    DashboardWidget,
    CountWidget,
    RecentItemsWidget,
    QuickActionsWidget,
    DashboardLayout,
)
```

### Configuration Changes

```python
# HyperAdminSettings additions
dashboard_enabled: bool = False
dashboard_cache_ttl_seconds: int = 60
dashboard_default_widgets: list[str] = []   # widget ids in default order
```

```python
# Admin(...) additions
admin = Admin(
    app,
    dashboard=True,
    widgets=[
        CountWidget(Order, title=_("Orders")),
        RecentItemsWidget(Order, n=5),
        QuickActionsWidget(actions=[(_("New Order"), "/admin/order/create")]),
    ],
)
```

The `widgets=` kwarg is the ordered default. `Admin.__init__` registers each into the
`WidgetRegistry` and seeds `dashboard_default_widgets` if the host did not already set it
in settings.

## Edge Cases & Error Handling

| Case | Handling |
|---|---|
| Widget render raises | Caught per-widget; `widget_error.html` shows widget id + minimal error; logged at ERROR |
| Widget id collision | Registry refuses second registration with `ValueError` at startup |
| Layout references unknown widget id | Silently skipped at render; warning logged once per id per process |
| User has no `DashboardLayout` row | Default order used (from `dashboard_default_widgets`) |
| Drag-drop POST receives unknown widget id | 400 Bad Request — never accept ids the server didn't render |
| Drag-drop POST receives a different number of widgets than registered | 400 Bad Request |
| `reset_layout` for a user with no row | Idempotent — no-op, 204 |
| `count()`/`aggregate()` on adapter without backend support | Raise `NotImplementedError`; widget renders error placeholder |
| Cache-key collision between sessions | Keyed by `(user_id, tenant_id or "_", widget_id)`; collisions impossible |
| Tenant changes mid-session (admin switches tenant via header) | Cache key includes tenant id, so stale data is impossible |
| `dashboard_cache_ttl_seconds=0` | Cache disabled; every render hits the adapter |
| Widget grid_span > 12 | Clamped to 12 with a `WARN` at registration |
| Widget grid_span < 1 | Clamped to 1 with a `WARN` |
| HTMX request without `hx-request` header | Endpoint accepts plain POST (curl-friendly), returns 204 |
| Anonymous user lands on `/admin/` | Existing auth middleware redirects to login — dashboard never renders |
| Layout reset while drag-drop POST is in flight | Last-writer-wins on `(user_id, name)` unique key |
| `default` layout name conflict with user-renamed layouts | Layout name is fixed to `"default"` in MVP — multi-name support is forward-only |

## Migration & Backward Compatibility

- **No breaking changes.** Default `dashboard=False` preserves the welcome page.
- **DB migration owned by host app:** add `hyperadmin_dashboard_layouts`. Documented in
  changelog.
- **Public API is additive.** `__init__.py` gains widget classes and `DashboardLayout`.
- **Adapters.** `count()` / `aggregate()` are new; default `BaseAdapter` raises
  `NotImplementedError`. SQLModel and SQLAlchemy adapters implement both. Third-party
  adapters keep working until a widget calls these methods — at which point they raise
  cleanly with a clear error.

## Open Questions

- [x] Where does cache live? → **In-process `LRU` keyed by `(user_id, tenant_id,
      widget_id)` with TTL.** No Redis required for MVP. Multi-worker deployments will see
      duplicate hits (acceptable — TTL is short).
- [x] Resizable tiles? → **Defer.** A 12-column grid with widget-declared `grid_span` is
      enough for MVP.
- [x] Multiple dashboards per user? → **Defer.** Layout name field exists; only `"default"`
      is rendered.
- [x] Live count updates? → **Defer to v0.6.0.** A `LiveCountWidget` mixin will subscribe
      to model-change events when WebSocket pubsub lands.
- [x] How are widget instances identified for layout persistence? → **`widget.id`.** Auto-
      generated as `f"{class_name.lower()}-{model.__tablename__}"` for built-ins; custom
      widgets must set an explicit `id`.
- [ ] Should dashboard widgets honour object-level permission checks? → **Yes**, count and
      list widgets must use `adapter.count(request=request)` so the v0.5.1 `get_queryset()`
      hook applies. Object-level checks fire on detail navigation as today. Resolved on
      approval — already implicit in the design.
- [ ] Cache invalidation on writes? → **No** in MVP. TTL is the only invalidation. Real-
      time invalidation arrives with v0.6.0 model-change signals. Resolved on approval.

## Decision Log

| Decision | Rationale | Alternatives considered |
|---|---|---|
| Widget config in code, not DB | Avoids half-built admin-of-the-admin UI; widgets are typed, refactorable | Persist widget configs as JSON — invites stringly-typed configuration; widgets-as-records — same problem |
| Single `default` dashboard per user | YAGNI for MVP; layout name field future-proofs | Ship multi-dashboard now — extra UI surface, marginal value |
| `@alpinejs/sort` for drag-drop | Alpine already loaded; zero new JS | SortableJS — extra dep; HTML5 DnD — fragile UX |
| Per-widget render cache (in-process) | Simple, no Redis dep; TTL-bounded | Centralised cache (Redis) — adds infra; per-template HTTP cache headers — coarse |
| Cache key includes tenant id | v0.5.3 multi-tenancy correctness | User-only key — would leak across tenant in multi-tenant admin |
| Widget render failure isolated | One bad widget shouldn't blank the dashboard | Hard fail — too brittle |
| `count()` and `aggregate()` on `BaseAdapter` | Generic operations every adapter can support | Dashboard-specific adapter mixin — duplicates work |
| Adapter default raises `NotImplementedError` | Third-party adapters keep working until a widget that needs aggregation lands | Make required — breaking change |
| Layout reset endpoint | Lets users escape a bad customisation | No reset — power users would have to manually edit JSON |
| Replace `/admin/` only when `dashboard=True` | Existing apps see no behaviour change | Always replace — would surprise upgrade users |
| Widget grid uses 12-column layout | Common, well-understood, maps to existing CSS grid | 16-column / 24-column — no benefit; flex-only — too freeform |
| Server-rendered HTML over JSON-rendered widgets | Aligns with HTMX-first stack; widgets compose easily | JSON + client renderer — couples to a JS framework |
