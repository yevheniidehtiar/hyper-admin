---
type: story
id: vnZdSiPuKMyA
title: "feat(auth): auto-register User/Group/Permission when auth_backend is set"
status: done
priority: medium
assignee: null
labels:
  - enhancement
  - agent-task
  - area:core
  - area:auth
  - size:S
estimate: null
epic_ref: null
github:
  issue_number: 361
  repo: yevheniidehtiar/hyper-admin
  last_sync_hash: sha256:ce4e97ee7ec10b79df3396cafa353c2e16abe46a2fc523f9d68aee24aab53c6b
  synced_at: 2026-04-07T17:23:23.791Z
created_at: 2026-03-31T08:42:15Z
updated_at: 2026-03-31T16:54:32Z
---

## Context

5 of 7 auth E2E tasks are implemented. This wires the last missing piece: auth models (User, Group, Permission) auto-registered in the admin site when `auth_backend` is configured.

## Scenarios

**Scenario: auth models appear in admin sidebar when auth is enabled**
  Given Admin is configured with `auth_backend=SessionAuthBackend(engine)`
  When  `admin.mount("/admin")` is called
  Then  `site._registry` contains User, Group, and Permission models
  And   User is registered with `can_delete=False`
  And   User `list_filter` includes `is_active` and `is_superuser`
  And   Permission is registered with `can_create=False, can_delete=False`

## Acceptance criteria

- [ ] `_register_auth_models()` added to `core/app.py`, called from `mount()` when `auth_backend` is set
- [ ] User registered with `can_delete=False`, `list_filter=["is_active", "is_superuser"]`
- [ ] Permission registered with `can_create=False, can_delete=False`
- [ ] Group registered with default options
- [ ] Skip silently if model already registered
- [ ] Unit test in `tests/unit/test_auth_auto_register.py`

## Files likely affected

- `src/hyperadmin/core/app.py` — modify `mount()`, add `_register_auth_models()`

## Dependencies

None

## Notes for implementer

The existing `site.register()` in `core/registry.py` raises `ValueError` on duplicate. Guard with `if Model not in site._registry` before calling. Two-phase timing: models registered at `mount()` time, DB tables created in `on_event("startup")`. Do NOT place model registration inside the startup handler.

```python
def _register_auth_models(self) -> None:
    from hyperadmin.core.registry import site
    from hyperadmin.auth.models import User, Group, Permission
    from hyperadmin.core.options import AdminOptions

    if User not in site._registry:
        site.register(User, options=AdminOptions(
            can_delete=False, list_filter=["is_active", "is_superuser"],
        ))
    if Group not in site._registry:
        site.register(Group)
    if Permission not in site._registry:
        site.register(Permission, options=AdminOptions(can_create=False, can_delete=False))
```
