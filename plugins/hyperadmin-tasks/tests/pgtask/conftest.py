"""Fixtures that provide a real Postgres 16+ with a migrated pgtask schema.

A server comes from ``HYPERADMIN_TASKS_TEST_DSN`` (a superuser DSN) or, when ``testcontainers``
and a Docker daemon are available, from a throw-away ``postgres:16`` container. Without either
every test in this directory is skipped with ``Postgres 16+ unavailable`` so CI stays green.
Run only these tests with ``pytest -m pgtask``.
"""

from __future__ import annotations

import asyncio
import contextlib
import os
import uuid
from collections.abc import Iterator
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING, Any
from urllib.parse import quote

import psycopg
import pytest
from psycopg import sql
from psycopg.conninfo import conninfo_to_dict

from hyperadmin_tasks.backend import (
    AttemptRecord,
    ScheduleRecord,
    TaskRecord,
    TaskState,
    WorkerRecord,
)
from hyperadmin_tasks.contract import ContractSeed

if TYPE_CHECKING:
    from pgtask import Task

DSN_ENV = "HYPERADMIN_TASKS_TEST_DSN"
MIN_SERVER_VERSION = 160000
SKIP_REASON = "Postgres 16+ unavailable"
SCHEDULE_CRON = "0 3 * * *"
SCHEDULE_NAME = "nightly-report"


@dataclass(frozen=True)
class PgRoles:
    """Names of the pgtask roles created for one test run (roles are cluster-global)."""

    owner: str
    producer: str
    worker: str
    observer: str
    administrator: str
    password: str

    def all(self) -> tuple[str, ...]:
        """Return every role name."""
        return (self.owner, self.producer, self.worker, self.observer, self.administrator)


@dataclass(frozen=True)
class PgDatabase:
    """A migrated pgtask database with one DSN per role."""

    name: str
    owner_dsn: str
    observer_dsn: str
    administrator_dsn: str


def url_for(dsn: str, *, dbname: str | None = None, user: str | None = None, **kw: str) -> str:
    """Return ``dsn`` (URL or key/value form) as a URL with the given parts replaced."""
    parts = conninfo_to_dict(dsn)
    if dbname is not None:
        parts["dbname"] = dbname
    if user is not None:
        parts["user"] = user
    if "password" in kw:
        parts["password"] = kw["password"]
    auth = quote(str(parts.get("user", "postgres")), safe="")
    if parts.get("password"):
        auth += ":" + quote(str(parts["password"]), safe="")
    host = parts.get("host", "localhost")
    port = parts.get("port", "5432")
    return f"postgresql://{auth}@{host}:{port}/{parts.get('dbname', 'postgres')}"


def server_is_usable(dsn: str) -> bool:
    """Return whether ``dsn`` reaches a Postgres 16+ server."""
    try:
        with psycopg.connect(dsn, connect_timeout=5) as conn:
            return conn.info.server_version >= MIN_SERVER_VERSION
    except psycopg.Error:
        return False


def create_roles(server_dsn: str) -> PgRoles:
    """Create the five pgtask roles (unique per run) and return their names."""
    suffix = uuid.uuid4().hex[:8]
    roles = PgRoles(
        owner=f"hatasks_owner_{suffix}",
        producer=f"hatasks_producer_{suffix}",
        worker=f"hatasks_worker_{suffix}",
        observer=f"hatasks_observer_{suffix}",
        administrator=f"hatasks_administrator_{suffix}",
        password=uuid.uuid4().hex,
    )
    with psycopg.connect(server_dsn, autocommit=True) as conn:
        for name in roles.all():
            conn.execute(
                sql.SQL("CREATE ROLE {} LOGIN PASSWORD {}").format(
                    sql.Identifier(name), sql.Literal(roles.password)
                )
            )
    return roles


def drop_roles(server_dsn: str, roles: PgRoles) -> None:
    """Drop the roles created by :func:`create_roles` (databases must be gone already)."""
    with psycopg.connect(server_dsn, autocommit=True) as conn:
        for name in roles.all():
            conn.execute(sql.SQL("DROP ROLE IF EXISTS {}").format(sql.Identifier(name)))


