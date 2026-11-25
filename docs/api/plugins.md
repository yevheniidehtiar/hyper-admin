# Plugins

A plugin is a package that declares an entry point in the `hyperadmin.plugins` group and
provides an object that satisfies the `Plugin` protocol. `Admin` discovers installed plugins,
validates their settings and calls `on_register(admin)` before the admin is mounted.

```toml
# the plugin's pyproject.toml
[project.entry-points."hyperadmin.plugins"]
reports = "my_reports.plugin:ReportsPlugin"
```

```python
from fastapi import APIRouter

from hyperadmin import Admin


class ReportsPlugin:
    name = "reports"

    def on_register(self, admin: Admin) -> None:
        router = APIRouter()
        admin.plugins.add_page(self, router, prefix="/reports")
        admin.plugins.add_nav_entry(self, label="Reports", url_name="reports-index")
        admin.plugins.add_permission(self, "view_report_sales")
```

From `on_register` a plugin may call `add_page`, `add_nav_entry`, `add_template_dir`,
`set_static_dir` and `add_permission`. These are the public registry methods
(see [What is public API](../versioning.md#what-is-public-api)); the other methods of
`PluginRegistry` are used by `Admin` itself. Pass `disabled_plugins=` or set
`HYPERADMIN_DISABLED_PLUGINS` to skip a plugin, and `plugin_settings=` to configure one.

## Lifecycle hooks

`LIFECYCLE_HOOKS` lists the names of the lifecycle hooks a plugin may implement as methods.
HyperAdmin calls them with keyword arguments only, so write them to accept extra keyword
arguments (`**kwargs`). A hook that raises is logged on the `hyperadmin.core.plugins` logger
and skipped; it never breaks the request or the other plugins. When each hook fires is
described in the [hook reference](../plugins/hooks.md).

| Hook | Keyword arguments |
|---|---|
| `on_model_register` | `admin, model, options` |
| `on_before_create` / `on_after_create` | `admin, model, data` / `admin, model, instance` |
| `on_before_update` / `on_after_update` | `admin, model, pk, data` / `admin, model, instance` |
| `on_before_delete` / `on_after_delete` | `admin, model, pk` |
| `on_before_adapter_call` / `on_after_adapter_call` | `admin, model, op, kwargs` / `admin, model, op, result, error` |
| `on_validation_error` | `admin, model, field_errors` |
| `on_auth_event` | `admin, event, user, username, request` (and `model` for `permission_denied`) |

## API Reference

::: hyperadmin.core.plugins.Plugin

::: hyperadmin.core.plugins.PluginRegistry

::: hyperadmin.core.plugins.PluginError

::: hyperadmin.core.plugins.LIFECYCLE_HOOKS
