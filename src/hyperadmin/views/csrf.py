"""``CsrfGuard``: the signed double-submit CSRF check behind ``HyperAdminRoute`` (SDD D.1).

``core/csrf.py`` issues and verifies tokens; this module is the HTTP side. It
implements the route class's ``RouteCsrfCheck`` seam:

- :meth:`CsrfGuard.verify` runs on every admin request, after auth and before
  the handler. It first makes sure the request has a token
  (``request.state.csrf_token``, rendered by the ``csrf_token()`` /
  ``csrf_input()`` template globals), then checks unsafe methods:

  1. ``Sec-Fetch-Site: cross-site`` fails.
  2. The ``Origin`` check: its ``host[:port]`` must equal the request ``Host``
     (or ``X-Forwarded-Host``), or the origin must be listed in
     ``csrf_trusted_origins``. An ``https`` Origin on an ``http`` request is
     accepted on the host alone — the TLS-terminating proxy case.
     ``Sec-Fetch-Site: same-origin`` passes outright.
  3. The token comes from the ``X-CSRF-Token`` header, else from the
     ``csrf_token`` field of a urlencoded or multipart body, parsed with
     ``request.form()`` on the very ``Request`` the handler receives, so the
     handler is served from Starlette's form cache.
  4. The token must carry a valid signature and equal the cookie.

- :meth:`CsrfGuard.attach` sets the ``hyperadmin_csrf`` cookie on the handler's
  response when the request had none (or an invalid one).

Tokens are per cookie, not per request, so several tabs and parallel HTMX
requests stay valid. ``X-Forwarded-Host`` is safe to honour here: a
cross-site page cannot set it (a browser form sends no custom headers, and
``fetch`` with one needs a CORS preflight), and the token pair stays the
primary control.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any
from urllib.parse import urlsplit

from jinja2 import pass_context
from markupsafe import Markup
from starlette.responses import PlainTextResponse, Response

from hyperadmin.core.csrf import CsrfTokenSigner, EffectiveCsrfMode
from hyperadmin.core.settings import CookieSecure, resolve_cookie_secure
from hyperadmin.views.urls import admin_base_path

if TYPE_CHECKING:
    from collections.abc import Callable, Iterable, Mapping

    from fastapi import Request
    from jinja2 import Environment
    from starlette.requests import HTTPConnection

__all__ = [
    "CSRF_FAILED_HEADER",
    "CsrfGuard",
    "install_csrf_globals",
    "make_websocket_origin_check",
]

logger = logging.getLogger("hyperadmin.csrf")


#: Response header marking a CSRF rejection, so the UI can offer a reload.
CSRF_FAILED_HEADER = "X-HyperAdmin-CSRF"

_SAFE_METHODS = frozenset({"GET", "HEAD", "OPTIONS", "TRACE"})
_FORM_TYPES = ("application/x-www-form-urlencoded", "multipart/form-data")
_DEFAULT_PORTS = {"http": "80", "https": "443"}
#: A WebSocket handshake's scheme, as the scheme of the page that opened it.
_WS_SCHEMES = {"ws": "http", "wss": "https"}
#: ``request.state`` flag: the token was issued on this request, so the cookie
#: must be set on the response.
_ISSUED_FLAG = "csrf_token_issued"


def _strip_default_port(host: str, *schemes: str) -> str:
    """Drop a ``:80``/``:443`` suffix that is the default port of one of ``schemes``."""
    for scheme in schemes:
        suffix = f":{_DEFAULT_PORTS[scheme]}"
        if host.endswith(suffix):
            return host[: -len(suffix)]
    return host


def _normalize_origin(origin: str) -> str:
    return origin.strip().rstrip("/").lower()


def _origin_allowed(conn: HTTPConnection, origin: str, trusted_origins: frozenset[str]) -> bool:
    """Return whether ``origin`` is the connection's own host or a trusted origin.

    A WebSocket's ``ws``/``wss`` scheme is compared as ``http``/``https``, the
    scheme of the page that opened it.
    """
    if _normalize_origin(origin) in trusted_origins:
        return True
    parts = urlsplit(origin.strip().lower())
    if not parts.netloc or parts.scheme not in _DEFAULT_PORTS:
        return False  # "null", or an opaque/unknown scheme
    request_scheme = _WS_SCHEMES.get(conn.url.scheme, conn.url.scheme)
    # A TLS-terminating proxy uvicorn does not trust: the app sees http while
    # the browser sends an https Origin. Compare hosts only in that case.
    if parts.scheme != request_scheme and not (
        request_scheme == "http" and parts.scheme == "https"
    ):
        return False
    origin_host = _strip_default_port(parts.netloc, parts.scheme)
    candidates = [conn.headers.get("host", "")]
    forwarded = conn.headers.get("x-forwarded-host")
    if forwarded:
        candidates.append(forwarded.split(",")[0])
    return any(
        origin_host == _strip_default_port(candidate.strip().lower(), parts.scheme, request_scheme)
        for candidate in candidates
        if candidate.strip()
    )


def make_websocket_origin_check(
    trusted_origins: Iterable[str] = (),
) -> Callable[[HTTPConnection], bool]:
    """Build the realtime WebSocket's handshake ``Origin`` check (SDD D.1).

    WebSockets do not go through ``HyperAdminRoute``, and a browser attaches the
    admin's cookies to a handshake opened by any page, so the handler vets
    ``Origin`` itself: it must be the admin's own host (as for unsafe HTTP
    requests) or listed in ``csrf_trusted_origins``. A handshake without
    ``Origin`` (a non-browser client, which carries no ambient cookies) passes.
    The check applies in every CSRF mode: it is the only cross-site defence
    the WebSocket has.
    """
    trusted = frozenset(_normalize_origin(o) for o in trusted_origins)

    def origin_allowed(conn: HTTPConnection) -> bool:
        origin = conn.headers.get("origin")
        if origin is None or _origin_allowed(conn, origin, trusted):
            return True
        logger.warning(
            "HyperAdmin WebSocket Origin check failed: Origin %r does not match Host %r. "
            "Add the origin to csrf_trusted_origins (HYPERADMIN_CSRF_TRUSTED_ORIGINS) "
            "if it is legitimate.",
            origin,
            conn.headers.get("host", ""),
        )
        return False

    return origin_allowed


def install_csrf_globals(env: Environment, *, field_name: str, header_name: str) -> None:
    """Add the ``csrf_token()`` and ``csrf_input()`` globals to the admin's Jinja env.

    Both read ``request.state.csrf_token`` (set by :meth:`CsrfGuard.ensure_token`)
    and render nothing when the request carries no token (CSRF off).
    ``csrf_header_name`` is exposed for ``_base.html``'s ``hx-headers``.
    """

    @pass_context
    def csrf_token(context: Mapping[str, Any]) -> str:
        request = context.get("request")
        state = getattr(request, "state", None)
        return str(getattr(state, "csrf_token", "") or "")

    @pass_context
    def csrf_input(context: Mapping[str, Any]) -> Markup:
        token = csrf_token(context)
        if not token:
            return Markup("")
        return Markup('<input type="hidden" name="{}" value="{}">').format(field_name, token)

    env.globals["csrf_token"] = csrf_token
    env.globals["csrf_input"] = csrf_input
    env.globals["csrf_header_name"] = header_name


class CsrfGuard:
    """Signed double-submit CSRF check for one admin.

    Args:
        secret_key: The admin ``secret_key``; the signing key is derived from it.
        mode: ``"enforce"`` rejects failures with a 403, ``"report"`` lets them
            through with a ``WARNING``. Resolve ``"auto"`` with
            :func:`hyperadmin.core.csrf.resolve_csrf_mode` first.
        cookie_name: The token cookie (``csrf_cookie_name``).
        header_name: The token request header (``csrf_header_name``).
        field_name: The token form field (``csrf_field_name``).
        trusted_origins: Extra origins accepted by the ``Origin`` check
            (``csrf_trusted_origins``), e.g. ``"https://admin.example"``.
        cookie_secure: ``"auto"`` marks the cookie ``Secure`` when the effective
            request scheme is https; ``True``/``False`` force it.

    Raises:
        ValueError: ``mode`` is not ``"enforce"`` or ``"report"``.
    """

    def __init__(
        self,
        secret_key: str,
        *,
        mode: EffectiveCsrfMode = "enforce",
        cookie_name: str = "hyperadmin_csrf",
        header_name: str = "X-CSRF-Token",
        field_name: str = "csrf_token",
        trusted_origins: Iterable[str] = (),
        cookie_secure: CookieSecure = "auto",
    ) -> None:
        if mode not in {"enforce", "report"}:
            msg = f"CsrfGuard mode must be 'enforce' or 'report', not {mode!r}"
            raise ValueError(msg)
        self.signer = CsrfTokenSigner(secret_key)
        self.mode = mode
        self.cookie_name = cookie_name
        self.header_name = header_name
        self.field_name = field_name
        self.trusted_origins = frozenset(_normalize_origin(o) for o in trusted_origins)
        self.cookie_secure: CookieSecure = cookie_secure

    # ── Token lifecycle ────────────────────────────────────────────────────

    def ensure_token(self, request: Request) -> str:
        """Return this request's token, issuing a new one when the cookie is unusable.

        Sets ``request.state.csrf_token``; a newly issued token is set as the
        cookie by :meth:`attach`.
        """
        cookie = request.cookies.get(self.cookie_name)
        if self.signer.is_valid(cookie):
            token = str(cookie)
        else:
            token = self.signer.issue()
            setattr(request.state, _ISSUED_FLAG, True)
        request.state.csrf_token = token
        return token

    def attach(self, request: Request, response: Response) -> None:
        """Set the token cookie on ``response`` when this request issued one."""
        if not getattr(request.state, _ISSUED_FLAG, False):
            return
        secure = resolve_cookie_secure(self.cookie_secure, request.url.scheme)
        response.set_cookie(
            self.cookie_name,
            request.state.csrf_token,
            path=admin_base_path(request) or "/",
            httponly=True,
            samesite="lax",
            secure=secure,
        )

    # ── Verification ───────────────────────────────────────────────────────

    async def verify(self, request: Request) -> Response | None:
        """Check an unsafe request; return the 403 to send instead, or ``None``."""
        self.ensure_token(request)
        if request.method in _SAFE_METHODS:
            return None
        reason = self._origin_failure(request) or await self._token_failure(request)
        if reason is None:
            return None
        if self.mode == "report":
            logger.warning(
                "HyperAdmin csrf check failed (report mode, request allowed): %s %s: %s",
                request.method,
                request.url.path,
                reason,
            )
            return None
        logger.info(
            "HyperAdmin csrf check failed: %s %s: %s", request.method, request.url.path, reason
        )
        return PlainTextResponse(
            "CSRF token missing or invalid",
            status_code=403,
            headers={CSRF_FAILED_HEADER: "failed"},
        )

    def _origin_failure(self, request: Request) -> str | None:
        """Return why the fetch-metadata/``Origin`` check fails, or ``None``."""
        fetch_site = request.headers.get("sec-fetch-site", "").lower()
        if fetch_site == "cross-site":
            return "Sec-Fetch-Site is cross-site"
        if fetch_site == "same-origin":
            return None
        origin = request.headers.get("origin")
        if origin is None or self._origin_allowed(request, origin):
            return None
        host = request.headers.get("host", "")
        logger.warning(
            "HyperAdmin csrf Origin check failed: Origin %r does not match Host %r "
            "(X-Forwarded-Host %r). Add the origin to csrf_trusted_origins "
            "(HYPERADMIN_CSRF_TRUSTED_ORIGINS) if it is legitimate.",
            origin,
            host,
            request.headers.get("x-forwarded-host"),
        )
        return f"Origin {origin!r} does not match Host {host!r}"

    def _origin_allowed(self, request: Request, origin: str) -> bool:
        return _origin_allowed(request, origin, self.trusted_origins)

    async def _token_failure(self, request: Request) -> str | None:
        """Return why the double-submit token check fails, or ``None``."""
        cookie = request.cookies.get(self.cookie_name)
        if not self.signer.is_valid(cookie):
            return "csrf cookie missing or invalid"
        submitted: object = request.headers.get(self.header_name)
        if submitted is None:
            content_type = request.headers.get("content-type", "").lower()
            if content_type.startswith(_FORM_TYPES):
                form = await request.form()
                submitted = form.get(self.field_name)
        if submitted is None:
            return "csrf token missing"
        if not self.signer.matches(cookie, submitted):
            return "csrf token does not match the cookie"
        return None
