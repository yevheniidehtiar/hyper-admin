---
type: story
id: X0iESCETqvl-
title: "feat(core): wire plugin discovery, pages, static and templates into Admin"
status: done
priority: high
assignee: null
labels:
  - backend
  - size:M
  - planned
  - plugins
estimate: null
epic_ref:
  id: um1zqB0-b2AZ
created_at: 2026-10-18T00:00:00Z
updated_at: 2026-10-20T00:00:00Z
---

## Summary

Phase 1b (`plug-wire`, gated on v0.5.8 Bring Your Own App). `Admin` calls
`PluginRegistry.discover(admin=self, disabled=..., settings=plugin_settings)`, exposes
`admin.plugins` / `admin.dispatch_hook`, and applies the collected seams:

- include each `PluginPage.router` in `admin.asgi_app` with the admin `HyperAdminRoute`
  class, under its prefix, after model routes (model-slug collisions logged + skipped);
- mount each `PluginStaticDir` at `mount_path` **before** the core `/static` mount;
- append plugin template dirs after core templates in the Jinja loader;
- `Admin(disabled_plugins=..., plugin_settings=...)`;
- re-export `Plugin`, `PluginRegistry`, `PluginError` from `hyperadmin` and `hyperadmin.core`.

**Spec:** [`docs/specs/plugin-registry.md`](../../../../docs/specs/plugin-registry.md) — "Phasing" 1b

## Scenarios

**Scenario: plugin page is served inside the admin**
  Given plugin "reports" adds a router with GET "/" named "reports-index"
  When  a signed-in staff user requests GET {prefix}/reports/
  Then  the response is 200 and url_for("hyperadmin:reports-index") resolves

**Scenario: plugin static file is served under its own path**
  Given plugin "reports" sets a static dir containing "charts.css"
  When  GET {prefix}/static/plugins/reports/charts.css
  Then  the response is 200

**Scenario: broken plugin does not break the admin**
  Given plugin "broken" raises in on_register after adding a page
  When  the admin starts
  Then  its page is not mounted and an ERROR names the plugin

## Blocked by

- `featcore-plugin-ui-seam-registration-api`
- v0.5.8 Bring Your Own App (`core/app.py` ownership)

## Parent

- Epic: `epic-plugins-registry-and-lifecycle-hooks`
