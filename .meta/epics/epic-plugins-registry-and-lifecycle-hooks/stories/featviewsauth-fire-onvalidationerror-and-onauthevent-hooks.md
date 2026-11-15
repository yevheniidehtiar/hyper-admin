---
type: story
id: Vq7nTd2KxHs_
title: "feat(views,auth): fire on_validation_error and on_auth_event hooks"
status: todo
priority: high
assignee: null
labels:
  - backend
  - size:M
  - planned
  - plugins
  - views
  - auth
estimate: null
epic_ref:
  id: um1zqB0-b2AZ
created_at: 2026-11-11T00:00:00Z
updated_at: 2026-11-11T00:00:00Z
---

## Summary

Fire the two hooks the registry SDD added for `hyperadmin-logfire` (2026-11-07):
`on_validation_error` from the create and update handlers, and `on_auth_event` from the
login and logout views and from the view permission check. The hook names are already in the
dispatcher's allowed list in the SDD; nothing in `src/` fires them yet.

**Spec:** [`docs/specs/plugin-registry.md`](../../../../docs/specs/plugin-registry.md), hook table
(`on_validation_error`, `on_auth_event`). Context: [`docs/specs/plugin-logfire.md`](../../../../docs/specs/plugin-logfire.md) §Hooks.

## Files to Change

- **Modified:** `src/hyperadmin/views/dynamic.py` — `create_view` and `update_view`: fire
  `on_validation_error` when the form returns errors; fire `on_auth_event(permission_denied)`
  where the view permission check returns False.
- **Modified:** `src/hyperadmin/auth/views.py` — fire `on_auth_event` for `login_success`,
  `login_failure` and `logout`.
- **Modified:** `src/hyperadmin/core/plugins.py` — add `on_validation_error` and
  `on_auth_event` to `LIFECYCLE_HOOKS`; today `dispatch_hook` rejects both with `ValueError`.
- **New:** `tests/unit/test_plugin_validation_auth_hooks.py`

## Design

```python
# create_view / update_view, when the form fails validation
self._admin.dispatch_hook(
    "on_validation_error",
    admin=self._admin,
    model=self._model,
    field_errors=field_errors,  # dict[str, list[str]] of field -> pydantic error TYPES
)
```

```python
# auth/views.py
admin.dispatch_hook("on_auth_event", admin=admin, event="login_failure",
                    user=None, username=username, request=request)
```

- `field_errors` carries pydantic error types (`"float_parsing"`), never input values.
- `user` is `None` on `login_failure`. The password is never passed.
- Use `has_handlers(name)` to skip the work when no plugin listens.
- Failure isolation comes from `dispatch_hook`; a failing handler must not change the response.

## Scenarios

**Scenario: a failed form emits on_validation_error**
  Given a plugin records the arguments of on_validation_error
  When  POST /admin/products/create with an invalid payload
  Then  the plugin received model "Product" and a non-empty field_errors
  And   the response is the same 4xx form re-render as before

**Scenario: field_errors never contain input values**
  Given a plugin records field_errors
  When  POST /admin/products/create with price="not-a-number"
  Then  the recorded error type is "float_parsing"
  And   the string "not-a-number" appears nowhere in field_errors

**Scenario: a failed login emits on_auth_event with no user**
  Given a plugin records on_auth_event
  When  POST /admin/login with username=alice password=wrong
  Then  the plugin received event "login_failure", user None, username "alice"
  And   the password is not among the arguments

**Scenario: a successful login and a logout emit events**
  Given a plugin records on_auth_event
  When  alice logs in and then logs out
  Then  the plugin received "login_success" for alice and then "logout"

**Scenario: a denied permission emits permission_denied**
  Given alice lacks the delete permission for Product
  When  POST /admin/products/1/delete
  Then  the plugin received event "permission_denied" for alice

**Scenario: a failing handler does not break the request**
  Given a plugin whose on_auth_event raises
  When  POST /admin/login with valid credentials
  Then  the login still succeeds

## Acceptance Criteria

- [ ] `on_validation_error` fires on every create/update form failure, with the SDD signature
- [ ] `on_auth_event` fires for login_success, login_failure, logout and permission_denied
- [ ] No input values and no password reach a hook
- [ ] No behaviour change when no plugin registers either hook
- [ ] 100% coverage of changed lines; `poe lint` and `poe test:unit` pass

## Blocked by

- `featcore-implement-app-level-hook-dispatcher`
- `featviews-fire-onbeforeafter-create-update-delete-around-views` (same handlers; merge it first to avoid conflicts in `views/dynamic.py`)

## Parent

- Epic: `epic-plugins-registry-and-lifecycle-hooks`
