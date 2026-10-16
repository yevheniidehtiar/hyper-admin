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

# FastAPI itself imports ``get_route_path`` from here (not from
# ``starlette.routing``, which only re-exports it without an ``__all__``
# entry — basedpyright flags that re-export as private). See
# starlette/routing.py and fastapi/routing.py for the same import.
from starlette._utils import get_route_path

if TYPE_CHECKING:
    from collections.abc import AsyncIterator, Awaitable, Callable

logger = logging.getLogger("hyperadmin")

_GUARD_REALTIME_WARNING = (
    "HyperAdmin started via the first-request safety net, not an explicit "
    "lifespan. Realtime is enabled but shutdown() has no safety net, so SSE/"
    "WebSocket connections will not be drained on a graceful shutdown. "
    "Compose admin.lifespan() into your host app's own lifespan to fix this."
)

_DEFAULT_RETRY_BACKOFF_SECONDS = 30.0


class StartupUnavailableError(Exception):
    """Raised by the safety net while a recent startup failure's backoff is active.

    Distinguishes "startup is known to be broken, retry suppressed" from a
    fresh failure, so :class:`StartupGuardMiddleware` can turn either into a
    ``503`` without re-running (and re-logging) the failing work on every
    request.
    """


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

    A failure reached through the safety net additionally opens a backoff
    window (``retry_backoff_seconds``, default 30s): further safety-net calls
    inside that window raise :class:`StartupUnavailableError` without re-running
    ``create_tables``/``sync_permissions`` or re-logging a full traceback.
    Without this, a persistently failing startup (e.g. the host's DB is not
    reachable yet) would otherwise re-attempt — and re-log — the same failing
    DDL/permission-sync work on every single admin-prefixed request, by
    anyone, unauthenticated, serialised through the lock. The explicit path
    (:meth:`startup`) never observes this window — it always attempts and
    raises immediately, so a host-driven retry is never silently suppressed.
    """

    def __init__(
        self,
        *,
        create_tables: Callable[[], Awaitable[None]],
        sync_permissions: Callable[[], Awaitable[None]],
        drain: Callable[[], Awaitable[None]],
        realtime_enabled: bool,
        retry_backoff_seconds: float = _DEFAULT_RETRY_BACKOFF_SECONDS,
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
            retry_backoff_seconds: How long a safety-net call suppresses
                retrying a startup that just failed. Never applies to the
                explicit ``startup()`` path.
        """
        self._create_tables = create_tables
        self._sync_permissions = sync_permissions
        self._drain = drain
        self._realtime_enabled = realtime_enabled
        self._retry_backoff_seconds = retry_backoff_seconds
        self._started = False
        self._lock = asyncio.Lock()
        self._retry_at = 0.0

    @property
    def started(self) -> bool:
        """Whether ``startup()`` has completed successfully at least once."""
        return self._started

    @property
    def retry_backoff_seconds(self) -> float:
        """Seconds a safety-net failure suppresses retrying startup for."""
        return self._retry_backoff_seconds

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
            now = asyncio.get_running_loop().time()
            if via_guard and now < self._retry_at:
                msg = "HyperAdmin startup failed recently; retry suppressed."
                raise StartupUnavailableError(msg)
            had_failed_before = self._retry_at > 0
            try:
                await self._create_tables()
                await self._sync_permissions()
            except Exception:
                if via_guard:
                    if had_failed_before:
                        # Already logged the full traceback for the first failure in
                        # this backoff window — every repeat has the same cause, so
                        # logging just the message keeps the log from flooding.
                        logger.error(
                            "HyperAdmin startup failed again; retry suppressed for %.0fs.",
                            self._retry_backoff_seconds,
                        )
                    else:
                        logger.exception(
                            "HyperAdmin startup failed; the next admin request will retry."
                        )
                    self._retry_at = now + self._retry_backoff_seconds
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


async def _send_startup_unavailable(send: Any, *, retry_after: float) -> None:
    """Send a plain ``503`` instead of letting a startup failure 500 the request.

    Used only for ``http`` scopes — see :meth:`StartupGuardMiddleware.__call__`.
    """
    await send(
        {
            "type": "http.response.start",
            "status": 503,
            "headers": [
                (b"content-type", b"text/plain; charset=utf-8"),
                (b"retry-after", str(max(1, int(retry_after))).encode("ascii")),
            ],
        }
    )
    await send(
        {
            "type": "http.response.body",
            "body": b"HyperAdmin startup failed; retry shortly.",
        }
    )


class StartupGuardMiddleware:
    """Pure-ASGI safety net: calls ``lifecycle.ensure_started()`` once.

    Only requests whose *route path* (``http`` or ``websocket``) is
    ``admin_prefix`` itself, or starts with ``admin_prefix + "/"``, trigger the
    check; every other host route passes straight through untouched. Matching
    is on whole path segments, via Starlette's ``get_route_path`` (which reads
    ``scope["root_path"]`` too, so this still matches when the host app is
    itself mounted, or served behind ``--root-path``) — a plain
    ``path.startswith(admin_prefix)`` would wrongly match a host's own
    ``/admin-api/...`` or ``/administration`` routes.

    This is intentionally plain ASGI rather than ``BaseHTTPMiddleware`` — it
    never buffers or wraps the response, so streaming SSE/WebSocket
    connections are unaffected.

    Once ``lifecycle.started`` is ``True`` the check is a single attribute
    read, so the steady-state cost of this middleware is negligible.
    """

    def __init__(self, app: Any, *, lifecycle: Lifecycle, admin_prefix: str) -> None:
        self.app = app
        self._lifecycle = lifecycle
        self._admin_prefix = admin_prefix.rstrip("/") or "/"

    def _matches_admin_prefix(self, scope: Any) -> bool:
        prefix = self._admin_prefix
        if prefix == "/":
            return True
        path = get_route_path(scope)
        return path == prefix or path.startswith(prefix + "/")

    async def __call__(self, scope: Any, receive: Any, send: Any) -> None:
        scope_type = scope.get("type")
        if (
            scope_type in ("http", "websocket")
            and not self._lifecycle.started
            and self._matches_admin_prefix(scope)
        ):
            try:
                await self._lifecycle.ensure_started()
            except Exception:
                if scope_type == "http":
                    # A websocket scope has no HTTP response to send — the raised
                    # exception is left to propagate (the ASGI server rejects the
                    # connection) rather than let a healthy-looking admin page
                    # desync permission state. The lock's own backoff (see
                    # Lifecycle._run_startup) already prevents this from flooding
                    # the DB/log on repeat attempts, over either scope type.
                    await _send_startup_unavailable(
                        send, retry_after=self._lifecycle.retry_backoff_seconds
                    )
                    return
                raise
        await self.app(scope, receive, send)
