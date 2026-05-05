---
type: story
id: qLiduVMFCQew
title: "feat(core): add Plugin protocol and PluginRegistry module"
status: todo
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
created_at: 2026-05-05T00:00:00Z
updated_at: 2026-05-05T00:00:00Z
---

## Summary

Introduce the `Plugin` protocol and `PluginRegistry` class in a new module
`src/hyperadmin/core/plugins.py`. This is the foundation that everything else in the
epic depends on. No wiring yet — just the contract.

**Spec:** [`docs/specs/plugin-registry.md`](../../../../docs/specs/plugin-registry.md)

## Files to Change

- **New:** `src/hyperadmin/core/plugins.py`
- **Modified:** `src/hyperadmin/core/__init__.py` — export `Plugin`, `PluginRegistry`
- **Modified:** `src/hyperadmin/__init__.py` — re-export `Plugin` for plugin authors

## Design

```python
# src/hyperadmin/core/plugins.py
from __future__ import annotations
import logging
import os
from importlib.metadata import entry_points
from typing import TYPE_CHECKING, Any, Callable, Protocol, runtime_checkable

if TYPE_CHECKING:
    from hyperadmin.core.app import Admin

log = logging.getLogger("hyperadmin.plugins")


@runtime_checkable
class Plugin(Protocol):
    name: str

    def on_register(self, admin: "Admin") -> None: ...


class PluginRegistry:
    def __init__(self) -> None:
        self._plugins: dict[str, Plugin] = {}

    @classmethod
    def discover(
        cls,
        *,
        admin: "Admin",
        disabled: set[str] | None = None,
    ) -> "PluginRegistry": ...

    def __contains__(self, name: str) -> bool: ...
    def __getitem__(self, name: str) -> Plugin: ...
    def __bool__(self) -> bool: ...
    def names(self) -> list[str]: ...

    def dispatch(self, hook: str, /, **kwargs: Any) -> None:
        """Call every registered handler for `hook`. Exceptions logged, not raised."""
```

`disabled` is the union of the constructor argument (caller passes
`set(admin.disabled_plugins)`) and `HYPERADMIN_DISABLED_PLUGINS` parsed from env.
Entries skipped during discovery are NOT added to `self._plugins`.

`dispatch` iterates all plugins, calls `getattr(plugin, hook, None)`, invokes if
callable, catches `Exception`, logs at ERROR with `plugin`, `hook`, exc info.

## Scenarios

**Scenario: protocol is runtime-checkable**
  Given a class with `name: str` and `on_register(self, admin) -> None`
  When  `isinstance(instance, Plugin)` is evaluated
  Then  result is True

**Scenario: registry is empty by default**
  Given no entry points exist for "hyperadmin.plugins"
  When  PluginRegistry.discover(admin=mock, disabled=set()) is called
  Then  the returned registry has names() == []
  And   bool(registry) is False

## Acceptance Criteria

- [ ] `Plugin` protocol defined and runtime-checkable
- [ ] `PluginRegistry` class with `discover` / `dispatch` / `names` / `__contains__` / `__getitem__` / `__bool__`
- [ ] Imports lazy: `core/plugins.py` uses `TYPE_CHECKING` for `Admin` import
- [ ] Exported from `hyperadmin.core.__init__` and `hyperadmin.__init__`
- [ ] `poe lint` passes

## Blocked by

- `reviewspec-approve-sdd-for-plugin-registry` (SDD approved)

## Parent

- Epic: `epic-plugins-registry-and-lifecycle-hooks`
