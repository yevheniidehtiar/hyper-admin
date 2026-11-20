# Authentication & Permissions

HyperAdmin has two auth modes. With **built-in auth** the admin keeps its own users, groups and
permissions in the `hyperadmin_*` tables (`User`, `Group`, `Permission`) and signs users in with
`SessionAuthBackend`. With **bring your own auth** you pass `Admin(auth=ExternalAuth(...))` and
the host application decides who the user is and what they may do; see
[Bring Your Own Auth](../guides/external-auth.md).

```python
from hyperadmin import Admin
from hyperadmin.auth.permissions import ModelPermissionChecker, PermissionSyncService
from hyperadmin.auth.session import SessionAuthBackend

admin = Admin(
    app,
    engine=engine,
    auth_backend=SessionAuthBackend(engine),
    permission_checker=ModelPermissionChecker(engine),
    permission_registry=PermissionSyncService(engine),
)
```

`hyperadmin.auth.metadata()` returns the built-in tables as an Alembic `target_metadata`.

## Permission codenames

The admin asks for `view_<model>`, `add_<model>`, `change_<model>`, `delete_<model>` and, for a
custom action, `action_<name>`. `<model>` is the lowercased model class name.

A detail-page panel checks `view_<model>_panel_<slug>`, or the `permission=` it was declared with.

!!! warning "Built-in auth does not create action and panel permissions"
    At startup `PermissionSyncService` creates the four `view_`, `add_`, `change_` and `delete_`
    codenames for every registered model, plus the `(codename, name)` pairs listed in a
    `permissions` attribute of the model's `ModelAdmin`. It does not create the
    `action_<name>` codename a custom action checks, or the codename of a detail panel, so with
    built-in auth only a superuser can run such an action or see such a panel until the
    codename exists in `hyperadmin_permissions` (create it yourself, or list it in
    `permissions`). The `action_<name>` codename does not include the model name, so two models
    with an action of the same name share one permission.

## Caches

`ModelPermissionChecker` remembers the permission set it read on the user object for the rest of
the request; call `forget_user_permissions(user)` after a write that changes it. With
`user_cache_ttl` set, the signed-in user is also cached per worker; call
`invalidate_user(user_id)` after you change a user outside the admin.

## API Reference

::: hyperadmin.auth.ExternalAuth

::: hyperadmin.auth.TokenCookie

::: hyperadmin.auth.session.SessionAuthBackend

::: hyperadmin.auth.permissions.ModelPermissionChecker

::: hyperadmin.auth.permissions.PermissionSyncService

::: hyperadmin.auth.permissions.forget_user_permissions

::: hyperadmin.auth.user_cache.invalidate_user

::: hyperadmin.auth.metadata

::: hyperadmin.auth.User

::: hyperadmin.auth.Group

::: hyperadmin.auth.Permission