def create_database(server_dsn: str, roles: PgRoles) -> PgDatabase:
    """Create a database, migrate pgtask into it and grant the roles."""
    name = f"hatasks_{uuid.uuid4().hex[:12]}"
    with psycopg.connect(server_dsn, autocommit=True) as conn:
        conn.execute(sql.SQL("CREATE DATABASE {} TEMPLATE template0").format(sql.Identifier(name)))
    server_url = url_for(server_dsn, dbname=name)
    asyncio.run(_migrate_database(server_url))
    with psycopg.connect(url_for(server_dsn, dbname=name), autocommit=True) as conn:
        conn.execute(
            "SELECT pgtask.configure_grants(%s::regrole, %s::regrole, %s::regrole, "
            "%s::regrole, %s::regrole)",
            (roles.owner, roles.producer, roles.worker, roles.observer, roles.administrator),
        )
    return PgDatabase(
        name=name,
        owner_dsn=server_url,
        observer_dsn=url_for(server_dsn, dbname=name, user=roles.observer, password=roles.password),
        administrator_dsn=url_for(
            server_dsn, dbname=name, user=roles.administrator, password=roles.password
        ),
    )


async def _migrate_database(url: str) -> None:
    from pgtask import Client

    client = await Client.connect(url)
    await client.migrate()


def drop_database(server_dsn: str, database: PgDatabase) -> None:
    """Drop ``database``, disconnecting any leftover sessions."""
    with psycopg.connect(server_dsn, autocommit=True) as conn:
        conn.execute(
            sql.SQL("DROP DATABASE IF EXISTS {} WITH (FORCE)").format(sql.Identifier(database.name))
        )


def _record(
    task_id: str,
    queue: str,
    name: str,
    state: TaskState,
    now: datetime,
    *,
    attempt: int = 0,
    error: str | None = None,
) -> TaskRecord:
    return TaskRecord(
        id=task_id,
        queue=queue,
        name=name,
        state=state,
        priority=0,
        attempt=attempt,
        max_attempts=3,
        created_at=now,
        error=error,
    )


async def seed_contract_data(owner_url: str) -> ContractSeed:
    """Seed the canonical contract data with real pgtask calls and return the matching seed.

    One failed task (3 attempts) and one succeeded task are produced by a real ``Worker``; the
    running task is claimed by a registered worker row that never completes it; the pending and
    scheduled tasks are plain enqueues; one cron schedule is stored with ``put_schedule``.
    """
    from pgtask import Client, EnqueueRequest, TaskRegistry, Worker

    now = datetime.now(UTC)
    client = await Client.connect(owner_url)
    default = TaskRegistry("default")
    mail = TaskRegistry("mail")

    @default.task("app.send", retry_delay=0.05)
    async def _send(task: Task, payload: dict[str, object]) -> None:
        raise RuntimeError("boom")

    @mail.task("app.mail", retry_delay=0.05)
    async def _mail(task: Task, payload: dict[str, object]) -> str:
        return "sent"

    failed = await client.enqueue(
        EnqueueRequest("app.send", {"n": 6}, queue_name="default", max_attempts=3)
    )
    succeeded = await client.enqueue(EnqueueRequest("app.mail", {"n": 8}, queue_name="mail"))
    scheduled = await client.enqueue(
        EnqueueRequest("app.mail", {"n": 9}, queue_name="mail", run_at=now + timedelta(days=1))
    )
    running = await client.enqueue(EnqueueRequest("app.report", {"n": 7}, queue_name="default"))

    worker = Worker(owner_url, [default, mail], poll_interval=0.1, retention_enabled=False)
    runner = asyncio.create_task(worker.run())
    try:
        await asyncio.gather(failed.result(timeout=30), succeeded.result(timeout=30))
    finally:
        worker.shutdown()
        with contextlib.suppress(Exception):
            await runner

    pending = [
        await client.enqueue(
            EnqueueRequest("app.send", {"n": n}, queue_name="default", max_attempts=3)
        )
        for n in range(1, 6)
    ]
    worker_id = await _claim_and_hold(owner_url, "default", "app.report")
    schedule_id = await _put_schedule(owner_url)

    tasks = [_record(h.id, "default", "app.send", TaskState.PENDING, now) for h in pending]
    tasks.append(
        _record(failed.id, "default", "app.send", TaskState.FAILED, now, attempt=3, error="boom")
    )
    tasks.append(_record(running.id, "default", "app.report", TaskState.RUNNING, now, attempt=1))
    tasks.append(_record(succeeded.id, "mail", "app.mail", TaskState.SUCCEEDED, now, attempt=1))
    tasks.append(_record(scheduled.id, "mail", "app.mail", TaskState.SCHEDULED, now))
    attempts = {
        failed.id: [
            AttemptRecord(number=n, started_at=now, outcome="failed", error="boom")
            for n in (1, 2, 3)
        ]
    }
    schedules = [
        ScheduleRecord(
            id=schedule_id,
            task_name="app.report",
            queue="default",
            cron=SCHEDULE_CRON,
            misfire_policy="skip",
        )
    ]
    workers = [
        WorkerRecord(
            id=worker_id,
            queues=("default",),
            task_names=("app.report",),
            last_seen_at=now,
            concurrency=0,
            healthy=True,
        )
    ]
    return ContractSeed(tasks=tasks, attempts=attempts, workers=workers, schedules=schedules)


