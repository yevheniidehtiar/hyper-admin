---
type: story
id: UExbEq_t2pV_
title: "feat(core): wire plugin discovery into Admin.__init__"
status: todo
priority: high
assignee: null
labels:
  - backend
  - size:S
  - planned
  - plugins
estimate: null
epic_ref:
  id: um1zqB0-b2AZ
created_at: 2026-05-05T00:00:00Z
updated_at: 2026-05-05T00:00:00Z
---

## Summary

Wire `PluginRegistry.discover()` into `Admin.__init__` and add the
`disabled_plugins` constructor argument. Plugins are discovered eagerly on
construction; `on_register` fires for each.

**Spec:** [`docs/specs/plugin-registry.md`](../../../../docs/specs/plugin-registry.md)

## Files to Change

- **Modified:** `src/hyperadmin/core/app.py:23-417` — `Admin.__init__`

## Design

```python
class Admin:
    def __init__(
        self,
        app: FastAPI,
        engine: ...,
        ...,
        disabled_plugins: Iterable[str] = (),
    ) -> None:
        ...
        # late in __init__, after self.app/self.engine are set,
        # before any model registration:
        env_disabled = {
            n.strip() for n in os.environ.get("HYPERADMIN_DISABLED_PLUGINS", "").split(",")
            if n.strip()
        }
        self.plugins = PluginRegistry.discover(
            admin=self,
            disabled=set(disabled_plugins) | env_disabled,
        )
```

`Admin.dispatch_hook(name, **kwargs)` is a thin proxy:

```python
def dispatch_hook(self, hook: str, /, **kwargs: Any) -> None:
    self.plugins.dispatch(hook, **kwargs)
```

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

## Acceptance Criteria

- [ ] `Admin(disabled_plugins=...)` argument added (keyword-only, default empty)
- [ ] `Admin.plugins` populated before any auto-registration happens
- [ ] `Admin.dispatch_hook` proxy method available
- [ ] No regression in existing `Admin` tests
- [ ] `poe lint` and `poe test:unit` pass

## Blocked by

- `featcore-add-plugin-protocol-and-registry-module`

## Parent

- Epic: `epic-plugins-registry-and-lifecycle-hooks`
