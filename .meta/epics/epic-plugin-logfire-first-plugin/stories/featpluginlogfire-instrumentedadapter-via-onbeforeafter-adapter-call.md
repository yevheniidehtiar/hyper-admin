---
type: story
id: UheQE0jlCmFL
title: "feat(plugin-logfire): InstrumentedAdapter spans via on_before/after_adapter_call"
status: todo
priority: high
assignee: null
labels:
  - backend
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

Implement adapter span emission. `LogfirePlugin.on_before_adapter_call` opens a
`admin.adapter.<op>` span and stashes it in a `contextvar`;
`on_after_adapter_call` retrieves and closes it. Span attributes include
`model` and `op` plus per-op kwargs (paging, search, filters).

**Spec:** [`docs/specs/plugin-logfire.md`](../../../../docs/specs/plugin-logfire.md)

## Files to Change

- **New:** `plugins/hyperadmin-logfire/src/hyperadmin_logfire/adapter_spans.py`
- **Modified:** `plugins/hyperadmin-logfire/src/hyperadmin_logfire/plugin.py` —
  add `on_before_adapter_call` / `on_after_adapter_call` methods

## Design

```python
# adapter_spans.py
from contextvars import ContextVar
import logfire

# Stack of open spans — supports nested adapter calls (e.g. get_related from list)
_open_spans: ContextVar[list] = ContextVar("hyperadmin_logfire_open_spans", default=None)


def _safe_attrs(op: str, kwargs: dict) -> dict:
    """Whitelist of attrs per op to avoid leaking PII or huge payloads."""
    if op == "list":
        return {
            "page": kwargs.get("page"),
            "page_size": kwargs.get("page_size"),
            "search": kwargs.get("search"),
            "has_filters": bool(kwargs.get("filters")),
        }
    if op in ("get", "delete"):
        return {"pk": str(kwargs.get("pk"))}
    if op in ("create", "update"):
        return {"field_count": len(kwargs.get("data", {}))}
    if op == "get_choices":
        return {"field": kwargs.get("field"), "limit": kwargs.get("limit")}
    return {}


def open_span(*, model, op, kwargs):
    span = logfire.span(f"admin.adapter.{op}", model=model.__name__, **_safe_attrs(op, kwargs))
    span.__enter__()
    stack = _open_spans.get() or []
    stack = [*stack, span]
    _open_spans.set(stack)


def close_span(*, model, op, result):
    stack = _open_spans.get() or []
    if not stack:
        log.warning("logfire adapter span close called but no open span found", extra={"model": model.__name__, "op": op})
        return
    span = stack[-1]
    _open_spans.set(stack[:-1])
    if op == "list" and isinstance(result, (list, tuple)):
        span.set_attribute("result_count", len(result))
    span.__exit__(None, None, None)
```

```python
# plugin.py — additions
class LogfirePlugin:
    name = "logfire"

    def on_before_adapter_call(self, admin, model, op, kwargs):
        from .adapter_spans import open_span
        open_span(model=model, op=op, kwargs=kwargs)

    def on_after_adapter_call(self, admin, model, op, result):
        from .adapter_spans import close_span
        close_span(model=model, op=op, result=result)
```

## Scenarios

**Scenario: adapter span emitted with model attribute**
  Given logfire test sink active and instrument_admin(admin) called
  When  GET /admin/products/ is requested
  Then  the sink contains a span "admin.adapter.list" with attributes model="Product", page=1, page_size=10

**Scenario: nested adapter call produces nested spans**
  Given instrument_admin(admin) is called
  When  the list view triggers a get_choices for an FK field on the same request
  Then  the sink contains an "admin.adapter.list" span with a child "admin.adapter.get_choices" span

**Scenario: missing close span is logged but does not crash**
  Given the contextvar stack is empty
  When  on_after_adapter_call is called manually
  Then  a WARNING log is emitted
  And   no exception is raised

## Acceptance Criteria

- [ ] Spans named `admin.adapter.<op>` for all 9 BaseAdapter operations
- [ ] Span attributes: `model`, plus op-specific safe attrs (no PII / large payloads)
- [ ] Nested calls produce nested spans (contextvar stack)
- [ ] Missing-stack edge case logged, not crashed
- [ ] Unit tests using a logfire test sink — see next story

## Blocked by

- `featpluginlogfire-implement-logfireplugin-and-instrumentadmin`
- Epic 1: `featadapters-wrap-baseadapter-with-onbeforeafter-adapter-call-hooks`

## Parent

- Epic: `epic-plugin-logfire-first-plugin`
