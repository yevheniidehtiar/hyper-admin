import os
from importlib.metadata import entry_points

import typer

from hyperadmin.core.plugins import (
    DISABLED_PLUGINS_ENV,
    PLUGIN_ENTRY_POINT_GROUP,
    parse_disabled_env,
)

app = typer.Typer(
    help="Manage HyperAdmin plugins.",
    pretty_exceptions_show_locals=False,
)


@app.command("list")
def list_plugins() -> None:
    """List all discovered hyperadmin.plugins entry points."""
    eps = entry_points(group=PLUGIN_ENTRY_POINT_GROUP)
    if not eps:
        typer.echo("No plugins discovered.")
        raise typer.Exit(0)

    disabled = parse_disabled_env(os.environ.get(DISABLED_PLUGINS_ENV))

    typer.echo(f"{'NAME':<24} {'CLASS':<48} STATUS")
    for ep in sorted(eps, key=lambda e: (e.name, e.value)):
        status = "disabled" if ep.name in disabled else "active"
        typer.echo(f"{ep.name:<24} {ep.value:<48} {status}")
