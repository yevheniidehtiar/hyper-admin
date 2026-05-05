---
type: story
id: mzMHxg0eqXhQ
title: "feat(adapters): wrap BaseAdapter with on_before/after_adapter_call hooks"
status: todo
priority: high
assignee: null
labels:
  - backend
  - size:M
  - planned
  - plugins
  - adapters
estimate: null
epic_ref:
  id: um1zqB0-b2AZ
created_at: 2026-05-05T00:00:00Z
updated_at: 2026-05-05T00:00:00Z
---

## Summary

Introduce `_AdapterHookWrapper(BaseAdapter)` that delegates every method to an
inner adapter and dispatches `on_before_adapter_call` / `on_after_adapter_call`
around each call. Wrap at `SiteRegistry.register()` boundary so concrete adapters
(`SQLModelAdapter`, `SQLAlchemyAdapter`) stay clean.

**Spec:** [`docs/specs/plugin-registry.md`](../../../../docs/specs/plugin-registry.md)

## Files to Change

- **Modified:** `src/hyperadmin/core/plugins.py` — add `_AdapterHookWrapper`
- **Modified:** `src/hyperadmin/core/registry.py:20-69` — wrap adapter at registration

## Design

```python
# core/plugins.py
class _AdapterHookWrapper(BaseAdapter):
    def __init__(self, *, inner: BaseAdapter, admin: "Admin", model: type) -> None:
        self._inner = inner
        self._admin = admin
        self._model = model

    async def list(self, **kwargs):
        self._admin.dispatch_hook(
            "on_before_adapter_call",
            admin=self._admin, model=self._model, op="list", kwargs=kwargs,
        )
        result = await self._inner.list(**kwargs)
        self._admin.dispatch_hook(
            "on_after_adapter_call",
            admin=self._admin, model=self._model, op="list", result=result,
        )
        return result

    # similar wrappers for: get, create, update, delete, get_related,
    # get_choices, save_inline_rows, get_schema, get_queryset
```

Methods that mutate state (`create`, `update`, `delete`, `save_inline_rows`) fire
`before` then `after`. Read methods (`list`, `get`, `get_related`, `get_choices`,
`get_schema`, `get_queryset`) also fire both — observability shouldn't be
read/write-asymmetric.

Zero-overhead path: if `not self._admin.plugins` → `SiteRegistry.register` skips
the wrap entirely, returning the bare adapter.

```python
# core/registry.py — inside register()
adapter = adapter_cls(model, engine=...)
if self._admin.plugins:
    adapter = _AdapterHookWrapper(inner=adapter, admin=self._admin, model=model)
self._models[model] = (adapter, options)
```

## Scenarios

**Scenario: adapter call hooks wrap every CRUD operation**
  Given a plugin records (op, model) tuples in on_before_adapter_call / on_after_adapter_call
  When  the list, create, update, delete views are exercised once each for Product
  Then  the recorded tuples include ("list","Product"), ("create","Product"), ("update","Product"), ("delete","Product") in order
  And   each "before" precedes its matching "after"

**Scenario: wrapper is transparent when no plugins are loaded**
  Given Admin is constructed with no entry points present
  When  SiteRegistry.register(Product) is called
  Then  _models[Product][0] is the bare adapter, not _AdapterHookWrapper

**Scenario: inner adapter exception still bubbles, but on_after still fires** (decision: NO — see Decision Log in SDD)
  *Removed — exceptions short-circuit on_after to mirror sync semantics. Document in design.*

## Acceptance Criteria

- [ ] `_AdapterHookWrapper` covers all 9 `BaseAdapter` methods
- [ ] Wrapping is conditional on `bool(admin.plugins)` — zero overhead path verified
- [ ] Hook order: before → inner → after; if inner raises, after does NOT fire
- [ ] `model` and `op` attributes attached to every hook call
- [ ] No regression in any adapter test
- [ ] Coverage for `_AdapterHookWrapper` ≥ 95%

## Blocked by

- `featcore-implement-app-level-hook-dispatcher`

## Parent

- Epic: `epic-plugins-registry-and-lifecycle-hooks`
