---
type: story
id: MiLd8X9lxIA2
title: "feat(core): add dashboard config to Admin class"
status: todo
priority: medium
assignee: null
labels:
  - enhancement
  - agent-task
  - area:core
  - size:S
  - area:settings
estimate: null
epic_ref:
  id: _MkBhj2OoiGp
github:
  issue_number: 468
  repo: yevheniidehtiar/hyper-admin
  last_sync_hash: sha256:a43271421d17bc59f81a8f74bbd60e343b7f6e10786f6bc7eeb84fc6bf680ea0
  synced_at: 2026-04-07T17:23:23.791Z
created_at: 2026-04-01T21:45:33Z
updated_at: 2026-11-20T00:00:00Z
---

## Context

Spec: `docs/specs/dashboard-builder.md` (Core seam, Configuration Changes).

The admin index `{prefix}/` is core-owned and renders `dashboard.html`. Plugin templates are
searched after the core's, so a plugin cannot replace it. This story adds the one core change of
the epic, an additive plugin seam `PluginRegistry.set_home_page(plugin, endpoint)`, and gives the
reports plugin its typed settings (`ReportsSettings`). It is the seam story: it ships before the
dashboard routes use it. No `Admin()` or `HyperAdminSettings` parameter is added.

## Scenarios

**Scenario: a plugin home page replaces the welcome page**
  Given a test plugin calls `admin.plugins.set_home_page(self, endpoint)` in `on_register`
  And   `endpoint` returns an HTML response "plugin home"
  When  a signed-in user requests `GET {prefix}/`
  Then  the response is 200 with "plugin home"

**Scenario: without a home page the welcome page is served**
  Given no plugin set a home page
  When  a signed-in user requests `GET {prefix}/`
  Then  the response contains "Welcome to HyperAdmin Dashboard"

**Scenario: a second home page claim is refused**
  Given plugin "first" set the home page
  When  plugin "second" calls `set_home_page` in its `on_register`
  Then  `PluginError` is raised
  And   "second" is skipped with reason `register_error`
  And   `GET {prefix}/` still serves "first"'s endpoint

**Scenario: a home page endpoint that raises falls back to the welcome page**
  Given a plugin home page endpoint that raises `RuntimeError`
  When  a signed-in user requests `GET {prefix}/`
  Then  the response is 200 with the welcome page
  And   the error is logged with the plugin name

**Scenario: an HTTP error from the home page endpoint is kept**
  Given a plugin home page endpoint that raises `HTTPException(403)`
  When  a signed-in user requests `GET {prefix}/`
  Then  the response is 403

**Scenario: reports plugin settings come from plugin_settings**
  Given `Admin(app, engine=engine, plugin_settings={"reports": {"dashboard_home": False}})`
  When  the reports plugin is registered
  Then  `admin.plugins.settings("reports").dashboard_home` is `False`
  And   `dashboard_layouts` is `True` and `dashboard_prefix` is `"/dashboard"`

## Acceptance Criteria

- [ ] `PluginHomePage(plugin, endpoint)` and `PluginRegistry.set_home_page()` / `home_page` in
      `core/plugins.py`; the claim is part of `_Contributions`, so a failed `on_register` drops it
- [ ] `set_home_page` outside the plugin's own `on_register` raises `PluginError` (same guard as the other seams)
- [ ] `HyperAdminRouter` takes a `home_page` lookup; `GET {prefix}/` (name `admin-dashboard`)
      awaits it per request; non-HTTP exceptions are logged and fall back to the welcome page
- [ ] `Admin._register_views` passes `home_page=lambda: self.plugins.home_page` (one anchored hunk)
- [ ] `ReportsSettings(BaseSettings)` with env prefix `HYPERADMIN_REPORTS_`: `dashboard_home=True`,
      `dashboard_layouts=True`, `dashboard_prefix="/dashboard"` (validated against the page prefix
      pattern); `ReportsPlugin.settings_model = ReportsSettings`
- [ ] Addendum in `docs/specs/plugin-registry.md` listing the home page seam
- [ ] Unit tests cover all 6 scenarios

## Files to Change

- `src/hyperadmin/core/plugins.py`
- `src/hyperadmin/routing.py`
- `src/hyperadmin/core/app.py` (one keyword argument in `_register_views`)
- `plugins/hyperadmin-reports/src/hyperadmin_reports/settings.py` (new)
- `plugins/hyperadmin-reports/src/hyperadmin_reports/plugin.py` (`settings_model` only)
- `docs/specs/plugin-registry.md`
- `tests/unit/test_plugin_home_page.py` (new)
- `plugins/hyperadmin-reports/tests/test_plugin.py`

## Dependencies

Depends on: `reviewspec-approve-sdd-for-dashboard-builder.md`

## Notes for Implementer

- `core/app.py` and `routing.py` are hotspots: keep each change in its own small hunk.
- The endpoint signature is exactly `async (request: Request) -> Response`; the core calls it
  directly, not through FastAPI dependency injection.
- `PluginHomePage` is not re-exported from `hyperadmin.__init__`.
