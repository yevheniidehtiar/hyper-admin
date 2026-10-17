"""Admin-scoped session cookie (BYOA SDD C.4).

:class:`AdminSessionMiddleware` wraps Starlette's ``SessionMiddleware`` so the
admin keeps its own signed session cookie, separate from any host session:

- the cookie is named ``settings.session_cookie`` (``hyperadmin_session``), its
  ``Path`` is the per-request admin path (which honours the host's
  ``root_path``), and ``Secure`` follows ``settings.cookie_secure``;
- the host's ``scope["session"]`` is saved before the admin session is loaded
  and restored before ``http.response.start`` is forwarded. A ``Mount`` shares
  the scope dict with the host, so without this a host ``SessionMiddleware``
  would serialise the admin session into the host's own cookie.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from starlette.middleware.sessions import SessionMiddleware
from starlette.requests import Request

from hyperadmin.core.settings import resolve_cookie_secure

if TYPE_CHECKING:
    from collections.abc import Callable

    from starlette.types import ASGIApp, Message, Receive, Scope, Send

    from hyperadmin.core.settings import CookieSecure, SameSiteLiteral

logger = logging.getLogger("hyperadmin")

#: Marks "the host had no ``scope['session']``", as opposed to a ``None`` value.
_MISSING: Any = object()


def rewrite_cookie_header(value: str, *, path: str, secure: bool) -> str:
    """Return a ``Set-Cookie`` value with its ``path`` replaced and ``secure`` set or dropped."""
    attributes: list[str] = []
    for attribute in value.split("; "):
        lowered = attribute.strip().lower()
        if lowered.startswith("path="):
            attributes.append(f"path={path}")
        elif lowered != "secure":
            attributes.append(attribute)
    if secure:
        attributes.append("secure")
    return "; ".join(attributes)


class AdminSessionMiddleware:
    """Pure-ASGI wrapper around Starlette's ``SessionMiddleware`` for the admin.

    Args:
        app: The downstream ASGI app.
        secret_key: Key the session cookie is signed with.
        session_cookie: Cookie name.
        max_age: Cookie lifetime in seconds.
        same_site: ``SameSite`` attribute.
        cookie_secure: ``"auto"`` (``Secure`` on https requests) or a fixed bool.
        admin_path: Returns the per-request admin path the cookie is scoped to.
            ``None`` keeps ``Path=/`` (the legacy router-mode cookie).
    """

    def __init__(
        self,
        app: ASGIApp,
        *,
        secret_key: str,
        session_cookie: str = "hyperadmin_session",
        max_age: int = 1_209_600,
        same_site: SameSiteLiteral = "lax",
        cookie_secure: CookieSecure = "auto",
        admin_path: Callable[[Request], str] | None = None,
    ) -> None:
        self.app = app
        self._cookie_prefix = f"{session_cookie}=".encode("latin-1")
        self._cookie_secure: CookieSecure = cookie_secure
        self._admin_path = admin_path
        self._warned_insecure_proxy = False
        self._session = SessionMiddleware(
            app,
            secret_key=secret_key,
            session_cookie=session_cookie,
            max_age=max_age,
            path="/",
            same_site=same_site,
            https_only=False,
        )

    def _cookie_path(self, scope: Scope) -> str:
        if self._admin_path is None:
            return "/"
        return self._admin_path(Request(scope)) or "/"

    def _warn_if_behind_untrusted_tls_proxy(self, scope: Scope) -> None:
        """Log once when a browser on https reaches the admin over plain http.

        That is a TLS-terminating proxy whose forwarded headers the server does
        not trust: ``cookie_secure="auto"`` then leaves ``Secure`` off.
        """
        if self._warned_insecure_proxy or self._cookie_secure != "auto":
            return
        if resolve_cookie_secure("auto", scope.get("scheme", "http")):
            return
        origin = Request(scope).headers.get("origin", "")
        if origin.lower().startswith("https://"):
            self._warned_insecure_proxy = True
            logger.warning(
                "HyperAdmin received an https Origin over plain http, so admin cookies "
                "are not marked Secure. Set HYPERADMIN_COOKIE_SECURE=true, or configure "
                "the server's forwarded_allow_ips to trust the TLS proxy."
            )

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] not in ("http", "websocket"):
            await self.app(scope, receive, send)
            return

        host_session = scope.get("session", _MISSING)
        # Never let the host's session leak into (or be mistaken for) the admin's.
        scope.pop("session", None)

        def restore_host_session() -> None:
            if host_session is _MISSING:
                scope.pop("session", None)
            else:
                scope["session"] = host_session

        async def send_wrapper(message: Message) -> None:
            if message["type"] == "http.response.start":
                self._scope_cookie(scope, message)
                # Restore before forwarding: an outer host SessionMiddleware
                # serialises scope["session"] when it sees this message.
                restore_host_session()
            await send(message)

        if scope["type"] == "http":
            self._warn_if_behind_untrusted_tls_proxy(scope)
        try:
            await self._session(scope, receive, send_wrapper)
        finally:
            restore_host_session()

    def _scope_cookie(self, scope: Scope, message: Message) -> None:
        """Rewrite the admin session ``Set-Cookie`` with the admin path and ``Secure``."""
        headers = message.get("headers", [])
        path: str | None = None
        secure = resolve_cookie_secure(self._cookie_secure, scope.get("scheme", "http"))
        rewritten: list[tuple[bytes, bytes]] = []
        for name, value in headers:
            if name.lower() == b"set-cookie" and value.startswith(self._cookie_prefix):
                if path is None:
                    path = self._cookie_path(scope)
                cookie = rewrite_cookie_header(value.decode("latin-1"), path=path, secure=secure)
                value = cookie.encode("latin-1")  # noqa: PLW2901 - rebuilt header value
            rewritten.append((name, value))
        message["headers"] = rewritten
