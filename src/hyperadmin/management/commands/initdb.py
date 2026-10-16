"""``hyperadmin init-db`` — create database tables without starting the app.

Defaults to creating only the built-in ``hyperadmin_*`` tables, so running this
against a host's own database never touches tables the host migrates itself
(Alembic, etc) — the same "never alter a host database behind its migrations'
back" goal that drove ``create_tables`` defaulting to ``False`` (SDD
``bring-your-own-app.md`` C.2). Pass ``--all`` to create every table registered
on ``SQLModel.metadata`` instead (the host's own models too), for a host with
no migration tooling of its own yet.
"""

from __future__ import annotations

import asyncio
from typing import Annotated

import typer
from sqlalchemy.ext.asyncio import create_async_engine

import hyperadmin.auth as auth_module
from hyperadmin.db import create_tables

app = typer.Typer(
    help="Create HyperAdmin's database tables without starting the app.",
    # The database URL (with its password) lives in every frame between here and
    # the driver's connect() call. Typer/Rich's pretty tracebacks print frame
    # locals when this is True — the default on every Typer release before
    # 0.17 — so a connection failure would otherwise dump the password to the
    # terminal / CI log. Keep this explicit rather than relying on the
    # installed Typer's own default.
    pretty_exceptions_show_locals=False,
)


async def _init_db(database_url: str, *, all_tables: bool) -> None:
    tables = None if all_tables else list(auth_module.metadata().tables.values())

    engine = create_async_engine(database_url)
    try:
        await create_tables(engine, tables=tables)
    finally:
        await engine.dispose()


@app.command("init-db")
def init_db(
    database_url: Annotated[
        str,
        typer.Option(
            "--database-url",
            envvar="HYPERADMIN_DATABASE_URL",
            help="Async SQLAlchemy database URL (e.g. sqlite+aiosqlite:///./app.db).",
        ),
    ],
    all_tables: Annotated[
        bool,
        typer.Option(
            "--all",
            help="Create every SQLModel table, not just hyperadmin_* ones.",
        ),
    ] = False,
) -> None:
    """Create database tables for ``--database-url`` (``hyperadmin_*`` only by default)."""
    try:
        asyncio.run(_init_db(database_url, all_tables=all_tables))
    except Exception as exc:
        # Never let a connection/DDL failure fall through to Typer's traceback
        # renderer: str(exc) is driver-level ("Connect call failed ...") and
        # does not include the URL, unlike the frames pretty_exceptions_show_locals
        # would have printed.
        typer.echo(f"init-db failed: {exc}", err=True)
        raise typer.Exit(1) from exc
    if all_tables:
        typer.echo("Created every SQLModel table.")
    else:
        typer.echo("Created hyperadmin_* tables.")
