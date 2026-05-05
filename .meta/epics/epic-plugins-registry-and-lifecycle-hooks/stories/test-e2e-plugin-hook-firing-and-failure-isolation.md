---
type: story
id: cGk6vHhW7bZC
title: "test(e2e): plugin hook firing and failure isolation through full request flow"
status: todo
priority: high
assignee: null
labels:
  - testing
  - size:M
  - planned
  - plugins
  - e2e
estimate: null
epic_ref:
  id: um1zqB0-b2AZ
created_at: 2026-05-05T00:00:00Z
updated_at: 2026-05-05T00:00:00Z
---

## Summary

End-to-end Playwright tests that exercise plugin hooks through real HTTP
requests against a running admin. Uses an in-test plugin registered via a
pytest fixture that monkeypatches `entry_points`.

**Spec:** [`docs/specs/plugin-registry.md`](../../../../docs/specs/plugin-registry.md)

## Files to Change

- **New:** `tests/e2e/test_plugin_hooks.py`
- **New:** `tests/e2e/_plugin_fixtures.py` — shared `RecordingPlugin` and `BrokenPlugin`
  classes plus a `plugins_registered` fixture that monkeypatches `entry_points`

## Test Functions (1:1 with epic scenarios)

```python
async def test_plugin_discovered_via_entry_point_on_admin_construction(
    page, recording_plugin
):
    """
    Scenario: plugin discovered via entry point on Admin construction
      Given a package "demo_plugin" exposes [project.entry-points."hyperadmin.plugins"] demo = "demo_plugin:DemoPlugin"
      When  Admin(app, engine=engine) is constructed
      Then  admin.plugins["demo"] is an instance of DemoPlugin
      And   demo.on_register(admin) was called exactly once
    """

async def test_disabled_plugin_is_not_loaded(page, recording_plugin_disabled):
    """Scenario: disabled plugin is not loaded"""

async def test_on_before_create_hook_fires_before_adapter_create(
    page, recording_plugin
):
    """Scenario: on_before_create hook fires before adapter create"""

async def test_hook_exception_is_logged_and_does_not_break_request(
    page, broken_plugin, caplog
):
    """Scenario: hook exception is logged and does not break the request"""

async def test_adapter_call_hooks_wrap_every_crud_operation(
    page, recording_plugin
):
    """Scenario: adapter call hooks wrap every CRUD operation"""
```

CLI scenario lives in unit tests (no E2E browser needed for stdout check).

## Acceptance Criteria

- [ ] All five E2E tests above implemented
- [ ] Use `data-testid` selectors per CLAUDE.md (no `.ha-*`)
- [ ] Inline `# Given / # When / # Then` comments in every test
- [ ] `poe test:e2e` passes locally and in CI
- [ ] Visual snapshots (if any added) committed

## Blocked by

- `featcore-fire-onmodelregister-from-siteregistry`
- `featadapters-wrap-baseadapter-with-onbeforeafter-adapter-call-hooks`
- `featviews-fire-onbeforeafter-create-update-delete-around-views`

## Parent

- Epic: `epic-plugins-registry-and-lifecycle-hooks`
