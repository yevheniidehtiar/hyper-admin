"""Host integration: an in-process pgtask worker and transactional enqueue from a session.

pgtask itself is only touched by the pgtask adapter (``backends/pgtask.py``, the only module that
imports pgtask); this module resolves settings, drives the worker's ``run()`` / ``shutdown()`` and
finds the psycopg connection behind a SQLAlchemy session.
"""

from __future__ import annotations

import asyncio
import logging
from contextlib import asynccontextmanager
from importlib import import_module
from typing import TYPE_CHECKING, Any, Protocol

from hyperadmin_tasks.backend import TasksBackendError
from hyperadmin_tasks.selection import PGTASK_MODULE

if TYPE_CHECKING:
    from collections.abc import AsyncIterator, Iterable

    from sqlalchemy.ext.asyncio import AsyncSession

    from hyperadmin_tasks.settings import TasksSettings

logger = logging.getLogger(__name__)

#: Name of the worker factory the pgtask module exposes.
WORKER_FACTORY = "create_worker"
_NO_REGISTRIES = (
    "run_worker=True needs task registries: pass hyperadmin_tasks.lifespan(admin, "
    "registries=[...]) or set HYPERADMIN_TASKS_REGISTRIES='module:attr'"
)


class Worker(Protocol):
    """What the lifespan needs from a worker: pgtask's ``Worker`` satisfies it."""

    async def run(self) -> None: ...

    def shutdown(self) -> None: ...


def resolve_registries(settings: TasksSettings, registries: Iterable[Any] | None) -> list[Any]:
    """Return ``registries`` if given, else the ones ``settings.registries`` names."""
    if registries is not None:
        found = list(registries)
    elif settings.registries:
        found = _load_registries(settings.registries)
    else:
        found = []
    if not found:
        raise TasksBackendError(_NO_REGISTRIES)
    return found


def _load_registries(path: str) -> list[Any]:
    module_name, sep, attr = path.partition(":")
    if not sep:
        raise TasksBackendError(f"task registries '{path}': use 'module:attr'")
    try:
        value = getattr(import_module(module_name), attr)
    except (ImportError, AttributeError) as exc:
        raise TasksBackendError(f"cannot load task registries '{path}': {exc}") from exc
    return list(value) if isinstance(value, list | tuple) else [value]


def build_worker(settings: TasksSettings, registries: Iterable[Any] | None) -> Worker:
    """Build the pgtask worker for ``settings`` or raise ``TasksBackendError``."""
    dsn = settings.worker_dsn or settings.dsn
    if dsn is None:
        raise TasksBackendError(
            "run_worker=True needs a database: set HYPERADMIN_TASKS_WORKER_DSN "
            "(worker role) or HYPERADMIN_TASKS_DSN"
        )
    found = resolve_registries(settings, registries)
    worker: Worker = getattr(_pgtask_adapter("the in-process worker"), WORKER_FACTORY)(
        dsn, found, settings
    )
    return worker


async def enqueue_in_session(session: AsyncSession, request: Any) -> str:
    """Enqueue a pgtask ``EnqueueRequest`` in ``session``'s current transaction.

    The task is written on the session's own connection, so it commits or rolls back together
    with the business rows (no outbox). Returns the task id. The session's engine must use the
    psycopg driver (``postgresql+psycopg://``); anything else raises ``TasksBackendError``.
    """
    connection = await session.connection()
    dialect = connection.dialect
    if dialect.driver != "psycopg":
        raise TasksBackendError(
            "enqueue_in_session() needs the psycopg driver (postgresql+psycopg://); "
            f"the session uses {dialect.name}+{dialect.driver}"
        )
    raw = await connection.get_raw_connection()
    adapter = _pgtask_adapter("enqueue_in_session()")
    task_id: str = await adapter.enqueue_on(raw.driver_connection, request)
    return task_id


def _pgtask_adapter(feature: str) -> Any:
    try:
        return import_module(PGTASK_MODULE)
    except ImportError as exc:
        raise TasksBackendError(
            f"{feature} needs pgtask; install hyperadmin-tasks[pgtask] ({exc})"
        ) from exc


@asynccontextmanager
async def run_worker_in_lifespan(
    settings: TasksSettings, registries: Iterable[Any] | None = None
) -> AsyncIterator[None]:
    """Run a pgtask worker in the background while the block runs, if ``run_worker`` is set.

    On exit the worker is asked to stop and awaited: running handlers get
    ``worker_shutdown_grace`` seconds, then pgtask cancels them and returns their tasks to
    ``pending``. A worker that crashes is logged and does not stop the app.
    """
    if not settings.run_worker:
        yield
        return
    worker = build_worker(settings, registries)
    runner = asyncio.create_task(_run(worker), name="hyperadmin-tasks-worker")
    try:
        yield
    finally:
        worker.shutdown()
        await runner


async def _run(worker: Worker) -> None:
    try:
        await worker.run()
    except Exception:
        logger.exception("in-process pgtask worker stopped")
