---
type: story
id: QWzNA81Jovue
title: "feat(core): implement app-level hook dispatcher with failure isolation"
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

Implement the dispatch loop on `PluginRegistry`. For a given hook name, iterate all
plugins, call the matching method if defined, catch and log any exception. This is
the contract every other story in the epic relies on.

**Spec:** [`docs/specs/plugin-registry.md`](../../../../docs/specs/plugin-registry.md)

## Files to Change

- **Modified:** `src/hyperadmin/core/plugins.py` — implement `PluginRegistry.dispatch`

## Design

```python
def dispatch(self, hook: str, /, **kwargs: Any) -> None:
    for name, plugin in self._plugins.items():
        handler = getattr(plugin, hook, None)
        if handler is None or not callable(handler):
            continue
        try:
            handler(**kwargs)
        except Exception:
            log.exception(
                "plugin hook raised",
                extra={"plugin": name, "hook": hook},
            )
```

Iteration order is insertion order of `self._plugins` (Python dict, sorted by
entry-point name during `discover`).

`structlog`-friendly: `extra={"plugin": ..., "hook": ...}` so structured backends
can index by plugin/hook name.

## Scenarios

**Scenario: hook exception is logged and does not break the request**
  Given a plugin's on_after_update hook always raises RuntimeError
  When  POST /admin/products/1/update with valid data
  Then  the response is 302 (success redirect)
  And   a structured log record at level ERROR mentions the plugin name and the hook

**Scenario: dispatch with no handlers is a no-op**
  Given a registry with two plugins, neither defines on_xyz
  When  registry.dispatch("on_xyz", foo=1) is called
  Then  no log records are emitted
  And   the call returns in O(plugins) without raising

## Acceptance Criteria

- [ ] `dispatch` iterates all plugins, catches exceptions, logs at ERROR
- [ ] Log record includes `plugin` and `hook` in `extra` for structured logging
- [ ] No-handler hooks are O(plugins) and silent
- [ ] Subsequent handlers fire even if an earlier one raised
- [ ] Unit tests passing (covered by `test-unit-tests-for-plugin-discovery-and-disable-mechanism`)

## Blocked by

- `featcore-wire-plugin-discovery-into-admin-init`

## Parent

- Epic: `epic-plugins-registry-and-lifecycle-hooks`
