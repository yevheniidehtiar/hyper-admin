# SDD: Plugin Registry & Lifecycle Hooks

| Field | Value |
|---|---|
| Author | Claude Code |
| Status | Draft |
| Issue | TBD |
| Milestone | v0.8.0 — Plugins |
| Created | 2026-05-05 |
| Last updated | 2026-05-05 |

---

## Problem

HyperAdmin has zero extension surface today. The only existing hooks are model-level
(`HyperAdminModel.before_save / after_save / before_delete / after_delete` at
`src/hyperadmin/core/model.py:62-71`) and adapter-level
(`BaseAdapter.get_queryset(request)` at `src/hyperadmin/core/adapters.py:59-85`).
There is no app-level lifecycle, no entry-point discovery, no `Plugin` contract.

That blocks four near-term workstreams:

- **`hyperadmin-logfire`** (RFC #276) — needs `on_before_adapter_call` /
  `on_after_adapter_call` to wrap CRUD spans without monkey-patching.
- **Future ORM adapters and AI features** — need a stable, discoverable place to attach.
- **Community plugins** — currently impossible to ship without a fork.
- **Per-deployment customisation** — operators have no clean way to add audit logging,
  custom auth providers, or telemetry without modifying core.

This SDD designs the minimal plugin contract that unblocks all of the above without
locking in choices we will regret in v0.9+.

## Goals

1. **Entry-point discovery** — packages declare `[project.entry-points."hyperadmin.plugins"]`;
   `Admin.__init__` discovers them via `importlib.metadata.entry_points`.
2. **`Plugin` protocol** — runtime-checkable Protocol every plugin satisfies; minimal API
   (`name`, `on_register(admin)`, optional hook methods).
3. **App-level lifecycle hooks** — `on_model_register`, `on_before_create`,
   `on_after_create`, `on_before_update`, `on_after_update`, `on_before_delete`,
   `on_after_delete`, `on_before_adapter_call`, `on_after_adapter_call`.
4. **Disable mechanism** — `Admin(disabled_plugins=[...])` constructor arg and
   `HYPERADMIN_DISABLED_PLUGINS` env var (comma-separated names).
5. **CLI introspection** — `hyperadmin plugins list` prints discovered plugins, their
   import paths, and which are disabled.
6. **Failure isolation** — a plugin that raises in any hook is logged at ERROR and
   skipped; the request/operation continues normally.

## Non-Goals

- **Plugin scaffold CLI (`hyperadmin create-plugin`)** — handled by the
  `/scaffold-plugin` slash command in RFC #275, tracked separately under the
  `agentic-workflow` label.
- **Custom non-CRUD page registration (`register_page()`)** — deferred to v0.8.1+.
- **Hot-reload of plugins** — out of scope; restart required.
- **Plugin sandboxing / capability restrictions** — plugins run with full Python access
  in the admin process. Plugins are explicitly trusted code (the operator chose to
  install them).
- **Async hook fan-out via taskgroups** — synchronous fan-out only in v1; revisit if
  any plugin needs concurrency.
- **Versioned plugin API surface** — the public hook list is the API; we will add
  hooks (additive) freely and remove them only with a semver major bump.

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

Scenario: on_before_create hook fires before adapter create
  Given a plugin registers an on_before_create hook that appends model_name to a list
  When  POST /admin/products/create with valid data
  Then  the hook list contains "Product" before the row exists in the DB

Scenario: hook exception is logged and does not break the request
  Given a plugin's on_after_update hook always raises RuntimeError
  When  POST /admin/products/1/update with valid data
  Then  the response is 302 (success redirect)
  And   a structured log record at level ERROR mentions the plugin name and the hook

Scenario: hyperadmin plugins list CLI prints discovered plugins
  Given demo_plugin is installed
  When  the user runs `hyperadmin plugins list`
  Then  stdout contains "demo" and the plugin's class path

Scenario: adapter call hooks wrap every CRUD operation
  Given a plugin records (op, model) tuples in on_before_adapter_call / on_after_adapter_call
  When  the list, create, update, delete views are exercised once each for Product
  Then  the recorded tuples include ("list","Product"), ("create","Product"), ("update","Product"), ("delete","Product") in order
  And   each "before" precedes its matching "after"
```

## Design

### Architecture

New module: `src/hyperadmin/core/plugins.py`. Self-contained, no upward dependencies.

```
┌───────────────────────────────────────────────────────────┐
│  importlib.metadata.entry_points(group="hyperadmin.plugins") │
└───────────────────────────┬───────────────────────────────┘
                            │
                            ▼
       ┌─────────────────────────────────────────┐
       │  PluginRegistry.discover(disabled=...)  │   core/plugins.py
       │   - resolves env var + ctor disabled    │
       │   - skips broken imports (logs)         │
       │   - instantiates plugins                │
       │   - calls on_register(admin)            │
       └────────────────┬────────────────────────┘
                        │ self.plugins
                        ▼
              ┌─────────────────┐
              │   Admin (app)   │   core/app.py
              └────────┬────────┘
                       │ dispatch_hook(name, **kw)
        ┌──────────────┼──────────────┬──────────────────┐
        ▼              ▼              ▼                  ▼
   SiteRegistry    DynamicView    AdapterWrapper    AuthMiddleware
   (model_register) (create/upd/del) (adapter_call)  (future: auth events)
```

Dependency direction obeyed: `core/plugins.py` is leaf — it imports nothing from
`views/`, `adapters/`, `auth/`. `Admin` imports `core/plugins.py`. Higher layers call
`admin.dispatch_hook(...)` rather than importing the registry directly.

### Data Model Changes

No data model changes. All plugin state is in-memory.

### API / Protocol Changes

New public symbols (exported from `hyperadmin` and `hyperadmin.core`):

```python
# src/hyperadmin/core/plugins.py
from typing import Any, Protocol, runtime_checkable

@runtime_checkable
class Plugin(Protocol):
    name: str

    def on_register(self, admin: "Admin") -> None: ...

    # All hook methods are optional. Plugins implement only the ones they care about.
    # Signatures are documented; not enforced by the Protocol.

class PluginRegistry:
    def __init__(self) -> None:
        self._plugins: dict[str, Plugin] = {}
        self._hooks: dict[str, list[tuple[str, Callable]]] = {}

    @classmethod
    def discover(cls, *, admin: "Admin", disabled: set[str]) -> "PluginRegistry": ...
    def __contains__(self, name: str) -> bool: ...
    def __getitem__(self, name: str) -> Plugin: ...
    def names(self) -> list[str]: ...
    def dispatch(self, hook: str, /, **kwargs: Any) -> None:
        """Call every registered handler for `hook`. Exceptions logged, not raised."""
```

Hook signatures (documented contract — plugins type-hint explicitly):

| Hook | Signature | Fired from |
|---|---|---|
| `on_register(admin)` | `(Admin) -> None` | `PluginRegistry.discover` |
| `on_model_register(admin, model, options)` | `(Admin, type, AdminOptions) -> None` | `SiteRegistry.register` |
| `on_before_create(admin, model, data)` | `(Admin, type, dict) -> None` | `DynamicModelView.create_view` |
| `on_after_create(admin, model, instance)` | `(Admin, type, Any) -> None` | same |
| `on_before_update(admin, model, pk, data)` | `(Admin, type, Any, dict) -> None` | `DynamicModelView.update_view` |
| `on_after_update(admin, model, instance)` | `(Admin, type, Any) -> None` | same |
| `on_before_delete(admin, model, pk)` | `(Admin, type, Any) -> None` | `DynamicModelView.delete_view` |
| `on_after_delete(admin, model, pk)` | `(Admin, type, Any) -> None` | same |
| `on_before_adapter_call(admin, model, op, kwargs)` | `(Admin, type, str, dict) -> None` | `_AdapterHookWrapper` |
| `on_after_adapter_call(admin, model, op, result)` | `(Admin, type, str, Any) -> None` | same |

`Admin` gains:

```python
admin.plugins: PluginRegistry
admin.dispatch_hook(name: str, **kwargs) -> None  # thin proxy to plugins.dispatch
```

### Configuration Changes

```python
Admin(
    app,
    engine,
    ...,
    disabled_plugins: Iterable[str] = (),  # NEW — defaults to empty
)
```

Env var: `HYPERADMIN_DISABLED_PLUGINS=foo,bar` — merged into the constructor set
(union, not override) so an env-disable can't be re-enabled in code.

### Adapter wrapping strategy (decided)

**Decision: wrap at `SiteRegistry.register()` boundary**, not in `BaseAdapter` itself.

```python
# core/registry.py — inside SiteRegistry.register()
adapter = adapter_cls(model, engine=...)
if admin.plugins:
    adapter = _AdapterHookWrapper(inner=adapter, admin=admin, model=model)
self._models[model] = (adapter, options)
```

`_AdapterHookWrapper` lives in `core/plugins.py`, subclasses `BaseAdapter`,
delegates every method, and fires `on_before_adapter_call` / `on_after_adapter_call`
around each call. Concrete adapters (`SQLModelAdapter`, `SQLAlchemyAdapter`) stay
unchanged. Zero overhead when `not admin.plugins.has_handlers("on_before_adapter_call")`
(the wrapper short-circuits).

Rejected alternatives recorded in Decision Log.

## Edge Cases & Error Handling

| Case | Handling |
|---|---|
| Plugin import raises (e.g. missing optional dep) | Caught in `discover`; logged ERROR with `plugin_entry_point=...`; entry skipped; remaining plugins continue loading. |
| Plugin `on_register` raises | Caught; logged ERROR; plugin removed from registry; subsequent hooks not dispatched to it. |
| Two plugins register the same hook | Both fire in entry-point definition order (sorted by entry-point name for determinism). |
| Plugin hook raises | Caught per-plugin; logged ERROR with `plugin`, `hook`, `exc_type`; remaining handlers and the calling code continue. |
| `disabled_plugins=["nonexistent"]` | Silently no-op (no log) — disable list is a request, not an assertion. |
| Plugin name collides with another plugin | First-loaded wins; second logs WARNING and is skipped. Entry-point names are the unit of identity. |
| Hook fired with no registered handlers | Fast path: `dispatch` is a no-op (no list iteration). |
| Plugin uses async hook | Not supported in v1. Plugins must run sync code; if they need async, they own their own task scheduling. SDD revisit if a real plugin needs this. |
| `HYPERADMIN_DISABLED_PLUGINS` malformed (e.g. trailing commas) | Stripped tokens, empty tokens skipped. |
| Plugin stores per-request state on itself | Plugin author's bug; not our concern. We document "plugins are singletons; do not store per-request state". |

## Migration & Backward Compatibility

**Backward compatible — no migration required.**

- All new symbols are additive.
- `Admin(...)` gains one keyword-only parameter with a default; existing call sites
  unchanged.
- `BaseAdapter` subclasses are not modified — wrapping is external. Any third-party
  adapter that already exists continues to work.
- Model-level hooks (`HyperAdminModel.before_save` etc.) are untouched and remain the
  recommended path for model-specific logic. App-level hooks are for cross-cutting
  concerns (telemetry, audit, multi-model policies).
- No public API removed. No semver major bump required.

## Open Questions

- [ ] **Should `dispatch_hook` return values?** Some hooks (`on_before_create`)
      could in principle veto the operation. v1 says no — hooks are observers, not
      mutators. Plugins that need to mutate data implement model-level hooks instead.
      Confirm at SDD review.
- [ ] **Async hooks** — defer until first real need. Confirm at SDD review.
- [ ] **Naming: `on_before_adapter_call` vs `on_adapter_call_start`** — current
      proposal mirrors the rest of the `on_before_*` family for consistency. Confirm.
- [ ] **Should the wrapper short-circuit be exposed as `plugins.has_handlers(name)`
      or computed implicitly in `dispatch`?** Implicit is simpler; explicit gives
      adapter wrapper a faster check. Recommend implicit for v1.

## Decision Log

| Decision | Rationale | Alternatives considered |
|---|---|---|
| Wrap adapters at `SiteRegistry.register()` boundary | Concrete adapters stay clean; zero changes to `SQLModelAdapter` / `SQLAlchemyAdapter`; one wrapper covers all current and future adapters | (a) Decorator on each `BaseAdapter` abstract method — couples concrete adapters to plugin system; (b) Inheritance via mixin — forces every adapter author to extend a specific base |
| Synchronous fan-out, exceptions caught per-plugin | Simplest; matches "plugins must not break core" requirement; no async leakage to non-async call sites | (a) Async-aware fan-out — premature; (b) Re-raise — violates isolation |
| Entry-point group `hyperadmin.plugins` | Convention follows pytest, FastAPI, Django plugins | `hyperadmin.extensions`, `hyperadmin_plugins` (no namespace) |
| `Plugin` as `Protocol`, not ABC | Plugins shouldn't have to inherit from us; runtime_checkable enables `isinstance` for tests | ABC — forces inheritance and import-time coupling |
| Disable list is union of ctor + env var | Lets ops disable a misbehaving plugin without code change; can't be silently re-enabled in code | Override (env wins / ctor wins) — surprising in either direction |
| Hooks are observers, not mutators (in v1) | Keeps the contract simple; mutation paths exist via model hooks | Allow hooks to return modified data — opens a large surface for plugin conflicts |
| No async hook support in v1 | YAGNI; no current consumer needs it | Async-first design — premature complexity |
