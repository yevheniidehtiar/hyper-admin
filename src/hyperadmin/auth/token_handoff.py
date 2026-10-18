"""Token handoff, bearer login form and bridge logout for bearer-only hosts (SDD B.4).

A bearer-only host (``OAuth2PasswordBearer`` plus an SPA) cannot authenticate a
plain browser navigation to ``/admin``: the browser sends no ``Authorization``
header. With ``ExternalAuth(token_cookie=TokenCookie())`` the admin stores the
bearer token in an admin-scoped ``HttpOnly`` cookie, which ``HyperAdminRoute``
copies back into ``Authorization`` on later admin requests. Two ways in:

- ``POST {prefix}/auth/session`` (:func:`token_handoff_view`): an SPA hands over
  the bearer it already holds. The route is guarded by
  ``build_admin_dependency(auth)`` itself, so the host dependency validates the
  token natively, and it is exempt from CSRF (a cross-site page cannot set
  ``Authorization``).
- ``GET/POST {prefix}/login`` (:func:`bridge_login_view`), opt-in with
  ``TokenCookie(token_endpoint=...)``: credentials are posted **server side** to
  the host's token endpoint (or an ``issue_token`` callable), so a bearer-only
  host needs no frontend change at all.

``POST {prefix}/logout`` (:func:`bridge_logout_view`) clears the cookie and
redirects to ``ExternalAuth.logout_url``.

Every function here takes the per-request admin path as a plain string and
imports nothing from ``views/`` (CONSTITUTION.md §2); ``core/app.py`` wires them
into routes.
"""

from __future__ import annotations

import base64
import binascii
import inspect
import json
import logging
import time
import urllib.error
import urllib.request
from typing import TYPE_CHECKING, Any
from urllib.parse import unquote, urlencode, urlsplit

from fastapi import HTTPException, Request
from fastapi.dependencies.utils import get_dependant
from fastapi.openapi.models import OAuth2
from fastapi.security import OAuth2PasswordBearer
from starlette.concurrency import run_in_threadpool
from starlette.responses import RedirectResponse, Response

from hyperadmin.core.settings import CookieSecure, resolve_cookie_secure

if TYPE_CHECKING:
    from collections.abc import Callable

    from fastapi.templating import Jinja2Templates
    from starlette.types import ASGIApp, Message

    from hyperadmin.auth.bridge import MaybeAwaitable, TokenCookie

__all__ = [
    "DISCOVER_TOKEN_URL",
    "MAX_TOKEN_BYTES",
    "bridge_login_view",
    "bridge_logout_view",
    "cookie_max_age",
    "discover_token_url",
    "jwt_expiry",
    "reject_oversized_token",
    "request_token",
    "resolve_token_endpoint",
    "safe_next",
    "token_handoff_view",
]

logger = logging.getLogger("hyperadmin.auth")

#: Largest bearer token the handoff stores. A cookie holds about 4 KB, name and
#: attributes included; a larger token would be silently dropped by the browser.
MAX_TOKEN_BYTES = 3800

#: ``TokenCookie(token_endpoint="auto")``: post to the ``tokenUrl`` of the
#: ``OAuth2PasswordBearer`` found in ``ExternalAuth.get_user``'s dependency tree.
DISCOVER_TOKEN_URL = "auto"  # noqa: S105 - a sentinel, not a secret

#: Seconds a server-side call to an absolute token URL may take.
_TOKEN_REQUEST_TIMEOUT = 10.0


# ── Token helpers ──────────────────────────────────────────────────────────


def _credentials(authorization: str | None) -> str:
    """Return the credentials part of an ``Authorization`` header (``""`` when absent)."""
    if not authorization:
        return ""
    return authorization.partition(" ")[2].strip() or authorization.strip()


def _bearer_token(authorization: str | None, scheme: str) -> str | None:
    """Return the token of ``"<scheme> <token>"`` (scheme case-insensitive), else ``None``."""
    if not authorization:
        return None
    given, _, token = authorization.partition(" ")
    token = token.strip()
    if given.lower() != scheme.lower() or not token:
        return None
    return token


