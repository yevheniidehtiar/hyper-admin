"""Startup probe of PgTaskBackend on a real Postgres + pgtask (skipped without a server)."""

from __future__ import annotations

from typing import Any

import psycopg
import pytest
from psycopg.conninfo import make_conninfo

from hyperadmin_tasks.backend import TasksBackendError

pytest.importorskip("pgtask")

pytestmark = [pytest.mark.anyio, pytest.mark.pgtask]


async def test_startup_probe_passes_on_a_migrated_database(pgtask_database: Any) -> None:
    """
    Scenario: a migrated database starts
      Given a Postgres 16 database migrated by the installed pgtask
      When  PgTaskBackend.startup() runs on the observer DSN
      Then  the probe passes and queries work
    """
    from hyperadmin_tasks.backends.pgtask import PgTaskBackend

    backend = PgTaskBackend(pgtask_database.observer_dsn)
    await backend.startup()
    try:
        assert await backend.list_queues() == []
    finally:
        await backend.shutdown()


async def test_startup_probe_asks_to_migrate_an_empty_database(
    pg_server_dsn: str, pgtask_database: Any
) -> None:
    """
    Scenario: schema not migrated
      Given a database without the pgtask schema
      When  PgTaskBackend.startup() runs
      Then  TasksBackendError tells the user to run `pgtask migrate`
    """
    import uuid

    from psycopg import sql

    from hyperadmin_tasks.backends.pgtask import PgTaskBackend

    name = f"hatasks_empty_{uuid.uuid4().hex[:8]}"
    with psycopg.connect(pg_server_dsn, autocommit=True) as conn:
        conn.execute(sql.SQL("CREATE DATABASE {} TEMPLATE template0").format(sql.Identifier(name)))
    try:
        dsn = make_conninfo(pgtask_database.observer_dsn, dbname=name)
        with pytest.raises(TasksBackendError, match="pgtask migrate"):
            await PgTaskBackend(dsn).startup()
    finally:
        with psycopg.connect(pg_server_dsn, autocommit=True) as conn:
            conn.execute(
                sql.SQL("DROP DATABASE IF EXISTS {} WITH (FORCE)").format(sql.Identifier(name))
            )
