---
type: story
id: k0Q9LnzMo_GA
title: "feat(plugin-logfire): emit admin.validation_error events"
status: todo
priority: high
assignee: null
labels:
  - backend
  - size:S
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

Wire `LogfirePlugin.on_validation_error` to emit a structured
`admin.validation_error` event whenever an admin form fails validation. Enables
dashboards: validation failure rate per model, most-failing fields, error
message distribution.

**Spec:** [`docs/specs/plugin-logfire.md`](../../../../docs/specs/plugin-logfire.md)

## Files to Change

- **Modified:** `plugins/hyperadmin-logfire/src/hyperadmin_logfire/plugin.py` —
  add `on_validation_error` method

**Cross-epic dependency:** the `on_validation_error` hook must be defined and
fired by core. That is added as part of the **Epic 1 SDD revision** triggered
by this epic. The fire site lives in `src/hyperadmin/views/dynamic.py` (or
wherever `PydanticForm.validate()` is called) and follows the
`featviews-fire-onbeforeafter-create-update-delete-around-views` story's
pattern.

## Design

```python
# plugin.py — addition
import logfire

class LogfirePlugin:
    ...
    def on_validation_error(self, admin, model, field_errors):
        # field_errors is a dict[str, list[str]] (field_name -> [messages])
        logfire.warn(
            "admin.validation_error",
            model=model.__name__,
            field_errors=_stringify(field_errors),
            error_count=sum(len(v) for v in field_errors.values()),
        )

def _stringify(errors: dict) -> dict:
    """Coerce non-serialisable values to strings."""
    return {k: [str(m) for m in v] for k, v in errors.items()}
```

## Scenarios

**Scenario: validation failure emits a structured event**
  Given logfire is configured to capture events
  When  POST /admin/products/create with an invalid payload
  Then  the sink contains an event "admin.validation_error" with attributes model="Product" and field_errors non-empty

**Scenario: non-serialisable error values are stringified**
  Given a field validator raises a custom exception with __str__ output
  When  the form fails validation
  Then  the recorded field_errors values are all strings (no non-serialisable objects)

## Acceptance Criteria

- [ ] `admin.validation_error` event emitted on every form validation failure
- [ ] Event attributes: `model`, `field_errors`, `error_count`
- [ ] Non-serialisable values stringified
- [ ] Unit test using logfire test sink

## Blocked by

- `featpluginlogfire-implement-logfireplugin-and-instrumentadmin`
- Epic 1: `featviews-fire-onbeforeafter-create-update-delete-around-views`
  (where `on_validation_error` is fired from)

## Parent

- Epic: `epic-plugin-logfire-first-plugin`
