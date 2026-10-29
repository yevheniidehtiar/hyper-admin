"""Backend start/stop handling: lazy first-use startup and an explicit ASGI-lifespan helper."""

from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

    from hyperadmin_tasks.backend import TaskBackend


class BackendLifecycle:
    """Owns a backend's ``startup()`` / ``shutdown()`` so each runs at most once per cycle.

    Core has no async plugin startup seam, so routes call :meth:`ensure_started` on first use
    and hosts that want eager start-up and clean shutdown compose :func:`lifespan`.
    """

    def __init__(self, backend: TaskBackend) -> None:
        self.backend = backend
        self._started = False
        self._lock = asyncio.Lock()

    @property
    def started(self) -> bool:
        """Whether ``startup()`` has completed and ``shutdown()`` has not run since."""
        return self._started

    async def ensure_started(self) -> TaskBackend:
        """Await ``backend.startup()`` once (double-checked) and return the backend."""
        if not self._started:
            async with self._lock:
                if not self._started:
                    await self.backend.startup()
                    self._started = True
        return self.backend

    async def shutdown(self) -> None:
        """Await ``backend.shutdown()`` if the backend was started; otherwise do nothing."""
        async with self._lock:
            if self._started:
                self._started = False
                await self.backend.shutdown()


@asynccontextmanager
async def lifespan(admin: Any) -> AsyncIterator[None]:
    """Start the tasks backend eagerly and shut it down on exit.

    Compose it in the host app's lifespan: ``async with hyperadmin_tasks.lifespan(admin): ...``.
    """
    lifecycle: BackendLifecycle = admin.plugins["tasks"].lifecycle
    await lifecycle.ensure_started()
    try:
        yield
    finally:
        await lifecycle.shutdown()