def reject_oversized_token(request: Request) -> None:
    """FastAPI dependency: 400 when the bearer token exceeds :data:`MAX_TOKEN_BYTES`.

    Listed before the admin principal on the handoff route, so an oversized
    token is refused before the host dependency ever sees it.
    """
    credentials = _credentials(request.headers.get("authorization"))
    if len(credentials.encode("utf-8")) > MAX_TOKEN_BYTES:
        raise HTTPException(status_code=400, detail="Token too large for the admin cookie")


def jwt_expiry(token: str) -> float | None:
    """Return the ``exp`` claim of a JWT, read **without** verifying its signature.

    Used only to size the cookie lifetime; the host dependency still verifies
    every request's token. Returns ``None`` for an opaque token, a malformed
    payload or a missing/non-numeric ``exp``.
    """
    parts = token.split(".")
    if len(parts) != 3:  # noqa: PLR2004 - header.payload.signature
        return None
    payload = parts[1]
    try:
        raw = base64.urlsafe_b64decode(payload + "=" * (-len(payload) % 4))
        claims = json.loads(raw)
    except (binascii.Error, ValueError):
        return None
    exp = claims.get("exp") if isinstance(claims, dict) else None
    if isinstance(exp, bool) or not isinstance(exp, (int, float)):
        return None
    return float(exp)


def cookie_max_age(token: str, max_age: int | None, *, now: float | None = None) -> int | None:
    """Return the token cookie's ``Max-Age``: ``min(max_age, exp - now)`` (SDD B.4).

    An opaque token keeps ``max_age``; with neither, the cookie is a session
    cookie (``None``). Never negative.
    """
    exp = jwt_expiry(token)
    if exp is None:
        return max_age
    remaining = max(0, int(exp - (time.time() if now is None else now)))
    return remaining if max_age is None else min(max_age, remaining)


def _set_token_cookie(
    response: Response,
    request: Request,
    cookie: TokenCookie,
    token: str,
    *,
    admin_path: str,
    cookie_secure: CookieSecure,
) -> None:
    response.set_cookie(
        cookie.name,
        token,
        max_age=cookie_max_age(token, cookie.max_age),
        path=admin_path or "/",
        httponly=True,
        samesite="lax",
        secure=resolve_cookie_secure(cookie_secure, request.url.scheme),
    )


# ── next validation ────────────────────────────────────────────────────────


def safe_next(value: str | None, admin_path: str) -> str:
    """Return ``value`` when it is a safe in-admin redirect target, else the dashboard.

    Safe means a relative path starting with ``admin_path + "/"``, with no
    scheme or authority, no ``//`` prefix, no backslash, no control or
    whitespace character and no ``.``/``..`` segment (encoded or not) that a
    browser would resolve outside the admin (SDD B.4).
    """
    dashboard = f"{admin_path}/"
    if not value or "\\" in value or value.startswith("//"):
        return dashboard
    if any(ord(char) < 0x21 or ord(char) == 0x7F for char in value):  # noqa: PLR2004
        return dashboard
    parts = urlsplit(value)
    if parts.scheme or parts.netloc or not value.startswith(dashboard):
        return dashboard
    segments = unquote(parts.path).split("/")
    if any(segment in {".", ".."} for segment in segments):
        return dashboard
    return value


# ── Token endpoint ─────────────────────────────────────────────────────────


def discover_token_url(get_user: Callable[..., Any]) -> str | None:
    """Return the ``tokenUrl`` of the first ``OAuth2PasswordBearer`` in ``get_user``'s tree."""
    stack = [get_dependant(path="", call=get_user)]
    while stack:
        dependant = stack.pop()
        call = dependant.call
        model = call.model if isinstance(call, OAuth2PasswordBearer) else None
        if isinstance(model, OAuth2) and model.flows.password is not None:
            return model.flows.password.tokenUrl
        stack.extend(dependant.dependencies)
    return None


