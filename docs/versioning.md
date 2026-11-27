# Versioning & Deprecation Policy

This page says what you can rely on when you upgrade HyperAdmin: which parts of the library
are public API, what each kind of release may change, how a feature is retired, and which
Python and dependency versions are supported.

!!! note "Current status: pre-release"
    HyperAdmin is at `0.5.0a1`, an alpha. The rules under [Before 1.0](#before-10) apply today.
    The rules under [From 1.0](#from-10) take effect with the 1.0.0 release.

## Version numbers

HyperAdmin follows [Semantic Versioning](https://semver.org/), written in the
[PEP 440](https://peps.python.org/pep-0440/) form that Python packaging requires:
`MAJOR.MINOR.PATCH`, with `aN`, `bN` and `rcN` suffixes for pre-releases (for example
`0.5.0a1`).

Installers skip pre-releases unless you ask for one, so pin the exact version while you use an
alpha, beta or release candidate:

```bash
pip install hyper-admin==0.5.0a1
```

Every release is described in the [Changelog](changelog.md), which follows
[Keep a Changelog](https://keepachangelog.com/).

## What is public API

The compatibility rules on this page cover the public API and nothing else.

| Surface | What is public |
|---|---|
| Python imports | Every name in `hyperadmin.__all__` (`from hyperadmin import Admin`, ...), and every class, function, method, parameter and attribute shown in the [API Reference](api/index.md) or used in a guide on this site, under the import path the documentation uses (for example `hyperadmin.core.registry.site`, `hyperadmin.core.options.AdminOptions`, `hyperadmin.core.model.ModelAdmin`, `hyperadmin.auth.ExternalAuth`, `hyperadmin.filters.DateRangeFilter`) |
| Settings | The field names of `HyperAdminSettings`, their types, and the matching `HYPERADMIN_*` environment variables |
| Templates | The template names and the lookup order described in [Override templates](getting-started.md#override-templates), and the blocks of `_base.html` (`title`, `messages`, `navbar`, `sidebar`, `content`, `command_palette`, `shortcuts_overlay`), `list_layout.html` (`list_container`), `form_layout.html` (`form_title`, `form_header_actions`, `form_body`, `form_actions`) and `detail_layout.html` (`detail_title`, `detail_actions`, `detail_fields`) |
| Test hooks | The `data-testid` values in the [`data-testid` reference](https://github.com/yevheniidehtiar/hyper-admin/blob/develop/CLAUDE.md#data-testid-reference). Use them, or accessible roles and labels, in your own browser tests |
| Theming | The `--ha-*` CSS custom properties listed under [Design Tokens](frontend/overview.md#design-tokens) |
| Plugins | The `hyperadmin.plugins` entry-point group; the `Plugin` protocol (`name`, `on_register(admin)`, the optional `settings_model`); the `PluginRegistry` methods a plugin calls from `on_register` (`add_page`, `add_nav_entry`, `add_template_dir`, `set_static_dir`, `add_permission`, `set_home_page`); and the lifecycle hook names in `hyperadmin.core.plugins.LIFECYCLE_HOOKS`. Hooks are called with keyword arguments only |
| Command line | The `hyperadmin` commands `createsuperuser` and `init-db`, their option names, and an exit status of `0` for success and non-zero for failure |
| Permissions | The codename format `<action>_<model>` (`view_`, `add_`, `change_`, `delete_` and `action_<name>_<model>`), the detail-panel codename `view_<model>_panel_<slug>`, and the `ModelAdmin.permissions` list of extra codenames described in [Bring Your Own Auth](guides/external-auth.md#permissions) |
| Database tables | The names of the built-in `hyperadmin_*` tables. A release that adds a column or a table lists it under [Upgrading the built-in auth tables](guides/existing-app.md#upgrading-the-built-in-auth-tables) |

### What is not public

These can change in any release, without a deprecation period:

- Any module, class, function or attribute whose name starts with an underscore.
- Anything importable from `hyperadmin` that this site does not document. Being importable is
  not a promise.
- The documents under `docs/specs/` and `docs/design/`. They record how a feature was designed,
  not what is supported.
- The HTML that the built-in templates render: element structure, `ha-*` class names, HTMX and
  Alpine attributes, and element ids. Theme with the design tokens, and select elements in tests
  by role, label or `data-testid`.
- The bundled JavaScript and the file names under `hyperadmin/static/`.
- Template files and blocks not listed in the table above, including everything under
  `components/` and `widgets/`.
- Log messages, the text of exceptions and warnings, and the text the command line prints.
- The exact SQL the adapters issue.
- `hyperadmin.loadtest`, the `hyperadmin seed` command and the rest of the load-test tooling.
- The first-party plugins in `plugins/` (`hyperadmin-reports`, `hyperadmin-tasks`,
  `hyperadmin-logfire`). Each has its own version number and changelog entries.

If you depend on something in this list, please
[open an issue](https://github.com/yevheniidehtiar/hyper-admin/issues) so it can be considered
for the public API.

## What a release may change

### Before 1.0

While the major version is `0`:

- A **minor** release (`0.5` to `0.6`) may contain breaking changes. Each one is listed in the
  changelog under `Changed`, `Removed` or an `Upgrade note`.
- A **patch** release (`0.5.0` to `0.5.1`) contains no intended breaking changes to the public
  API.
- **Pre-releases** of the same version (`0.5.0a1` to `0.5.0a2`) may break each other.

Pin an exact version, and read the changelog before you upgrade.

### From 1.0

| Release | May contain |
|---|---|
| **Major** (`1.x` to `2.0`) | Breaking changes to the public API, and the removal of deprecated features |
| **Minor** (`1.1` to `1.2`) | New features, new deprecations, and the changes listed below that are not breaking |
| **Patch** (`1.1.0` to `1.1.1`) | Bug fixes and security fixes only |

There are no breaking changes to the public API after 1.0 without a major version bump.

These are **not** breaking changes, and can ship in a minor release:

- Adding a class, function, optional parameter, setting, `AdminOptions` field, template block,
  `data-testid`, design token, plugin hook, or a keyword argument passed to an existing plugin
  hook. Write hook methods so they accept extra keyword arguments (`**kwargs`).
- Fixing a bug so that behaviour matches the documentation, even if code relied on the bug.
- Changing anything listed under [What is not public](#what-is-not-public).
- Raising the minimum version of a dependency, or dropping a Python version (see
  [Supported versions](#supported-python-and-dependency-versions)).
- Adding a column or a table to the built-in `hyperadmin_*` tables, with the migration step
  documented.

**Security fixes** are the one exception to the table. When closing a vulnerability requires a
breaking change, it can ship in a minor or patch release. The changelog lists it under
`Security` with an upgrade note.

## Deprecation process

A public feature is deprecated before it is removed:

1. **Warning.** Using the deprecated feature emits a `DeprecationWarning` through Python's
   `warnings` module. The message names the replacement and the release that removes the
   feature, for example: `HyperAdmin mount_mode='router' is deprecated and will be removed in
   0.6.`
2. **Changelog.** The release that introduces the deprecation lists it under a `### Deprecated`
   heading, with the replacement. The release that removes the feature lists it under
   `### Removed`.
3. **Documentation.** The feature is marked as deprecated where it is documented.
4. **Removal**, no earlier than:
    - before 1.0: the next minor release (deprecated during `0.5`, removed in `0.6` at the
      earliest);
    - from 1.0: the next major release, and only after at least one minor release has shipped
      with the warning.

A surface that cannot emit a Python warning (a template block, a `data-testid`, a design token)
is deprecated through the changelog and the documentation only, with the same removal timing.

Python hides `DeprecationWarning` by default outside of `__main__`. To see them before an
upgrade, run your test suite with warnings as errors:

```bash
python -W error::DeprecationWarning -m pytest
```

## Supported Python and dependency versions

What is supported today is listed in [Compatibility & Performance](compatibility.md). The rules
behind that table:

**Python.** The package declares `requires-python = ">=3.11,<4.0"`. CI runs the test suite on
CPython 3.11, 3.12, 3.13, 3.14 and 3.15. A new CPython release is added once HyperAdmin's
dependencies publish wheels for it. A Python version is dropped only in a minor or major
release, never in a patch release, and the changelog says so. The aim is to keep supporting a
CPython version until it reaches its upstream
[end of life](https://devguide.python.org/versions/).

**Runtime dependencies.** HyperAdmin is a library, so its runtime dependencies (FastAPI,
Pydantic, SQLAlchemy, SQLModel, Jinja2 and the rest of `[project.dependencies]`) declare a
lower bound and no upper bound. Each lower bound is the oldest version that works:

- CI runs the suite on CPython 3.11 to 3.14 twice: against the newest versions of every
  dependency, and against the declared lower bounds (`uv` resolution `lowest-direct`).
- A lower bound is raised only when the code needs a newer API, or when an older version has a
  security vulnerability. It is raised in a minor or major release, or in a patch release for a
  security fix, and the changelog names it.
- A new major version of a dependency is supported once CI passes on it. Until then HyperAdmin
  may not work with it, so pin your own dependencies.

**Optional extras.** `hyper-admin[redis]`, `[realtime]` and `[s3]` follow the same rules. The
`[dev]` and `[loadtest]` extras are for contributors and are not covered.

**Databases.** SQLite and PostgreSQL are tested. Other databases that SQLAlchemy's async engine
supports may work but are not covered until they are listed on the compatibility page.

## Security fixes

Security fixes are released for the latest version only; see the
[security policy](https://github.com/yevheniidehtiar/hyper-admin/blob/master/SECURITY.md).
