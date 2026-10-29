# hyperadmin-tasks

First-party HyperAdmin plugin that adds a background task dashboard under `{prefix}/tasks`.

This package is the foundation scaffold: it registers the plugin, a "Tasks" sidebar section,
the `view_tasks` and `manage_tasks` permissions, and a placeholder dashboard page gated on
`view_tasks`. See `docs/specs/plugin-tasks.md` for the full design.

Disable it with `disabled_plugins=["tasks"]`.