def resolve_token_endpoint(
    endpoint: str | Callable[[str, str], MaybeAwaitable[str | None]],
    get_user: Callable[..., Any],
) -> str | Callable[[str, str], MaybeAwaitable[str | None]]:
    """Resolve ``TokenCookie.token_endpoint``, expanding ``"auto"`` (:data:`DISCOVER_TOKEN_URL`).

    Raises:
        ValueError: ``"auto"`` was given but ``get_user`` depends on no
            ``OAuth2PasswordBearer``.
    """
    if endpoint != DISCOVER_TOKEN_URL:
        return endpoint
    url = discover_token_url(get_user)
    if url is None:
        msg = (
            'TokenCookie(token_endpoint="auto") found no OAuth2PasswordBearer tokenUrl in '
            "ExternalAuth.get_user's dependencies; pass the token URL or an "
            "issue_token(username, password) callable instead."
        )
        raise ValueError(msg)
    return url


def _post_url(url: str, body: bytes) -> tuple[int, bytes]:
    """POST a form to an absolute http(s) URL (runs in a worker thread)."""
    outgoing = urllib.request.Request(  # noqa: S310 - scheme checked by the caller
        url,
        data=body,
        headers={
            "Content-Type": "application/x-www-form-urlencoded",
            "Accept": "application/json",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(outgoing, timeout=_TOKEN_REQUEST_TIMEOUT) as reply:  # noqa: S310
            return reply.status, reply.read()
    except urllib.error.HTTPError as exc:
        return exc.code, b""
    except (urllib.error.URLError, OSError):
        logger.warning("HyperAdmin bridge login: token endpoint %s is unreachable", url)
        return 0, b""


async def _post_in_process(app: ASGIApp, url: str, body: bytes) -> tuple[int, bytes]:
    """POST a form to a path of the host app, in process (no network, no server)."""
    parts = urlsplit(url)
    path = "/" + parts.path.lstrip("/")
    scope: dict[str, Any] = {
        "type": "http",
        "asgi": {"version": "3.0"},
        "http_version": "1.1",
        "method": "POST",
        "scheme": "http",
        "path": path,
        "raw_path": path.encode("latin-1"),
        "root_path": "",
        "query_string": parts.query.encode("latin-1"),
        "headers": [
            (b"host", b"hyperadmin.internal"),
            (b"content-type", b"application/x-www-form-urlencoded"),
            (b"content-length", str(len(body)).encode("latin-1")),
            (b"accept", b"application/json"),
        ],
        "client": ("127.0.0.1", 0),
        "server": ("hyperadmin.internal", 80),
    }
    sent = False
    status = 0
    chunks: list[bytes] = []

    async def receive() -> Message:
        nonlocal sent
        if sent:
            return {"type": "http.disconnect"}
        sent = True
        return {"type": "http.request", "body": body, "more_body": False}

    async def send(message: Message) -> None:
        nonlocal status
        if message["type"] == "http.response.start":
            status = int(message["status"])
        elif message["type"] == "http.response.body":
            chunks.append(message.get("body", b""))

    try:
        await app(scope, receive, send)
    except Exception:
        logger.exception("HyperAdmin bridge login: the host token endpoint %s failed", url)
        return 0, b""
    return status, b"".join(chunks)


async def request_token(
    endpoint: str | Callable[[str, str], MaybeAwaitable[str | None]],
    username: str,
    password: str,
    *,
    host_app: ASGIApp,
) -> str | None:
    """Exchange credentials for an access token, server side; ``None`` on failure.

    ``endpoint`` is an ``issue_token(username, password)`` callable (sync or
    async), an absolute ``http(s)`` URL, or a path on ``host_app`` (called in
    process). URLs get an OAuth2 password-grant form and must answer 200 with a
    JSON ``access_token``.
    """
    if callable(endpoint):
        issued = endpoint(username, password)
        if inspect.isawaitable(issued):
            issued = await issued
        return issued or None
    body = urlencode({"grant_type": "password", "username": username, "password": password})
    if urlsplit(endpoint).scheme in {"http", "https"}:
        status, payload = await run_in_threadpool(_post_url, endpoint, body.encode())
    else:
        status, payload = await _post_in_process(host_app, endpoint, body.encode())
    if status != 200:  # noqa: PLR2004
        return None
    try:
        data = json.loads(payload)
    except ValueError:
        return None
    token = data.get("access_token") if isinstance(data, dict) else None
    return token if isinstance(token, str) and token else None


# ── Views ──────────────────────────────────────────────────────────────────


async def token_handoff_view(
    request: Request,
    *,
    cookie: TokenCookie,
    admin_path: str,
    cookie_secure: CookieSecure,
    next_param: str,
) -> Response:
    """``POST {prefix}/auth/session``: store the (already validated) bearer in the cookie.

    The host dependency has accepted the request's ``Authorization`` header by
    the time this runs. Returns 204, or 303 to a validated ``next``; 400 when
    the header does not carry a ``TokenCookie.scheme`` token.
    """
    token = _bearer_token(request.headers.get("authorization"), cookie.scheme)
    if token is None:
        raise HTTPException(
            status_code=400, detail=f"Expected an 'Authorization: {cookie.scheme} <token>' header"
        )
    next_value = request.query_params.get(next_param)
    response: Response
    if next_value is None:
        response = Response(status_code=204)
    else:
        response = RedirectResponse(safe_next(next_value, admin_path), status_code=303)
    _set_token_cookie(
        response, request, cookie, token, admin_path=admin_path, cookie_secure=cookie_secure
    )
    return response


async def bridge_logout_view(
    request: Request,
    *,
    cookie: TokenCookie | None,
    admin_path: str,
    logout_url: str | None,
    cookie_secure: CookieSecure,
) -> Response:
    """``POST {prefix}/logout``: clear the token cookie, then 303 to ``logout_url or "/"``."""
    response = RedirectResponse(logout_url or "/", status_code=303)
    if cookie is not None:
        response.delete_cookie(
            cookie.name,
            path=admin_path or "/",
            httponly=True,
            samesite="lax",
            secure=resolve_cookie_secure(cookie_secure, request.url.scheme),
        )
    return response


async def bridge_login_view(  # noqa: PLR0913 - one view, its wiring passed explicitly
    request: Request,
    *,
    templates: Jinja2Templates,
    cookie: TokenCookie,
    endpoint: str | Callable[[str, str], MaybeAwaitable[str | None]],
    host_app: ASGIApp,
    admin_path: str,
    cookie_secure: CookieSecure,
    next_param: str,
) -> Response:
    """``GET/POST {prefix}/login``: the opt-in admin login form for bearer hosts (SDD B.4).

    GET renders ``login.html``; POST exchanges the credentials for a token
    through :func:`request_token` and stores it in the cookie, then 303s to the
    validated ``next``. Wrong credentials re-render the form with an error.
    """
    error: str | None = None
    next_value = request.query_params.get(next_param)
    if request.method == "POST":
        form = await request.form()
        posted_next = form.get(next_param)
        next_value = posted_next if isinstance(posted_next, str) else next_value
        token = await request_token(
            endpoint,
            str(form.get("username", "")),
            str(form.get("password", "")),
            host_app=host_app,
        )
        if token is not None:
            response = RedirectResponse(safe_next(next_value, admin_path), status_code=303)
            _set_token_cookie(
                response, request, cookie, token, admin_path=admin_path, cookie_secure=cookie_secure
            )
            return response
        error = "Invalid username or password."
    target = safe_next(next_value, admin_path)
    context: dict[str, Any] = {
        "request": request,
        "error": error,
        "admin_prefix": admin_path,
        "next_param": next_param,
        # Only a validated, explicit target is round-tripped through the form.
        "next_url": target if next_value and target == next_value else None,
    }
    return templates.TemplateResponse(request, "login.html", context)
