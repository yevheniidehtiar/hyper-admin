"""Background tasks in HyperAdmin with the ``hyperadmin-tasks`` plugin and pgtask on Postgres.

Run it (see README.md)::

    docker compose -f examples/tasks/docker-compose.yml up    # http://127.0.0.1:8000/admin

On startup the app creates its table, migrates the pgtask schema, stores the ``reports-digest``
cron schedule, seeds three reports, and runs a pgtask worker inside the web process.
"""

from __future__ import annotations

from contextlib import asynccontextmanager
from typing import TYPE_CHECKING

import psycopg
from fastapi import FastAPI
from pgtask import Client
from sqlalchemy import func, select

import hyperadmin_tasks
from examples.tasks import admin as _admin  # noqa: F401  (registers the models)
from examples.tasks.db import DATABASE_URL, Session, engine
from examples.tasks.models import Base, Report
from examples.tasks.tasks import put_digest_schedule, registry
from hyperadmin import Admin
from hyperadmin.core.settings import HyperAdminSettings

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

SEED_TITLES = ("Weekly sales", "Monthly churn", "Quarterly revenue")

#: One database role for everything keeps the example short. In production give the dashboard,
#: the worker and the app their own pgtask roles (see the plugin docs on role setup).
TASKS_SETTINGS = {
    "backend": "pgtask",
    "dsn": DATABASE_URL,
    "run_worker": True,
    "worker_shutdown_grace": 5.0,
}


async def prepare_database() -> None:
    """Create the report table, migrate pgtask, store the cron schedule and seed reports."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    client = await Client.connect(DATABASE_URL)
    await client.migrate()
    async with await psycopg.AsyncConnection.connect(DATABASE_URL, autocommit=True) as conn:
        await put_digest_schedule(conn)
    async with Session.begin() as session:
        if not await session.scalar(select(func.count()).select_from(Report)):
            session.add_all(Report(title=title) for title in SEED_TITLES)


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
    await prepare_database()
    async with admin.lifespan(), hyperadmin_tasks.lifespan(admin, registries=[registry]):
        yield
    await engine.dispose()


app = FastAPI(lifespan=lifespan)

admin = Admin(
    app,
    engine=engine,
    settings=HyperAdminSettings(create_tables=False, auto_discover=False),
    plugin_settings={"tasks": TASKS_SETTINGS},
)
admin.mount(path="/admin")


@app.get("/")
def root() -> dict[str, str]:
    return {"message": "Go to /admin/report to queue a task, then /admin/tasks to watch it."}