async def _claim_and_hold(owner_url: str, queue: str, task_name: str) -> str:
    """Register a worker row and claim ``task_name`` for an hour without completing it."""
    worker_id = uuid.uuid4()
    async with await psycopg.AsyncConnection.connect(owner_url, autocommit=True) as conn:
        await conn.execute(
            "SELECT pgtask.register_worker(%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)",
            (
                worker_id,
                queue,
                "contract",
                [task_name],
                [1],
                ["exponential"],
                [1000],
                [2],
                [60000],
                3_600_000,
            ),
        )
        await conn.execute(
            "SELECT * FROM pgtask.claim(%s, %s, %s, %s, 1, 3600000)",
            (queue, worker_id, [task_name], [1]),
        )
    return str(worker_id)


async def _put_schedule(owner_url: str) -> str:
    schedule_id = uuid.uuid4()
    async with await psycopg.AsyncConnection.connect(owner_url, autocommit=True) as conn:
        await conn.execute(
            "SELECT pgtask.put_schedule(%s, %s, 'cron', NULL, %s, 'skip', NULL, 'default', "
            "'app.report', 1, '{}'::jsonb, '{}'::jsonb, 0::smallint, 3, "
            "now() + interval '15 hours')",
            (schedule_id, SCHEDULE_NAME, SCHEDULE_CRON),
        )
    return str(schedule_id)


def pytest_configure(config: pytest.Config) -> None:
    """Register the ``pgtask`` marker."""
    config.addinivalue_line("markers", "pgtask: needs a real Postgres 16+ with the pgtask schema")


def pytest_collection_modifyitems(items: list[pytest.Item]) -> None:
    """Mark every test collected under this directory with ``pgtask``."""
    here = os.path.dirname(__file__) + os.sep
    for item in items:
        if str(item.path).startswith(here):
            item.add_marker(pytest.mark.pgtask)


@pytest.fixture(scope="session")
def pg_server_dsn() -> Iterator[str]:
    """Yield a superuser DSN of a Postgres 16+ server or skip the requesting test."""
    dsn = os.environ.get(DSN_ENV)
    if dsn:
        if not server_is_usable(dsn):
            pytest.skip(SKIP_REASON)
        yield dsn
        return
    try:
        from testcontainers.postgres import PostgresContainer
    except ImportError:
        pytest.skip(SKIP_REASON)
    container: Any = PostgresContainer("postgres:16", driver=None)
    try:
        container.start()
    except Exception:
        pytest.skip(SKIP_REASON)
    try:
        yield container.get_connection_url()
    finally:
        with contextlib.suppress(Exception):
            container.stop()


@pytest.fixture(scope="session")
def pg_roles(pg_server_dsn: str) -> Iterator[Any]:
    """Create the pgtask roles once per run and drop them afterwards."""
    pytest.importorskip("pgtask")
    roles = create_roles(pg_server_dsn)
    yield roles
    drop_roles(pg_server_dsn, roles)


@pytest.fixture
def pgtask_database(pg_server_dsn: str, pg_roles: Any) -> Iterator[Any]:
    """Yield a fresh migrated database with observer / administrator roles granted."""
    database = create_database(pg_server_dsn, pg_roles)
    yield database
    drop_database(pg_server_dsn, database)


@pytest.fixture(scope="session")
def seeded_pgtask(pg_server_dsn: str, pg_roles: Any) -> Iterator[tuple[Any, Any]]:
    """Yield ``(database, seed)``: a database holding the canonical contract data.

    Shared by read-only tests; tests that mutate data use ``pgtask_database`` instead.
    """
    database = create_database(pg_server_dsn, pg_roles)
    seed = asyncio.run(seed_contract_data(database.owner_dsn))
    yield database, seed
    drop_database(pg_server_dsn, database)
