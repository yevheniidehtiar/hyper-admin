---
type: story
id: CgOAggzt_Geh
title: "test(e2e): end-to-end spans and events against logfire test sink"
status: todo
priority: high
assignee: null
labels:
  - testing
  - size:M
  - planned
  - plugins
  - observability
  - e2e
estimate: null
epic_ref:
  id: Plo-enMpTWhB
created_at: 2026-05-05T00:00:00Z
updated_at: 2026-05-05T00:00:00Z
---

## Summary

End-to-end Playwright tests that drive a real admin (with `instrument_admin`
called) and assert spans and events land in a Logfire test sink. Proves the
full pipeline: HTTP → view → adapter wrapper → plugin hook → logfire span.

**Spec:** [`docs/specs/plugin-logfire.md`](../../../../docs/specs/plugin-logfire.md)

## Files to Change

- **New:** `plugins/hyperadmin-logfire/tests/e2e/test_end_to_end_spans.py`
- **New:** `plugins/hyperadmin-logfire/tests/e2e/test_disabled_plugin.py`
- **Modified:** `tests/e2e/conftest.py` — extend `app` fixture to optionally call
  `instrument_admin` when a `logfire_sink` fixture is in scope

## Test Functions (1:1 with epic scenarios)

```python
async def test_instrument_admin_attaches_plugin_and_emits_adapter_spans(
    page, logfire_sink, products_seeded
):
    """
    Scenario: instrument_admin attaches the plugin and emits adapter spans
      Given logfire is configured to capture spans in a test sink
      And   instrument_admin(admin) has been called
      When  the admin.products list view is requested
      Then  the test sink contains a span named "admin.adapter.list" with attribute model="Product"
    """

async def test_validation_failure_emits_a_structured_event(
    page, logfire_sink, products_seeded
):
    """Scenario: validation failure emits a structured event"""

async def test_failed_login_emits_an_auth_event(
    page, logfire_sink, alice_user
):
    """Scenario: failed login emits an auth event"""

async def test_plugin_no_ops_when_logfire_is_not_configured(
    page, products_seeded, caplog
):
    """Scenario: plugin no-ops when logfire is not configured"""

async def test_plugin_is_not_loaded_when_disabled(
    page, logfire_sink, products_seeded, admin_with_disabled_logfire
):
    """Scenario: plugin is not loaded when disabled"""
```

## Acceptance Criteria

- [ ] All five E2E tests above implemented and passing
- [ ] `logfire_sink` fixture stitched into the existing E2E `app` fixture
- [ ] Inline `# Given / # When / # Then` comments in every test
- [ ] Tests run as part of `poe test:e2e` and CI

## Blocked by

- `featpluginlogfire-instrumentedadapter-via-onbeforeafter-adapter-call`
- `featpluginlogfire-emit-validation-error-events`
- `featpluginlogfire-emit-auth-events`

## Parent

- Epic: `epic-plugin-logfire-first-plugin`
