---
type: story
id: EUbD-9hQBaVC
title: "feat(views): fire on_before/after_create/update/delete around CRUD views"
status: todo
priority: high
assignee: null
labels:
  - backend
  - size:M
  - planned
  - plugins
  - views
estimate: null
epic_ref:
  id: um1zqB0-b2AZ
created_at: 2026-05-05T00:00:00Z
updated_at: 2026-05-05T00:00:00Z
---

## Summary

Fire app-level `on_before_create` / `on_after_create` / `on_before_update` /
`on_after_update` / `on_before_delete` / `on_after_delete` hooks from
`DynamicModelView` create, update, and delete handlers. These complement (not
replace) the model-level `before_save` / `after_save` hooks on
`HyperAdminModel` — model-level hooks remain for per-model logic; app-level hooks
are for cross-cutting plugins.

**Spec:** [`docs/specs/plugin-registry.md`](../../../../docs/specs/plugin-registry.md)

## Files to Change

- **Modified:** `src/hyperadmin/views/dynamic.py` — `create_view`, `update_view`,
  `delete_view` handlers

## Design

In each handler, after validation succeeds and before the adapter call:

```python
# create_view
self._admin.dispatch_hook(
    "on_before_create", admin=self._admin, model=self._model, data=validated_data,
)
instance = await self._adapter.create(validated_data)
self._admin.dispatch_hook(
    "on_after_create", admin=self._admin, model=self._model, instance=instance,
)
```

Update / delete follow the same pattern with their respective signatures
(see SDD hook table). All hooks fire SYNCHRONOUSLY in the request flow; failure
isolation comes from `dispatch` itself.

If the adapter call raises, `on_after_*` does NOT fire (mirrors the
adapter-wrapper semantics).

## Scenarios

**Scenario: on_before_create hook fires before adapter create**
  Given a plugin registers an on_before_create hook that appends model_name to a list
  When  POST /admin/products/create with valid data
  Then  the hook list contains "Product" before the row exists in the DB

**Scenario: on_after_update hook receives the updated instance**
  Given a plugin records the instance.id in on_after_update
  When  POST /admin/products/42/update with valid data
  Then  the recorded id is 42

**Scenario: on_before_delete fires before delete; on_after_delete fires after**
  Given a plugin records hook order
  When  POST /admin/products/42/delete
  Then  the recorded order is ["before_delete", "after_delete"]

**Scenario: validation failure prevents on_before_create from firing**
  Given POST /admin/products/create with invalid data (returns 400)
  When  the request completes
  Then  on_before_create was not called
  And   the validation_error event will be wired in the next story (deferred)

## Acceptance Criteria

- [ ] All six hooks fire from the correct handlers in `views/dynamic.py`
- [ ] `before` fires only after validation succeeds
- [ ] `after` fires only after the adapter call succeeds
- [ ] Hook signatures match the SDD's hook table exactly
- [ ] No regression in existing CRUD view tests
- [ ] `poe lint` and `poe test:unit` pass

## Blocked by

- `featcore-implement-app-level-hook-dispatcher`

## Parent

- Epic: `epic-plugins-registry-and-lifecycle-hooks`
