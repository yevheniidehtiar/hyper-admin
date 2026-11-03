"""Host integration: an optional in-process pgtask worker bound to the admin lifespan.

The worker itself is built by the pgtask adapter (``backends/pgtask.py``, the only module that
imports pgtask); this module only resolves the settings and drives ``run()`` / ``shutdown()``.
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
    try:
        module = import_module(PGTASK_MODULE)
    except ImportError as exc:
        raise TasksBackendError(
            f"the in-process worker needs pgtask; install hyperadmin-tasks[pgtask] ({exc})"
        ) from exc
    worker: Worker = getattr(module, WORKER_FACTORY)(dsn, found, settings)
    return worker


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
    runner = asyncio.create_task(worker.run(), name="hyperadmin-tasks-worker")
    runner.add_done_callback(_log_crash)
    try:
        yield
    finally:
        worker.shutdown()
        await asyncio.gather(runner, return_exceptions=True)


def _log_crash(runner: asyncio.Task[None]) -> None:
    if not runner.cancelled() and (exc := runner.exception()) is not None:
        logger.error("in-process pgtask worker stopped", exc_info=exc)
