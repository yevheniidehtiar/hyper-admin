"""``hyperadmin seed`` — bulk synthetic-data generator CLI.

Drives :class:`hyperadmin.loadtest.BulkSeeder` from a single ``--count`` target, scaling the
chosen plan's per-table ratios. See ``docs/specs/synthetic-data-generator.md`` for the design.
"""

from __future__ import annotations

from pathlib import Path
from typing import Annotated

import typer
from sqlalchemy import create_engine

from hyperadmin.loadtest.batch import BulkSeeder, SeedInterruptedError
from hyperadmin.loadtest.checkpoint import PlanHashMismatchError
from hyperadmin.loadtest.generators import PLAN_BUILDERS, build_plan
from hyperadmin.loadtest.progress import make_reporter

app = typer.Typer(help="Bulk synthetic-data seeding for load testing.")

# Async drivers cannot back the synchronous Core inserts the seeder uses; map them to their
# sync equivalents so a single --database-url works whether it came from app config or env.
_ASYNC_TO_SYNC = {
    "sqlite+aiosqlite": "sqlite",
    "postgresql+asyncpg": "postgresql+psycopg2",
    "postgresql+psycopg_async": "postgresql+psycopg",
    "mysql+aiomysql": "mysql+pymysql",
}


def _to_sync_url(url: str) -> str:
    for async_prefix, sync_prefix in _ASYNC_TO_SYNC.items():
        if url.startswith(async_prefix):
            return sync_prefix + url[len(async_prefix) :]
    return url


@app.command()
def seed(  # noqa: PLR0913 - each option is a distinct CLI flag
    count: Annotated[int, typer.Option("--count", help="Total target rows across the plan.")],
    database_url: Annotated[
        str | None,
        typer.Option("--database-url", envvar="DATABASE_URL", help="SQLAlchemy database URL."),
    ] = None,
    batch_size: Annotated[int, typer.Option("--batch-size", help="Rows per INSERT batch.")] = 5000,
    plan_name: Annotated[
        str, typer.Option("--plan", help=f"Plan name. One of: {', '.join(PLAN_BUILDERS)}.")
    ] = "erp",
    resume: Annotated[
        bool, typer.Option("--resume", help="Resume from the checkpoint file.")
    ] = False,
    rng_seed: Annotated[int, typer.Option("--seed", help="RNG seed for reproducible runs.")] = 42,
    state_file: Annotated[
        Path, typer.Option("--state-file", help="Checkpoint file location.")
    ] = Path(".hyperadmin-seed.json"),
    no_progress: Annotated[
        bool, typer.Option("--no-progress", help="Disable the Rich progress UI.")
    ] = False,
) -> None:
    """Seed COUNT rows into the database using the chosen plan."""
    if count < 0:
        typer.echo("Error: --count must be >= 0.", err=True)
        raise typer.Exit(code=1)
    if not database_url:
        typer.echo(
            "Error: provide a database via --database-url or the DATABASE_URL env var.",
            err=True,
        )
        raise typer.Exit(code=1)

    try:
        plan = build_plan(plan_name, seed=rng_seed).scaled(count)
    except KeyError as exc:
        typer.echo(f"Error: {exc.args[0]}", err=True)
        raise typer.Exit(code=1) from None

    engine = create_engine(_to_sync_url(database_url))
    reporter = make_reporter(no_progress=no_progress)
    seeder = BulkSeeder(
        plan=plan,
        engine=engine,
        batch_size=batch_size,
        rng_seed=rng_seed,
        state_file=state_file,
        resume=resume,
        progress=reporter,
    )

    try:
        summary = seeder.run()
    except PlanHashMismatchError as exc:
        typer.echo(f"Error: {exc}", err=True)
        raise typer.Exit(code=2) from None
    except SeedInterruptedError as exc:
        typer.echo(f"\nInterrupted: {exc}", err=True)
        raise typer.Exit(code=130) from None
    finally:
        engine.dispose()

    typer.echo(
        f"Seeded {summary.rows_inserted} rows in {summary.elapsed_seconds:.1f}s "
        f"({summary.rows_per_second:.0f} rows/s)."
    )


if __name__ == "__main__":
    app()
