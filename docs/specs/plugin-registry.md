# SDD: Plugin Registry, UI Extension Seams & Lifecycle Hooks

| Field | Value |
|---|---|
| Author | Claude Code |
| Status | In review (revision 2) |
| Issue | TBD |
| Milestone | Pulled forward ahead of v0.8.0 — prerequisite for the `hyperadmin-reports` plugin |
| Created | 2026-05-05 |
| Last updated | 2026-10-18 |

---

## Problem

HyperAdmin has no extension surface. The only hooks are model-level
(`HyperAdminModel.before_save / after_save / before_delete / after_delete`) and
adapter-level (`BaseAdapter.get_queryset(request)`). There is no app-level lifecycle,
no entry-point discovery, no `Plugin` contract — and no way for a package to add
**pages, sidebar entries, templates, static files or permissions** to the admin.

The last point became urgent on 2026-10-18: OLAP reporting (`docs/specs/olap-reporting.md`)
and the SVG charts (`docs/specs/chart-components.md`) leave core and ship as the first-party
plugin **`hyperadmin-reports`** (in-repo uv workspace member `plugins/hyperadmin-reports/`,
published to PyPI as its own distribution). Not every admin needs reports, so they should
not weigh on every install. That plugin needs UI seams, not CRUD hooks, so the plugin system
moves ahead of v0.8.0 and the UI seams become its first deliverable.

Other consumers, unchanged from revision 1:

