---
type: story
id: fY2baq9AS-fH
title: "test(unit): plugin discovery, disable mechanism, dispatch isolation"
status: todo
priority: high
assignee: null
labels:
  - testing
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

Unit tests for `PluginRegistry`. Mock `importlib.metadata.entry_points` to inject
fake plugins; assert discovery, disable, dispatch, and failure-isolation behaviour.

**Spec:** [`docs/specs/plugin-registry.md`](../../../../docs/specs/plugin-registry.md)

## Files to Change

- **New:** `tests/unit/core/test_plugins.py`

## Test Cases

```python
async def test_protocol_is_runtime_checkable() -> None:
    """Scenario: protocol is runtime-checkable"""

async def test_registry_empty_when_no_entry_points(monkeypatch) -> None:
    """Scenario: registry is empty by default"""

async def test_discovery_loads_plugin_and_calls_on_register(monkeypatch) -> None:
    """Scenario: plugin discovered via entry point on Admin construction"""

async def test_disabled_plugin_not_loaded_via_ctor(monkeypatch) -> None:
    """Scenario: disabled plugin is not loaded (ctor)"""

async def test_disabled_plugin_not_loaded_via_env(monkeypatch) -> None:
    """Scenario: HYPERADMIN_DISABLED_PLUGINS env var disables plugin"""

async def test_disable_ctor_and_env_take_union(monkeypatch) -> None:
    """env-disabled plugins cannot be re-enabled by omitting from ctor list"""

async def test_plugin_import_failure_skipped_and_logged(monkeypatch, caplog) -> None:
    """import error in entry point → log ERROR, skip, continue loading others"""

async def test_on_register_failure_skipped_and_logged(monkeypatch, caplog) -> None:
    """on_register raises → log ERROR, plugin removed from registry"""

async def test_dispatch_calls_all_handlers_in_definition_order(monkeypatch) -> None:
    """two plugins for same hook → both fire in entry-point name order"""

async def test_dispatch_isolates_handler_exceptions(monkeypatch, caplog) -> None:
    """one handler raises → other handlers still fire, log ERROR records plugin+hook"""

async def test_dispatch_with_no_handlers_is_noop() -> None:
    """fast path: no entries for hook name → dispatch does not iterate"""

async def test_name_collision_first_wins(monkeypatch, caplog) -> None:
    """two plugins claim the same name → first wins, second logs WARNING"""
```

## Acceptance Criteria

- [ ] All twelve test cases above implemented and passing
- [ ] Tests use `monkeypatch` on `importlib.metadata.entry_points`, no real package install
- [ ] Coverage for `core/plugins.py` ≥ 95%
- [ ] `poe test:unit` passes

## Blocked by

- `featcore-add-plugin-protocol-and-registry-module` (PluginRegistry exists)

## Parent

- Epic: `epic-plugins-registry-and-lifecycle-hooks`
