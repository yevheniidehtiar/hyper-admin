---
type: epic
id: um1zqB0-b2AZ
title: "epic(plugins): Plugin Registry & Lifecycle Hooks"
status: todo
priority: high
owner: null
labels:
  - size:L
  - planned
  - plugins
milestone_ref:
  id: XnHVJphQRoMf
created_at: 2026-05-05T00:00:00Z
updated_at: 2026-05-05T00:00:00Z
---

## Overview

Introduce the foundational plugin contract for HyperAdmin: entry-point discovery,
a runtime-checkable `Plugin` protocol, app-level lifecycle hooks, a disable
mechanism, and a `hyperadmin plugins list` CLI introspection command. This epic
unblocks every other v0.8.0+ extension workstream (`hyperadmin-logfire`, future
ORM adapters, AI features) and is the first required piece of the milestone.

**SDD:** [`docs/specs/plugin-registry.md`](../../../docs/specs/plugin-registry.md)
(required — touches `core/`, `adapters/` boundary, `views/`, CLI).

## Tracks

### Track A: Discovery & Plugin protocol
- New module `src/hyperadmin/core/plugins.py` — `Plugin` protocol, `PluginRegistry`.
- `importlib.metadata.entry_points(group="hyperadmin.plugins")` discovery.
- `Admin(disabled_plugins=...)` constructor arg + `HYPERADMIN_DISABLED_PLUGINS` env var.
- `Admin.plugins` attribute, `Admin.dispatch_hook(name, **kwargs)` proxy.

### Track B: Lifecycle hooks
- `on_model_register` fired from `SiteRegistry.register()`.
- `on_before_create` / `on_after_create` / `on_before_update` / `on_after_update` /
  `on_before_delete` / `on_after_delete` fired from `DynamicModelView` create/update/
  delete handlers.
- `on_before_adapter_call` / `on_after_adapter_call` fired by an `_AdapterHookWrapper`
  that wraps adapters at `SiteRegistry.register()` boundary — no concrete adapter
  changes.
- Failure isolation: hook exceptions logged at ERROR per-plugin, never raised.

### Track C: CLI & docs
- `hyperadmin plugins list` subcommand — prints discovered plugins, class paths, disabled state.
- Plugin author guide + hook reference under `docs/`.

## Scenarios

**Scenario: plugin discovered via entry point on Admin construction**
  Given a package "demo_plugin" exposes [project.entry-points."hyperadmin.plugins"] demo = "demo_plugin:DemoPlugin"
  When  Admin(app, engine=engine) is constructed
  Then  admin.plugins["demo"] is an instance of DemoPlugin
  And   demo.on_register(admin) was called exactly once

**Scenario: disabled plugin is not loaded**
  Given the same demo_plugin is installed
  When  Admin(app, engine=engine, disabled_plugins=["demo"]) is constructed
  Then  "demo" is not in admin.plugins
  And   DemoPlugin.on_register was not called

**Scenario: on_before_create hook fires before adapter create**
  Given a plugin registers an on_before_create hook that appends model_name to a list
  When  POST /admin/products/create with valid data
  Then  the hook list contains "Product" before the row exists in the DB

**Scenario: hook exception is logged and does not break the request**
  Given a plugin's on_after_update hook always raises RuntimeError
  When  POST /admin/products/1/update with valid data
  Then  the response is 302 (success redirect)
  And   a structured log record at level ERROR mentions the plugin name and the hook

**Scenario: hyperadmin plugins list CLI prints discovered plugins**
  Given demo_plugin is installed
  When  the user runs `hyperadmin plugins list`
  Then  stdout contains "demo" and the plugin's class path

**Scenario: adapter call hooks wrap every CRUD operation**
  Given a plugin records (op, model) tuples in on_before_adapter_call / on_after_adapter_call
  When  the list, create, update, delete views are exercised once each for Product
  Then  the recorded tuples include ("list","Product"), ("create","Product"), ("update","Product"), ("delete","Product") in order
  And   each "before" precedes its matching "after"

## Acceptance Criteria

- [ ] Plugin discovered via entry point on Admin construction
- [ ] Disabled plugin is not loaded (ctor + env var)
- [ ] `on_before_create` hook fires before adapter create
- [ ] Hook exception is logged and does not break the request
- [ ] `hyperadmin plugins list` CLI prints discovered plugins
- [ ] Adapter call hooks wrap every CRUD operation in correct order
- [ ] Unit + E2E tests for all six scenarios
- [ ] Plugin author guide published under `docs/`