- **`hyperadmin-logfire`** (RFC #276) — the second plugin; needs `on_before_adapter_call` /
  `on_after_adapter_call` to wrap CRUD spans without monkey-patching.
- **Future ORM adapters, AI features, community plugins** — need a stable, discoverable place
  to attach without a fork.
- **Per-deployment customisation** — audit logging, telemetry without modifying core.

## Goals

1. **Entry-point discovery** — packages declare `[project.entry-points."hyperadmin.plugins"]`;
   the admin discovers them via `importlib.metadata.entry_points(group="hyperadmin.plugins")`.
2. **`Plugin` protocol** — runtime-checkable Protocol (`name`, `on_register(admin)`, optional
   hook methods, optional `settings_model`). No inheritance from HyperAdmin required.
3. **UI extension seams** (phase 1) — from `on_register(admin)` a plugin can contribute:
   pages (routers in the admin sub-app), sidebar entries, template search paths, a static
   directory, permission codenames, and typed settings.
4. **Disable mechanism** — `Admin(disabled_plugins=[...])` and `HYPERADMIN_DISABLED_PLUGINS`
   (comma-separated), unioned.
5. **Failure isolation** — a plugin that fails to import, validate settings, register or run a
   hook is logged at ERROR and skipped; the admin and the request keep working.
6. **App-level lifecycle hooks** (phase 2, v0.8.0) — `on_model_register`, `on_before/after_create`,
   `on_before/after_update`, `on_before/after_delete`, `on_before/after_adapter_call`. The
   dispatcher ships in phase 1; firing them from core call sites ships with logfire.
7. **CLI introspection** (later story) — `hyperadmin plugins list`.

## Non-Goals

- **Plugin scaffold CLI (`hyperadmin create-plugin`)** — RFC #275, tracked separately.
- **Hot-reload of plugins** — restart required.
- **Sandboxing / capability restrictions** — plugins are trusted code the operator installed.
- **Async hooks** — sync fan-out only (see Decision Log).
- **Plugins overriding core templates** — see "Template search paths".
- **Versioned plugin API surface** — the public seam/hook list is the API; additive changes
  freely, removals only with a semver major.

## Phasing

| Phase | Scope | Delivered by |
|---|---|---|
| 1a — `plug-core` | `core/plugins.py`: `Plugin`, `PluginRegistry` (discovery, disable, isolation, ordering), seam *registration* API + data structures, `dispatch_hook`, typed settings. Unit tests only. | this SDD's first PR |
| 1b — `plug-wire` (gated on v0.5.8 BYOA) | `Admin` calls discovery; mounts pages + static; adds template dirs to the Jinja env; renders nav entries in the sidebar; syncs plugin permissions; `admin.plugins`, `admin.dispatch_hook`; exports from `hyperadmin`. E2E with a fixture plugin. | follow-up PR |
| 1c — `hyperadmin-reports` | First plugin, uses only phase-1 seams. | reports swarm items |
| 2 — v0.8.0 | Fire lifecycle hooks from `SiteRegistry` / `DynamicModelView`; `_AdapterHookWrapper`; `hyperadmin-logfire`; `hyperadmin plugins list`. | v0.8.0 epics |

## BDD Scenarios

```
Scenario: plugin discovered via entry point on Admin construction
  Given a package "demo_plugin" exposes [project.entry-points."hyperadmin.plugins"] demo = "demo_plugin:DemoPlugin"
  When  Admin(app, engine=engine) is constructed
  Then  admin.plugins["demo"] is an instance of DemoPlugin
  And   demo.on_register(admin) was called exactly once

Scenario: disabled plugin is not loaded
  Given the same demo_plugin is installed
  When  Admin(app, engine=engine, disabled_plugins=["demo"]) is constructed
  Then  "demo" is not in admin.plugins
  And   DemoPlugin.on_register was not called

Scenario: plugin page is served inside the admin
  Given plugin "reports" calls admin.plugins.add_page(self, router) with GET "/" named "reports-index"
  When  a signed-in staff user requests GET {prefix}/reports/
  Then  the response is 200 and rendered with the admin session and HyperAdminRoute error pages
  And   url_for("hyperadmin:reports-index") resolves to {prefix}/reports/

Scenario: plugin nav entry appears in the sidebar for permitted users only
  Given plugin "reports" adds a nav entry "Reports" with permission "view_report_sales"
  When  a user with that permission opens the dashboard
  Then  the sidebar shows a "Reports" link
  And   a user without it does not see the link

Scenario: plugin static file is served under its own path
  Given plugin "reports" sets a static dir containing "charts.css"
  When  GET {prefix}/static/plugins/reports/charts.css
  Then  the response is 200

Scenario: plugin permission shows in the permission system
  Given plugin "reports" declares "view_report_sales"
  When  the admin starts and permissions are synced
  Then  "view_report_sales" can be assigned to a group

Scenario: broken plugin does not break the admin
  Given plugin "broken" raises in on_register after adding a page
  When  the admin starts
  Then  "broken" is not in admin.plugins and its page is not mounted
  And   an ERROR log record names plugin "broken" and hook "on_register"

Scenario: hook exception is logged and does not break the request   (phase 2)
  Given a plugin's on_after_update hook always raises RuntimeError
  When  POST /admin/products/1/update with valid data
  Then  the response is 302 (success redirect)
  And   a structured log record at level ERROR mentions the plugin name and the hook

Scenario: adapter call hooks wrap every CRUD operation   (phase 2)
  Given a plugin records (op, model) tuples in on_before_adapter_call / on_after_adapter_call
  When  the list, create, update, delete views are exercised once each for Product
  Then  the recorded tuples include ("list","Product"), ("create","Product"), ("update","Product"), ("delete","Product") in order

Scenario: hyperadmin plugins list CLI prints discovered plugins   (later)
  Given demo_plugin is installed
  When  the user runs `hyperadmin plugins list`
  Then  stdout contains "demo" and the plugin's class path
```

## Design

### Architecture

`src/hyperadmin/core/plugins.py` is a leaf: no HTTP, no ORM, no imports from `views/`,
`adapters/` or `auth/` (CONSTITUTION: `core/` holds contracts and registries). The registry
**collects** contributions; `Admin` (phase 1b) **applies** them.

```
entry_points(group="hyperadmin.plugins")
        │  sorted by (name, value)
        ▼
PluginRegistry.discover(admin=, disabled=, settings=)          core/plugins.py
  ├─ skip disabled (ctor ∪ env)  ├─ load (class → instance)  ├─ validate settings_model
  └─ plugin.on_register(admin) ──► admin.plugins.add_page / add_nav_entry / add_template_dir
                                   / set_static_dir / add_permission   (collected, attributed)
        │ pages, nav_entries, template_dirs, static_dirs, permissions
        ▼
Admin (phase 1b, core/app.py) mounts routers + static, extends Jinja loader,
renders nav, syncs permissions; higher layers call admin.dispatch_hook(...) (phase 2)
```

### Plugin contract

```python
@runtime_checkable
class Plugin(Protocol):
    name: str                                  # == entry-point name; ^[a-z][a-z0-9_-]*$
    def on_register(self, admin: Admin) -> None: ...

# optional: settings_model: type[pydantic.BaseModel]
# optional: lifecycle hook methods (phase 2), e.g. def on_after_create(self, *, admin, model, instance)
```

The entry point may point at a class (instantiated with no arguments) or an instance.
`plugin.name` must equal the entry-point name; the entry-point name is the plugin's identity
(used in URLs, static paths, settings keys, logs, the disable list).

### Registry API (phase 1a)

```python
class PluginRegistry:
    @classmethod
    def discover(cls, *, admin, disabled: Iterable[str] = (),
                 settings: Mapping[str, Mapping[str, Any]] | None = None) -> PluginRegistry
    def register(self, plugin, *, admin, settings=None, origin=None) -> bool   # manual / tests
    # mapping-like
    __contains__, __getitem__, __bool__, __len__, names() -> list[str]
    origin(name) -> str            # entry-point value, for the CLI
    skipped -> dict[str, "disabled" | "load_error" | "invalid" | "register_error"]
    settings(name) -> BaseModel | None
    # UI seams — callable only from the calling plugin's own on_register()
    add_page(plugin, router, *, prefix=None) -> PluginPage
    add_nav_entry(plugin, *, label, url_name, icon=None, permission=None,
                  section=None, order=0, url_params=None) -> NavEntry
    add_template_dir(plugin, path) -> PluginTemplateDir
    set_static_dir(plugin, path) -> PluginStaticDir
    add_permission(plugin, codename, name=None) -> PluginPermission
    # collected (consumed by Admin)
    pages, nav_entries, template_dirs, static_dirs, permissions
    # hooks
    has_handlers(hook) -> bool
    dispatch_hook(hook, /, **kwargs) -> None
```

Seam methods take the plugin as their first argument so every contribution is attributed,
and they raise `PluginError` when called outside that plugin's own `on_register()` — after
discovery the set of contributions is frozen, because `Admin` mounts them once at startup.
Inside `on_register`, `PluginError` (like any exception) aborts that plugin's registration and
rolls back everything it contributed.

### UI extension seams

#### Pages

`add_page(self, router, prefix="/reports")` — `router` is a FastAPI `APIRouter` (duck-checked:
core does not import FastAPI). `prefix` defaults to `/<plugin name>`, must match
`^(/[a-z0-9][a-z0-9_-]*)+$` and be unique across plugins.

Phase 1b mounts each router **inside the admin sub-app** (`admin.asgi_app`, post-#632), so:

- routes use the admin's `HyperAdminRoute` (auth bridge, CSRF, admin-rendered 403/404/409);
  `include_router` keeps each route's own class, so `Admin.mount()` **rebuilds** every
  `APIRoute` / `APIWebSocketRoute` of the page router on the admin route class
  (`core/plugin_wiring.py`). Plugin authors write plain `APIRouter()` code; routes must be
  declared directly on the page router — a nested `include_router`, mount or raw Starlette
  route is logged at ERROR and that page is not mounted;
- in bridge mode (`auth=ExternalAuth`) plugin routes get the same `get_user` guard as model
  routes, because they are added to the admin's protected router;
- routes run behind the admin session — the request carries the admin user exactly like model
  views do; plugins enforce their own codenames with the admin's permission checker;
- route names join the `hyperadmin:` namespace, e.g. `url_for("hyperadmin:reports-index")`.
  Plugins prefix route names with their plugin name to avoid collisions;
- plugin routers are included **after** the model routes; a prefix that collides with a
  registered model slug is logged at ERROR and that page is not mounted (model wins).

#### Sidebar / nav entries

`add_nav_entry(self, label=, url_name=, icon=, permission=, section=, order=, url_params=)`.
`url_name` is a route name in the `hyperadmin:` namespace (usually the plugin's own page);
`url_name` is resolved once at `mount()`; an entry naming no route is logged at ERROR and
left out. Each link gets `data-testid="sidebar-plugin-<plugin>-<url_name>"`.
`icon` uses the admin's icon set names; `permission` is a codename the user must hold for the
entry to render (entry hidden otherwise; the page still enforces it); `section` groups
entries under a heading (`None` → a "Plugins" section); entries are ordered by
`(order, label)`, ties keep plugin order. Sections render after the model app groups.

#### Template search paths

`add_template_dir(self, path)` appends a directory to the admin Jinja loader. Precedence,
highest first:

1. host `settings.template_dirs` (operator overrides beat everything, including plugins),
2. core HyperAdmin templates,
3. plugin template dirs, in plugin order.

So plugins **cannot override core templates** — two plugins can never fight over
`list.html`, and a core upgrade cannot be silently shadowed. Plugins place their templates
under a folder named after the plugin (`templates/reports/index.html` →
`"reports/index.html"`) and `{% extends "base.html" %}` to inherit the admin chrome.
An operator customises a plugin template by putting the same relative path in their own
`template_dirs`.

#### Static files

`set_static_dir(self, path)` — one directory per plugin, served at
`{prefix}/static/plugins/<name>/` (`PluginStaticDir.mount_path`). Phase 1b mounts it in the
admin sub-app **before** the core `/static` mount so the more specific path wins. Templates
reference files with the existing helper:
`{{ url_for('static', path='/plugins/reports/charts.css') }}`.

#### Permission codenames

`add_permission(self, "view_report_sales", name=None)` — codename `^[a-z][a-z0-9_]*$`,
unique across plugins; `name` defaults to `"Can view report sales"`. Phase 1b feeds them to
`PermissionSyncService` next to model permissions (a collision with a model codename is
logged and skipped) so they appear in the permission matrix and group editor.

#### Typed settings

A plugin may declare `settings_model = MySettings` (a pydantic `BaseModel`, or
`pydantic_settings.BaseSettings` to also read env vars). The operator passes raw values in
`Admin(plugin_settings={"reports": {"page_size": 100}})` (phase 1b). The registry validates
them **before** `on_register`, so the plugin reads `admin.plugins.settings(self.name)` inside
`on_register`. Invalid settings → ERROR, plugin skipped. Settings for unknown or disabled
plugins are ignored.

### Lifecycle hooks

Signatures (documented contract; plugins type-hint explicitly; all keyword arguments):

| Hook | Arguments | Fired from (phase 2) |
|---|---|---|
| `on_register(admin)` | `admin` | `PluginRegistry.register` (phase 1) |
| `on_model_register` | `admin, model, options` | `SiteRegistry.register` |
| `on_before_create` / `on_after_create` | `admin, model, data` / `admin, model, instance` | `DynamicModelView` create |
| `on_before_update` / `on_after_update` | `admin, model, pk, data` / `admin, model, instance` | `DynamicModelView` update |
| `on_before_delete` / `on_after_delete` | `admin, model, pk` | `DynamicModelView` delete |
| `on_before_adapter_call` / `on_after_adapter_call` | `admin, model, op, kwargs` / `admin, model, op, result` | `_AdapterHookWrapper` |

`dispatch_hook(name, **kwargs)` rejects names outside this list (`ValueError` — a core typo,
not a plugin failure), calls handlers in plugin order, and logs-and-continues on exceptions.
Handler lists are cached per hook and invalidated on registration; `has_handlers(name)` lets
hot paths (the adapter wrapper) skip work entirely.

**Adapter wrapping strategy (phase 2, decided):** wrap at the `SiteRegistry.register()`
boundary with `_AdapterHookWrapper(BaseAdapter)` that delegates every method and fires the
adapter-call hooks; concrete adapters stay unchanged; zero overhead when
`not admin.plugins.has_handlers("on_before_adapter_call")`.

### Configuration Changes (phase 1b)

```python
Admin(
    app, engine, ...,
    disabled_plugins: Iterable[str] = (),
    plugin_settings: Mapping[str, Mapping[str, Any]] | None = None,
)
```

`HYPERADMIN_DISABLED_PLUGINS=foo,bar` is unioned with `disabled_plugins` — an env-disable
cannot be re-enabled in code. `HyperAdminSettings.plugins_enabled = False`
(`HYPERADMIN_PLUGINS_ENABLED=false`) skips entry-point discovery entirely; a plugin can
still be registered by hand with `admin.plugins.register(plugin, admin=admin)` before
`mount()`, which is when every seam is applied.

Plugin codenames are synced by `PermissionSyncService.sync_codenames` with
`content_type="plugin:<name>"`; a custom `PermissionRegistry` without that method only
syncs model permissions. In bridge mode there is no `Permission` table: plugins check their
codenames through `admin.permission_checker`, as views do.

### Data Model Changes

None. Plugin permissions use the existing `Permission` table.

## Edge Cases & Error Handling

| Case | Handling |
|---|---|
| Plugin import raises (missing optional dep) | Caught; ERROR with `plugin`, `plugin_entry_point`; `skipped[name]="load_error"`; others continue. |
| Entry point is not a `Plugin`, or `name` ≠ entry-point name | ERROR; `skipped[name]="invalid"`. |
| Invalid plugin name (not `^[a-z][a-z0-9_-]*$`) on manual `register` | ERROR; `register` returns `False`. |
| Settings fail validation | ERROR; plugin skipped (`register_error`); `on_register` not called. |
| `on_register` raises (incl. a seam `PluginError`) | ERROR with `hook="on_register"`; all of the plugin's pages/nav/templates/static/permissions/settings rolled back; `skipped[name]="register_error"`. |
| Seam called outside the plugin's own `on_register` | `PluginError` (contributions are frozen after discovery). |
| Duplicate page prefix / permission codename across plugins | `PluginError` in the later plugin's `on_register` → that plugin is skipped. |
| Second `set_static_dir` in one plugin | `PluginError`. |
| Template/static dir does not exist | `PluginError`. |
| Page prefix collides with a model slug (1b) | ERROR; page not mounted; model routes win. |
| Plugin permission collides with a model codename (1b) | ERROR; plugin codename not synced. |
| Two distributions expose the same entry-point name | Sorted by `(name, value)`; first wins, the rest WARNING and are skipped. |
| Two plugins implement the same hook | Both fire, in plugin (entry-point name) order. |
| Hook raises | Caught per plugin; ERROR with `plugin`, `hook`; remaining handlers and the caller continue. |
| Hook is `async def` | Not supported: ERROR once when the handler list is built; handler ignored. |
| Unknown hook name dispatched | `ValueError` (programming error in core). |
| `disabled_plugins=["nonexistent"]` | Silent no-op — the disable list is a request, not an assertion. |
| `HYPERADMIN_DISABLED_PLUGINS` malformed | Tokens stripped; empty tokens dropped. |
| Plugin stores per-request state on itself | Documented: plugins are singletons; do not. |

## Migration & Backward Compatibility

Backward compatible. All symbols are new; `Admin` gains keyword-only parameters with defaults
in phase 1b; with no plugins installed nothing is mounted and the sidebar is unchanged.
Concrete adapters and model-level hooks are untouched. No semver major.

For reports: phase 1c moves `ReportView` and the chart components out of the core roadmap into
`plugins/hyperadmin-reports/`; nothing reports-related has shipped in a core release, so no
public API is removed.

## Open Questions (resolved 2026-10-18)

- [x] **Should hooks return values (veto/mutate)?** No — observers only. Mutation belongs in
      model-level hooks; vetoes come with an explicit design if a real plugin needs them.
- [x] **Async hooks?** Deferred. Sync only; `async def` handlers are rejected with an ERROR.
- [x] **`on_before_adapter_call` vs `on_adapter_call_start`?** `on_before_*` / `on_after_*` for
      consistency with the rest of the family.
- [x] **Short-circuit implicit or explicit?** Both: `dispatch_hook` is a no-op without handlers,
      and `has_handlers(name)` is exposed (cached) for the adapter wrapper.
- [x] **How does a plugin call the seams?** Through `admin.plugins.add_*(self, ...)` inside
      `on_register`; no separate context object.
- [x] **Can plugins override core templates?** No (precedence above); operators can override
      plugin templates.

## Decision Log

| Decision | Rationale | Alternatives considered |
|---|---|---|
| First plugin is `hyperadmin-reports` (OLAP + charts), `hyperadmin-logfire` second (2026-10-18) | Reports are optional for many admins and need only UI seams, so they validate the plugin API early and keep core slim; logfire needs CRUD hook wiring, which can wait for v0.8.0 | Logfire first (original plan) — delays the plugin decision for reports; keep reports in core — every install pays for it |
| Plugin system pulled forward ahead of v0.8.0; CRUD/adapter hook wiring stays in v0.8.0 | Reports must not land in core and then move; the dispatcher is cheap to ship now, call-site wiring is not needed by reports | Ship everything in v0.8.0 — blocks reports |
| Registry collects, `Admin` applies (1a / 1b split) | Keeps `core/plugins.py` a leaf (no HTTP) and lets the registry ship while v0.5.8 owns `core/app.py` | Registry mounts routers itself — imports FastAPI into a core contract module |
| Seams take the plugin as first argument and only work inside its own `on_register` | Attribution for rollback/logs; contributions frozen before mounting | Implicit "current plugin" — hides attribution; context object — second API surface to learn |
| Plugin templates searched after core; no core overrides | Plugins cannot fight over core templates or shadow core fixes; operators still override anything | Plugins first — last-installed plugin silently restyles the admin |
| One static dir per plugin at `/static/plugins/<name>/`, reuse `url_for('static', ...)` | Namespaced, cache-friendly, no new template helper | Per-plugin route name + helper — more API |
| Plugin pages mounted in the admin sub-app with `HyperAdminRoute` | Same session, CSRF, error pages and `hyperadmin:` URL names as model views | Mount on the host app — loses admin auth context |
| Typed settings via optional `settings_model`, validated before `on_register` | Fail fast, typed access, `BaseSettings` gives env support for free | Untyped dict — errors surface late inside the plugin |
| Entry-point name is identity; `plugin.name` must match | One name for URLs, static path, settings, disable list | Trust `plugin.name` — two names for one plugin |
| Wrap adapters at `SiteRegistry.register()` boundary (phase 2) | Concrete adapters stay clean; one wrapper covers all adapters | Decorate `BaseAdapter` methods; mixin inheritance |
| Synchronous fan-out, exceptions caught per plugin | Plugins must not break core; no async leakage | Async fan-out; re-raise |
| Entry-point group `hyperadmin.plugins` | Convention (pytest, Flask) | `hyperadmin.extensions` |
| `Plugin` is a `Protocol`, not an ABC | No forced inheritance; `isinstance` works | ABC |
| Disable list = ctor ∪ env | Ops can disable without code; code can't re-enable | Either one overrides |
| Hooks are observers, not mutators | Small contract; mutation via model hooks | Return modified data |
| No async hooks | No consumer needs them | Async-first |
