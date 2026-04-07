---
type: story
id: vMAT45LgS66O
title: "feat(core): wire HyperAdminSettings into Admin class"
status: done
priority: medium
assignee: null
labels:
  - enhancement
  - agent-task
  - area:core
  - size:M
  - area:settings
estimate: null
epic_ref: null
github:
  issue_number: 376
  repo: yevheniidehtiar/hyper-admin
  last_sync_hash: sha256:913dbab63b4839f798451f5132927a83a11b869180a562bd245c3c492eeb3188
  synced_at: 2026-04-07T17:23:23.791Z
created_at: 2026-03-31T09:07:35Z
updated_at: 2026-03-31T19:58:58Z
---

## Context

Replace scattered scalar params on `Admin.__init__()` with a single `settings: HyperAdminSettings` object. Scalar config (theme, session_secret, auto_discover, create_tables, site_title, items_per_page, etc.) lives exclusively in settings — no duplicate params on Admin.

Protocol objects that cannot be env vars (`auth_backend`, `permission_checker`, `permission_registry`) remain as Admin params. `engine` remains a param (constructed from `settings.database_url` by the user or auto-created).

### Before

```python
Admin(app, engine=engine, session_secret="...", theme="dark",
      auto_discover=True, create_tables=True, auth_backend=backend, ...)
```

### After

```python
settings = HyperAdminSettings(secret_key="...", theme="dark")
Admin(app, engine=engine, settings=settings, auth_backend=backend)
```

## Scenarios

**Scenario: Admin reads all scalar config from settings**
  Given `HyperAdminSettings(theme="dark", auto_discover=False, site_title="My Admin")`
  When  `Admin(app, engine=engine, settings=settings)` is created
  Then  theme is "dark", auto_discover is False, site_title is "My Admin"

**Scenario: Admin works with default settings**
  Given no settings object passed
  When  `Admin(app, engine=engine)` is created
  Then  `HyperAdminSettings()` is auto-instantiated with defaults
  And   no errors

**Scenario: template globals populated from settings**
  Given `HyperAdminSettings(site_title="ERP Admin", theme="light")`
  When  `admin.mount("/admin")` is called
  Then  Jinja2 globals include `site_title="ERP Admin"` and `theme="light"`

## Acceptance criteria

- [ ] Remove scalar params from `Admin.__init__()`: `session_secret`, `theme`, `create_tables`, `discover_apps`, `template_dirs`
- [ ] Add `settings: HyperAdminSettings | None = None` param (auto-instantiate if None)
- [ ] All scalar config read from `self.settings.*`
- [ ] Protocol objects remain as params: `auth_backend`, `permission_checker`, `permission_registry`
- [ ] `engine` remains a param (user constructs from `settings.database_url` or passes directly)
- [ ] Template globals populated from settings
- [ ] Update examples to use new API
- [ ] Unit tests

## Files likely affected

- `src/hyperadmin/core/app.py` — refactor `__init__()` and `mount()`
- `examples/erp/main.py`
- `examples/simple/main.py`
- `tests/` — update any tests using old scalar params

## Dependencies

Depends on: #375

## Notes for implementer

This is a **breaking change** to `Admin.__init__()` signature. Existing code passing `session_secret=`, `theme=`, `create_tables=` as direct params must migrate to `HyperAdminSettings(...)`. Document in migration notes.
