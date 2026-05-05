---
type: story
id: MD1z52Kl1dil
title: "feat(plugin-logfire): emit admin.auth.* events"
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

Wire `LogfirePlugin.on_auth_event` to emit
`admin.auth.{login_success,login_failure,logout,permission_denied}` events.

**Spec:** [`docs/specs/plugin-logfire.md`](../../../../docs/specs/plugin-logfire.md)

## Files to Change

- **Modified:** `plugins/hyperadmin-logfire/src/hyperadmin_logfire/plugin.py` —
  add `on_auth_event` method
- **New:** `plugins/hyperadmin-logfire/src/hyperadmin_logfire/auth_events.py`

**Cross-epic dependency:** the `on_auth_event` hook must be defined and fired
by core. That is added as part of the **Epic 1 SDD revision** triggered by this
epic. The fire sites live in:
- `src/hyperadmin/auth/` middleware (login_success, login_failure, logout)
- `src/hyperadmin/views/dynamic.py` (permission_denied — when a request hits a
  view but the model-level or object-level permission check returns False)

## Design

```python
# auth_events.py
import logfire

EVENT_NAMES = {
    "login_success": "admin.auth.login_success",
    "login_failure": "admin.auth.login_failure",
    "logout": "admin.auth.logout",
    "permission_denied": "admin.auth.permission_denied",
}


def emit(event_type: str, *, user, **ctx) -> None:
    name = EVENT_NAMES.get(event_type)
    if name is None:
        return  # unknown event type — silently ignore (forward compatible)
    attrs = {"user": getattr(user, "username", None) if user else None, **ctx}
    if event_type == "login_failure":
        logfire.warn(name, **attrs)
    else:
        logfire.info(name, **attrs)
```

```python
# plugin.py — addition
class LogfirePlugin:
    ...
    def on_auth_event(self, admin, event_type, user, **ctx):
        from .auth_events import emit
        emit(event_type, user=user, **ctx)
```

## Scenarios

**Scenario: failed login emits an auth event**
  Given logfire is configured to capture events
  When  POST /admin/login with username=alice password=wrong
  Then  the sink contains an event "admin.auth.login_failure" with attribute username="alice"

**Scenario: successful login emits an auth event**
  Given logfire is configured to capture events
  When  POST /admin/login with valid credentials for alice
  Then  the sink contains an event "admin.auth.login_success" with attribute user="alice"

**Scenario: permission denied emits an auth event with codename context**
  Given alice does not have the "delete" permission for Product
  When  POST /admin/products/1/delete
  Then  the sink contains an event "admin.auth.permission_denied" with attributes user="alice", codename="delete", model="Product"

**Scenario: unknown event_type is silently ignored**
  Given a future core version emits on_auth_event with event_type="something_new"
  When  the plugin is the current version
  Then  no exception is raised
  And   no logfire event is emitted

## Acceptance Criteria

- [ ] All four event types (`login_success`, `login_failure`, `logout`, `permission_denied`) emitted with appropriate level (warn for failure, info for others)
- [ ] User attribute always present (None for failure pre-resolution)
- [ ] Unknown event types ignored (forward compatibility)
- [ ] Unit test for each event type

## Blocked by

- `featpluginlogfire-implement-logfireplugin-and-instrumentadmin`
- Epic 1: `on_auth_event` fire sites added (covered by Epic 1 view-hooks story
  + auth-middleware additions, both gated behind the Epic 1 SDD update for the
  two new hooks)

## Parent

- Epic: `epic-plugin-logfire-first-plugin`
