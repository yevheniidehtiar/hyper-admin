"""Token refresh for sessions started by an OAuth sign-in (``docs/specs/oauth-sso.md``).

:class:`OAuthRefreshMiddleware` sits between the admin session middleware and the
authentication middleware. It reads only the session marker written at sign-in
(``OAUTH_SESSION_KEY``), so a password session costs one dictionary lookup and no
database or network access. When the marker says the access token expires within
the leeway, the stored refresh token is exchanged for a new access token:

- success: the row and the marker get the new expiry and the request proceeds;
- the provider refuses (a revoked refresh token): the session is cleared and a
  "Session expired" message is left for the login page; the authentication
  middleware, next in line, then answers as for any signed-out request;
- the provider is unreachable: one retry after a short delay, then the request
  proceeds with the old token and the next attempt waits for a cooldown.
"""

from __future__ import annotations

import asyncio
import logging
import time
from typing import TYPE_CHECKING, Any

from hyperadmin.auth.exceptions import OAuthProviderError
from hyperadmin.auth.oauth.session import OAUTH_SESSION_KEY, read_oauth_session, set_flash

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable

    from starlette.types import ASGIApp, Receive, Scope, Send

logger = logging.getLogger("hyperadmin")

#: Message left for the login page when the provider no longer accepts the refresh token.
SESSION_EXPIRED_MESSAGE = "Session expired. Please sign in again."


class OAuthRefreshMiddleware:
    """Plain ASGI middleware that keeps the OAuth access token of a session fresh.

    Args:
        app: The downstream ASGI app.
        backend: The ``OAuthBackend`` holding the tokens.
        leeway_seconds: Refresh a token that expires within this many seconds.
        retry_delay: Seconds to wait before the single retry of a failed network call.
        retry_cooldown: Seconds before the next attempt after both calls failed.
        clock: Wall clock in epoch seconds (injectable for tests).
        sleep: Awaitable sleep (injectable for tests).
    """

    def __init__(
        self,
        app: ASGIApp,
        *,
        backend: Any,
        leeway_seconds: float = 60,
        retry_delay: float = 1.0,
        retry_cooldown: float = 30.0,
        clock: Callable[[], float] = time.time,
        sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
    ) -> None:
        self.app = app
        self._backend = backend
        self._leeway = leeway_seconds
        self._retry_delay = retry_delay
        self._retry_cooldown = retry_cooldown
        self._clock = clock
        self._sleep = sleep

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] == "http":
            await self._keep_fresh(scope.get("session"))
        await self.app(scope, receive, send)

    async def _keep_fresh(self, session: Any) -> None:
        """Refresh the token behind ``session`` when it is about to expire."""
        if not isinstance(session, dict):
            return
        marker = read_oauth_session(session, user_id=session.get("user_id"))
        if marker is None:
            return
        if self._backend.provider(marker["provider"]) is None:
            # The provider was removed from the configuration: nothing to refresh with.
            session.pop(OAUTH_SESSION_KEY, None)
            return
        expires_at = marker.get("expires_at")
        now = self._clock()
        if not isinstance(expires_at, (int, float)) or expires_at - now > self._leeway:
            return
        if now < marker.get("retry_at", 0):
            return
        try:
            new_expiry = await self._refresh(marker)
        except OAuthProviderError as exc:
            if exc.transient:
                logger.warning("OAuth token refresh postponed: %s", exc)
                session[OAUTH_SESSION_KEY] = {**marker, "retry_at": now + self._retry_cooldown}
                return
            logger.info("OAuth session of user %s ended: %s", marker["user_id"], exc)
            session.clear()
            set_flash(session, SESSION_EXPIRED_MESSAGE)
            return
        session[OAUTH_SESSION_KEY] = {
            "user_id": marker["user_id"],
            "provider": marker["provider"],
            "expires_at": new_expiry,
        }

    async def _refresh(self, marker: dict[str, Any]) -> float | None:
        """Ask the backend to refresh; a network failure is retried once."""
        provider, user_id = marker["provider"], marker["user_id"]
        try:
            return await self._backend.refresh_token(provider, user_id, leeway=self._leeway)
        except OAuthProviderError as exc:
            if not exc.transient:
                raise
        await self._sleep(self._retry_delay)
        return await self._backend.refresh_token(provider, user_id, leeway=self._leeway)


__all__ = ["SESSION_EXPIRED_MESSAGE", "OAuthRefreshMiddleware"]
