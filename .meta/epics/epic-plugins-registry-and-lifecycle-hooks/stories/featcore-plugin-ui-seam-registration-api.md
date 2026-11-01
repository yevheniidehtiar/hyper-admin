---
type: story
id: l_CHWhc2Un-c
title: "feat(core): plugin UI-seam registration API and typed settings"
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
updated_at: 2026-11-01T00:00:00Z
---

## Summary

Phase 1a (`plug-core`). `PluginRegistry` collects what a plugin contributes from
`on_register(admin)`: pages (`add_page`), sidebar entries (`add_nav_entry`), template
dirs (`add_template_dir`), a static dir (`set_static_dir`), permission codenames
(`add_permission`) and typed settings (`settings_model`). Collection only — no mounting.

**Spec:** [`docs/specs/plugin-registry.md`](../../../../docs/specs/plugin-registry.md) — "UI extension seams"

## Files to Change

- **New:** `src/hyperadmin/core/plugins.py`
- **New:** `tests/unit/test_plugins.py`

## Scenarios

**Scenario: plugin contributes pages, nav, templates, static and permissions**
  Given a plugin that uses every seam in on_register
  When  it is registered
  Then  the registry exposes each contribution attributed to the plugin

**Scenario: plugin on_register raises**
  Given a plugin that adds a permission and then raises
  When  it is registered
  Then  it is not kept and its permission is rolled back

**Scenario: seam called outside on_register**
  Then  PluginError is raised

## Acceptance Criteria

- [x] Seam data structures (`PluginPage`, `NavEntry`, `PluginTemplateDir`, `PluginStaticDir`, `PluginPermission`)
- [x] Validation + cross-plugin conflicts (prefix, codename) raise `PluginError`
- [x] Rollback of all contributions on registration failure
- [x] Typed settings validated before `on_register`
- [x] 100 % diff coverage

## Blocked by

- `reviewspec-approve-sdd-for-plugin-registry`

## Parent

- Epic: `epic-plugins-registry-and-lifecycle-hooks`
