---
type: story
id: 4ET1aIsAtQUl
title: "feat(cli): add `hyperadmin plugins list` command"
status: todo
priority: medium
assignee: null
labels:
  - dx
  - size:S
  - planned
  - plugins
  - cli
estimate: null
epic_ref:
  id: um1zqB0-b2AZ
created_at: 2026-05-05T00:00:00Z
updated_at: 2026-05-05T00:00:00Z
---

## Summary

Add a `hyperadmin plugins list` Typer subcommand that introspects discovered
plugins and prints them as a table. Mirrors the existing `createsuperuser`
command pattern at `src/hyperadmin/management/commands/createsuperuser.py`.

**Spec:** [`docs/specs/plugin-registry.md`](../../../../docs/specs/plugin-registry.md)

## Files to Change

- **New:** `src/hyperadmin/management/commands/plugins.py`
- **Modified:** `src/hyperadmin/__main__.py` — register the `plugins` subapp

## Design

```python
# management/commands/plugins.py
import typer
from importlib.metadata import entry_points

app = typer.Typer(help="Manage HyperAdmin plugins")


@app.command("list")
def list_plugins() -> None:
    """List all discovered hyperadmin.plugins entry points."""
    eps = entry_points(group="hyperadmin.plugins")
    if not eps:
        typer.echo("No plugins discovered.")
        raise typer.Exit(0)

    disabled = {
        n.strip() for n in os.environ.get("HYPERADMIN_DISABLED_PLUGINS", "").split(",")
        if n.strip()
    }

    typer.echo(f"{'NAME':<24} {'CLASS':<48} STATUS")
    for ep in sorted(eps, key=lambda e: e.name):
        status = "disabled" if ep.name in disabled else "active"
        typer.echo(f"{ep.name:<24} {ep.value:<48} {status}")
```

`__main__.py` registers via `app.add_typer(plugins.app, name="plugins")`.

## Scenarios

**Scenario: hyperadmin plugins list CLI prints discovered plugins**
  Given demo_plugin is installed
  When  the user runs `hyperadmin plugins list`
  Then  stdout contains "demo" and the plugin's class path

**Scenario: hyperadmin plugins list shows disabled status**
  Given demo_plugin is installed
  And   HYPERADMIN_DISABLED_PLUGINS=demo
  When  the user runs `hyperadmin plugins list`
  Then  the row for "demo" shows "disabled"

**Scenario: hyperadmin plugins list with no plugins**
  Given no entry points exist for hyperadmin.plugins
  When  the user runs `hyperadmin plugins list`
  Then  stdout is "No plugins discovered." and exit code is 0

## Acceptance Criteria

- [ ] `hyperadmin plugins list` registered as Typer subcommand
- [ ] Output table includes name, class path, status (active/disabled)
- [ ] Sorted alphabetically by entry-point name
- [ ] No discovery errors short-circuit the listing (skip + warn)
- [ ] Unit tests using Typer's `CliRunner`

## Blocked by

- `featcore-wire-plugin-discovery-into-admin-init`

## Parent

- Epic: `epic-plugins-registry-and-lifecycle-hooks`
