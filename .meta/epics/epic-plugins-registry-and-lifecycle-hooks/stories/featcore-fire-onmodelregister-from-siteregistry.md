---
type: story
id: pjMf5_ic9HU3
title: "feat(core): fire on_model_register from SiteRegistry"
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

Fire the `on_model_register` hook from `SiteRegistry.register()` after a model
+ adapter + options has been successfully attached. Plugins receive
`(admin, model, options)` and can index models, pre-warm caches, register custom
spans, etc.

**Spec:** [`docs/specs/plugin-registry.md`](../../../../docs/specs/plugin-registry.md)

## Files to Change

- **Modified:** `src/hyperadmin/core/registry.py:20-69` — `SiteRegistry.register`

## Design

After successful registration, before returning, dispatch:

```python
self._admin.dispatch_hook(
    "on_model_register",
    admin=self._admin,
    model=model,
    options=options,
)
```

`SiteRegistry` already holds a back-reference to `Admin`; if not, add it during
the `Admin.__init__` story.

Hook fires once per `register()` call. If the same model is registered twice (an
existing error path), the hook only fires for the successful first call.

## Scenarios

**Scenario: on_model_register fires for each registered model**
  Given a plugin records (model_name) into a list in on_model_register
  When  Admin auto-registers User and Product models
  Then  the list contains "User" and "Product" exactly once each

**Scenario: on_model_register fires after adapter is attached**
  Given a plugin's on_model_register reads admin.site._models[model][0] (the adapter)
  When  the hook fires for Product
  Then  the read succeeds and returns a non-None adapter

## Acceptance Criteria

- [ ] Hook fires exactly once per successful `SiteRegistry.register()` call
- [ ] Hook fires AFTER adapter and options are stored (plugins can read them)
- [ ] Hook does NOT fire on duplicate-register error
- [ ] Unit test added under `tests/unit/core/test_plugin_hooks.py`

## Blocked by

- `featcore-implement-app-level-hook-dispatcher`

## Parent

- Epic: `epic-plugins-registry-and-lifecycle-hooks`
