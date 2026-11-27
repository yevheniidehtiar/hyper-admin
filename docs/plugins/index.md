# Plugins

A HyperAdmin plugin is a Python package that extends the admin without a fork. A plugin can:

- add pages, sidebar links, templates, static files and permission codenames to the admin;
- observe what the admin does through [lifecycle hooks](hooks.md): model registration, create,
  update and delete, adapter calls, form validation errors and sign-in events.

Plugins are trusted code. They run in your application's process with full access to it, so
install only plugins you would also import by hand.

## First-party plugins

| Plugin | What it adds | Docs |
|---|---|---|
| `hyperadmin-tasks` | A background task dashboard backed by Postgres | [Background Tasks](tasks.md) |
| `hyperadmin-reports` | Crosstab reports, SVG charts, CSV and XLSX export, a home-page dashboard | [Reports and Dashboard](reports.md) |
| `hyperadmin-logfire` | Admin traces in Pydantic Logfire | [Logfire Traces](logfire.md) |

## Install a plugin

Install the plugin's package into the same environment as your application:

```bash
pip install hyperadmin-foo
```

That is all. Each plugin declares itself in the `hyperadmin.plugins` entry-point group, and
`Admin(...)` loads every entry point of that group when it is constructed. There is no list of
plugins to maintain in your code.

A plugin with settings reads them from `plugin_settings`, keyed by plugin name:

```python
admin = Admin(app, engine=engine, plugin_settings={"foo": {"page_size": 100}})
```

The plugin's own documentation lists the keys. Invalid settings do not stop the admin: the plugin
is skipped and the error is logged.

## Disable a plugin

There are two ways to keep an installed plugin from loading. Both take plugin names (the
entry-point name, for example `tasks`, not the package name `hyperadmin-tasks`).

In code:

```python
admin = Admin(app, engine=engine, disabled_plugins=["foo"])
```

Or with an environment variable, comma-separated:

```bash
HYPERADMIN_DISABLED_PLUGINS=foo,bar
```

The two lists are added together, so a plugin disabled in the environment cannot be turned back on
in code. A name that matches no installed plugin is ignored.

To skip entry-point discovery entirely, set `HyperAdminSettings(plugins_enabled=False)` or
`HYPERADMIN_PLUGINS_ENABLED=false`. You can still register a plugin object by hand before
`admin.mount()`:

```python
admin.plugins.register(MyPlugin(), admin=admin)
admin.mount("/admin")
```

A plugin is loaded once, at startup. Installing, removing or disabling a plugin takes effect after
a restart.

## See which plugins are installed

```bash
hyperadmin plugins list
```

```text
NAME                     CLASS                                            STATUS
logfire                  hyperadmin_logfire.plugin:LogfirePlugin          active
reports                  hyperadmin_reports.plugin:ReportsPlugin          active
tasks                    hyperadmin_tasks.plugin:TasksPlugin              active
```

The command reads the installed entry points without importing the plugins or starting your
application. For that reason `STATUS` reflects `HYPERADMIN_DISABLED_PLUGINS` only: a plugin
disabled with `Admin(disabled_plugins=...)` still shows as `active`, and so does a plugin that
fails to load. With no plugins installed the command prints `No plugins discovered.`

To see what a running admin actually loaded, ask its registry:

```python
admin.plugins.names()    # ['logfire', 'reports', 'tasks', ...]
admin.plugins.skipped    # {'foo': 'disabled', 'bar': 'load_error'}
```

`names()` also lists pages HyperAdmin registers through the same registry, such as the permission
matrix. The reasons in `skipped` are:

| Reason | Meaning |
|---|---|
| `disabled` | The name is in `disabled_plugins` or `HYPERADMIN_DISABLED_PLUGINS`. |
| `load_error` | Importing or instantiating the plugin raised, for example a missing dependency. |
| `invalid` | The entry point is not a plugin, or its `name` differs from the entry-point name. |
| `register_error` | The settings failed validation, or the plugin's `on_register` raised. |

## When a plugin fails

A broken plugin never takes the admin down:

- A plugin that fails to import, validate its settings or register is logged at `ERROR` and
  skipped. Everything it had contributed up to that point is rolled back.
- A hook that raises during a request is logged at `ERROR` with the plugin and hook names. The
  other plugins still get the hook and the request continues.

Each log record carries `plugin` (and `hook`, where one applies) as extra fields, on the
`hyperadmin.core.plugins` logger.

## Write your own

- [Writing a plugin](authoring.md): a first plugin, step by step, with a test.
- [Hook reference](hooks.md): every hook, its arguments and when it fires.
