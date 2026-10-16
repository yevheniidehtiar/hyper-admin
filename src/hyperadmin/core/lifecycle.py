"""Pure lifecycle orchestration for ``Admin`` (SDD ``bring-your-own-app.md`` C.2).

``Lifecycle`` owns exactly one thing: making sure the "create tables, then
sync permissions" startup sequence runs **once**, however it is reached —
either explicitly (the host composes :meth:`Lifecycle.lifespan` or calls
:meth:`Lifecycle.startup` itself) or through the first-request safety net
(:class:`StartupGuardMiddleware`). It never imports SQLAlchemy, an ORM model,
or anything from ``hyperadmin.auth`` — every ORM-specific operation (table
DDL, bind resolution, the hyperadmin-only table lookup) is injected as a
plain async callable from ``core/app.py``, which is the one place in
``core/`` allowed to reach into ``db.py`` and ``auth/`` (CONSTITUTION
section 1; SDD C.2 review amendments).
"""

from __future__ import annotations

import asyncio
import logging
from contextlib import asynccontextmanager
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from collections.abc import AsyncIterator, Awaitable, Callable

logger = logging.getLogger("hyperadmin")

_GUARD_REALTIME_WARNING = (
    "HyperAdmin started via the first-request safety net, not an explicit "
    "lifespan. Realtime is enabled but shutdown() has no safety net, so SSE/"
    "WebSocket connections will not be drained on a graceful shutdown. "
    "Compose admin.lifespan() into your host app's own lifespan to fix this."
)


class Lifecycle:
    """Owns HyperAdmin's startup/shutdown state.

    ``startup()`` is idempotent: once it has completed successfully, every
    further call (from either the explicit path or the safety net) is a
    no-op. Concurrent callers race for an ``asyncio.Lock`` so the work runs
    exactly once even when several requests arrive before the first one
    finishes. A failure during startup is **not** cached — ``_started``
    stays ``False`` so the next call retries — and, when it was reached
    through the safety net, the failure is logged (the caller still sees the
    exception; only the cheap re-run guarantee is "free" here).
    """

    def __init__(
        self,
        *,
        create_tables: Callable[[], Awaitable[None]],
        sync_permissions: Callable[[], Awaitable[None]],
        drain: Callable[[], Awaitable[None]],
        realtime_enabled: bool,
    ) -> None:
        """Build a ``Lifecycle``.

        Args:
            create_tables: Awaitable callable that creates tables if (and
                only if) the host opted in — the decision itself is made by
                the caller (``core/app.py``), not here.
            sync_permissions: Awaitable callable that syncs registered
                models' permissions. A no-op when no permission registry is
                configured is the caller's responsibility too.
            drain: Awaitable callable that drains realtime (SSE/WebSocket)
                connections. A no-op when realtime is disabled.
            realtime_enabled: Whether realtime is configured — used only to
                decide whether the safety-net warning applies.
        """
        self._create_tables = create_tables
        self._sync_permissions = sync_permissions
        self._drain = drain
        self._realtime_enabled = realtime_enabled
        self._started = False
        self._lock = asyncio.Lock()

    @property
    def started(self) -> bool:
        """Whether ``startup()`` has completed successfully at least once."""
        return self._started

    async def _run_startup(self, *, via_guard: bool) -> None:
        # The outer check reads through the ``started`` property rather than the
        # ``_started`` attribute directly: a type checker narrows a plain attribute
        # read to ``False`` across the two identical checks (it doesn't model another
        # task flipping it to ``True`` while this one awaits the lock), which makes the
        # second check look unreachable even though it is the whole point of the
        # double-checked-lock pattern — the fast path for every call after the first.
        if self.started:
            return
        async with self._lock:
            if self._started:
                return
            try:
                await self._create_tables()
                await self._sync_permissions()
            except Exception:
                if via_guard:
                    logger.exception(
                        "HyperAdmin startup failed; the next admin request will retry."
                    )
                raise
            self._started = True
            if via_guard and self._realtime_enabled:
                logger.warning(_GUARD_REALTIME_WARNING)

    async def startup(self) -> None:
        """Create tables (if opted in), then sync permissions. Idempotent.

        This is the explicit path: call it directly, or compose
        :meth:`lifespan` into the host's own ``lifespan=``.
        """
        await self._run_startup(via_guard=False)

    async def ensure_started(self) -> None:
        """Run :meth:`startup` exactly once — the first-request safety net.

        Used by :class:`StartupGuardMiddleware`. Starlette silently ignores
        ``on_event``/``on_startup`` handlers once a host passes its own
        ``lifespan=``, and a mounted sub-application never receives lifespan
        events at all, so this is the only mechanism guaranteed to run when
        the host has not explicitly composed :meth:`lifespan`.
        """
        await self._run_startup(via_guard=True)

    async def shutdown(self) -> None:
        """Drain realtime connections.

        Unlike :meth:`startup`, shutdown has **no** safety net: it only runs
        when the host composes :meth:`lifespan` (or calls this directly).
        Open SSE/WebSocket connections still exit gracefully regardless,
        because their generators poll ``request.is_disconnected()``.
        """
        await self._drain()

    @asynccontextmanager
    async def lifespan(self) -> AsyncIterator[None]:
        """Async context manager a host composes into its own ``lifespan=``."""
        await self.startup()
        try:
            yield
        finally:
            await self.shutdown()


class StartupGuardMiddleware:
    """Pure-ASGI safety net: calls ``lifecycle.ensure_started()`` once.

    Only requests whose path starts with ``admin_prefix`` trigger the check;
    every other host route passes straight through untouched. This is
    intentionally plain ASGI rather than ``BaseHTTPMiddleware`` — it never
    buffers or wraps the response, so streaming SSE/WebSocket connections are
    unaffected.

    Once ``lifecycle.started`` is ``True`` the check is a single attribute
    read, so the steady-state cost of this middleware is negligible.
    """

    def __init__(self, app: Any, *, lifecycle: Lifecycle, admin_prefix: str) -> None:
        self.app = app
        self._lifecycle = lifecycle
        self._admin_prefix = admin_prefix.rstrip("/") or "/"

    async def __call__(self, scope: Any, receive: Any, send: Any) -> None:
        if (
            scope["type"] == "http"
            and not self._lifecycle.started
            and scope.get("path", "").startswith(self._admin_prefix)
        ):
            await self._lifecycle.ensure_started()
        await self.app(scope, receive, send)
