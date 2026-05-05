---
type: story
id: kq5T3v-StZC6
title: "test(unit): adapter spans, validation/auth events, no-config no-op"
status: todo
priority: high
assignee: null
labels:
  - testing
  - size:M
  - planned
  - plugins
  - observability
estimate: null
epic_ref:
  id: Plo-enMpTWhB
created_at: 2026-05-05T00:00:00Z
updated_at: 2026-05-05T00:00:00Z
---

## Summary

Unit tests for `LogfirePlugin` using Logfire's test sink utility. No real
admin app — just direct hook invocation against the plugin instance.

**Spec:** [`docs/specs/plugin-logfire.md`](../../../../docs/specs/plugin-logfire.md)

## Files to Change

- **New:** `plugins/hyperadmin-logfire/tests/unit/test_plugin.py`
- **New:** `plugins/hyperadmin-logfire/tests/unit/test_adapter_spans.py`
- **New:** `plugins/hyperadmin-logfire/tests/unit/test_no_logfire_config.py`
- **New:** `plugins/hyperadmin-logfire/tests/unit/conftest.py` — `logfire_sink` fixture

## Test Cases

```python
# test_plugin.py
def test_plugin_name_attribute(): ...
def test_on_register_logs_info(caplog): ...
def test_runtime_checkable_protocol_satisfaction(): ...

# test_adapter_spans.py
def test_open_close_emits_admin_adapter_op_span(logfire_sink, fake_model): ...
def test_span_includes_model_and_op_attrs(logfire_sink, fake_model): ...
def test_safe_attrs_for_list_op_includes_paging(logfire_sink, fake_model): ...
def test_nested_calls_produce_nested_spans(logfire_sink, fake_model): ...
def test_close_with_empty_stack_logs_warning_no_crash(caplog): ...
def test_validation_error_event_emitted_with_field_errors(logfire_sink, fake_model): ...
def test_non_serialisable_field_errors_stringified(logfire_sink, fake_model): ...
def test_auth_login_failure_emitted_at_warn_level(logfire_sink): ...
def test_auth_login_success_emitted_at_info_level(logfire_sink): ...
def test_unknown_auth_event_type_ignored(logfire_sink): ...

# test_no_logfire_config.py
def test_warning_emitted_once_when_logfire_not_configured(caplog): ...
def test_no_spans_emitted_when_logfire_not_configured(caplog): ...
def test_instrument_admin_skips_when_plugin_disabled(mock_admin_disabled): ...
```

## Acceptance Criteria

- [ ] All test cases above implemented and passing
- [ ] `logfire_sink` fixture works under pytest-asyncio (smoke-tested in SDD review)
- [ ] Coverage for `hyperadmin_logfire/` ≥ 90%
- [ ] `poe test:unit` includes the new package

## Blocked by

- `featpluginlogfire-instrumentedadapter-via-onbeforeafter-adapter-call`

## Parent

- Epic: `epic-plugin-logfire-first-plugin`
