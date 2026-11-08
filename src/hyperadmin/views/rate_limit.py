"""Rate-limit middleware for admin requests."""

from __future__ import annotations

from typing import TYPE_CHECKING

from starlette._utils import get_route_path
from starlette.responses import PlainTextResponse

if TYPE_CHECKING:
    from starlette.types import ASGIApp, Receive, Scope, Send

    from hyperadmin.core.rate_limit import RateLimitDecision, RateLimiter

#: Paths below the admin prefix that are never limited: a page load fetches many assets.
_STATIC_PREFIX = "/static/"
_LOGIN_PATHS = frozenset({"/login", "/login/"})


class RateLimitMiddleware:
    """Pure-ASGI per-client rate limit answering ``429`` with ``Retry-After``.

    The client is ``scope["client"]``. Behind a reverse proxy that is the proxy's
    address unless the server rewrites it from ``X-Forwarded-For`` (uvicorn's
    ``--proxy-headers`` with ``forwarded_allow_ips``); this middleware never reads that
    header itself, because any client could forge it to dodge the limit.

    ``limiter`` applies to every http request below ``admin_prefix`` except static
    assets. ``login_limiter`` is an extra, normally stricter, limit on ``POST`` to the
    login form, which is checked first. Websocket and non-admin requests pass through.
    """

    def __init__(
        self,
        app: ASGIApp,
        *,
        limiter: RateLimiter | None = None,
        login_limiter: RateLimiter | None = None,
        admin_prefix: str = "/",
    ) -> None:
        if limiter is None and login_limiter is None:
            msg = "RateLimitMiddleware needs a limiter or a login_limiter"
            raise ValueError(msg)
        self.app = app
        self._limiter = limiter
        self._login_limiter = login_limiter
        self._admin_prefix = admin_prefix.rstrip("/")

    def _relative_path(self, scope: Scope) -> str | None:
        """Return the path below the admin prefix, or ``None`` for a host request."""
        path = get_route_path(scope)
        prefix = self._admin_prefix
        if not prefix:
            return path
        if path == prefix or path.startswith(prefix + "/"):
            return path[len(prefix) :] or "/"
        return None

    async def _decide(self, scope: Scope, path: str) -> RateLimitDecision | None:
        """Return the denying decision, or ``None`` when the request may proceed."""
        client = scope.get("client")
        key = client[0] if client else "unknown"
        if self._login_limiter is not None and scope["method"] == "POST" and path in _LOGIN_PATHS:
            decision = await self._login_limiter.acquire(key)
            if not decision.allowed:
                return decision
        if self._limiter is not None:
            decision = await self._limiter.acquire(key)
            if not decision.allowed:
                return decision
        return None

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        path = self._relative_path(scope) if scope["type"] == "http" else None
        if path is None or path.startswith(_STATIC_PREFIX):
            await self.app(scope, receive, send)
            return
        denied = await self._decide(scope, path)
        if denied is None:
            await self.app(scope, receive, send)
            return
        response = PlainTextResponse(
            "Too many requests. Try again later.",
            status_code=429,
            headers={"Retry-After": str(denied.retry_after)},
        )
        await response(scope, receive, send)
