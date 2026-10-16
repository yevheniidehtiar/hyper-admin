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

app = typer.Typer(help="Create HyperAdmin's database tables without starting the app.")


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
    asyncio.run(_init_db(database_url, all_tables=all_tables))
    if all_tables:
        typer.echo("Created every SQLModel table.")
    else:
        typer.echo("Created hyperadmin_* tables.")


if __name__ == "__main__":
    app()
