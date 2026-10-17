"""``HyperAdminRoute``: the route class every admin ``APIRouter`` uses (BYOA SDD B.2).

A host dependency such as ``OAuth2PasswordBearer(auto_error=True)`` raises
``HTTPException(401)`` before any admin code runs, so the only admin-scoped
place to turn it into a browser redirect is a wrapper around the route handler.
That wrapper is also the one place that performs the request pipeline, **in
this order, on one ``Request`` object**:

1. **Token-cookie bridge** — with no ``Authorization`` header, the token cookie
   is copied into one by mutating ``scope["headers"]`` before any body read.
2. **Auth** — FastAPI solves the route dependencies, including the admin
   principal (``auth.bridge.build_admin_dependency``).
3. **CSRF** — verified on the same ``Request`` the handler receives, so a form
   the check parsed is served from Starlette's cache, never from a consumed
   receive stream.
4. **Handler** — runs, and the CSRF cookie is attached to its response.

Auth errors are then mapped to responses (the B.2 table): a login redirect,
``HX-Redirect``/``HX-Refresh`` for HTMX, a plain 401/403 for API paths, and
the ``can_access`` page for an admin-wide denial. A 403 raised by a *view*
(model or object permission) is told apart from a 403 raised while solving
dependencies by the phase the request is in, and passes through unchanged.

This module imports only ``core/`` and ``views/`` (CONSTITUTION.md §2); the
``ExternalAuth`` settings reach it as plain keyword arguments.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Protocol
from urllib.parse import urlencode

from fastapi import Depends, Request
from fastapi.routing import APIRoute
from starlette._utils import get_route_path
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.requests import cookie_parser
from starlette.responses import HTMLResponse, PlainTextResponse, RedirectResponse, Response

from hyperadmin.core.auth import AdminAccessDenied, AdminAuthenticationRequired
from hyperadmin.views.error_pages import HTML_ERROR_STATUSES, render_error, wants_html
from hyperadmin.views.urls import admin_base_path

if TYPE_CHECKING:
    from collections.abc import Callable, Coroutine, Sequence

    from fastapi import params
    from fastapi.templating import Jinja2Templates

__all__ = ["DEFAULT_API_PREFIXES", "RouteCsrfCheck", "make_admin_route_class"]

#: Admin-relative path prefixes served to programs, not people: auth errors
#: there are a bare 401/403, never a redirect or an HTML page.
DEFAULT_API_PREFIXES: tuple[str, ...] = ("/realtime/",)

#: ``scope`` key recording which phase of the pipeline a request is in.
_PHASE_KEY = "hyperadmin.route_phase"
_PHASE_DEPENDENCIES = "dependencies"
_PHASE_ENDPOINT = "endpoint"

_SIGN_IN_PAGE = (
    "<!doctype html><html><head><meta charset='utf-8'><title>Sign in required</title></head>"
    "<body><h1>Sign in to the host application</h1>"
    "<p>The admin uses the host application's login. Sign in there, then reload this page.</p>"
    "</body></html>"
)
_ACCESS_DENIED_PAGE = (
    "<!doctype html><html><head><meta charset='utf-8'><title>Access denied</title></head>"
    "<body><h1>Access denied</h1>"
    "<p>You are signed in, but the admin's <code>can_access</code> check does not admit "
    "this account.</p></body></html>"
)


class RouteCsrfCheck(Protocol):
    """The CSRF seam the route class calls (implemented by ``views/csrf.py``)."""

    async def verify(self, request: Request) -> Response | None:
        """Return a failure response to send instead of the handler's, or ``None``."""

    def attach(self, request: Request, response: Response) -> None:
        """Attach the CSRF cookie to the handler's response."""


class _CsrfRejected(Exception):  # noqa: N818 - internal control flow, never escapes the route
    """Carries the CSRF failure response out of dependency solving."""

    def __init__(self, response: Response) -> None:
        super().__init__("CSRF check failed")
        self.response = response


def _bridge_token_cookie(request: Request, cookie_name: str | None, scheme: str) -> bool:
    """Copy the token cookie into ``Authorization`` when no such header is present.

    Mutates ``scope["headers"]`` (and drops any cached ``Headers``) so every
    later reader — the host dependency included — sees the header. Returns
    whether a header was added.
    """
    if cookie_name is None:
        return False
    raw_headers: list[tuple[bytes, bytes]] = list(request.scope.get("headers", []))
    cookie_header = ""
    for key, value in raw_headers:
        if key == b"authorization":
            return False
        if key == b"cookie":
            cookie_header = value.decode("latin-1")
    token = cookie_parser(cookie_header).get(cookie_name)
    if not token:
        return False
    raw_headers.append((b"authorization", f"{scheme} {token}".encode("latin-1")))
    request.scope["headers"] = raw_headers
    request.__dict__.pop("_headers", None)
    return True


def _browser_path(request: Request) -> str:
    """Return the browser-visible path of this request (host root_path included)."""
    return (request.scope.get("root_path", "") or "") + get_route_path(request.scope)


def _next_target(request: Request) -> str:
    """Return the relative admin path and query to come back to after login.

    Built on the server from the current request, never from user input, so it
    cannot be turned into an open redirect.
    """
    target = _browser_path(request)
    query = request.scope.get("query_string", b"").decode("latin-1")
    return f"{target}?{query}" if query else target


def _is_api_path(request: Request, api_prefixes: Sequence[str]) -> bool:
    relative = _browser_path(request).removeprefix(admin_base_path(request))
    return relative.startswith(tuple(api_prefixes))


def make_admin_route_class(  # noqa: PLR0913 - ExternalAuth settings; all but templates are keyword-only
    templates: Jinja2Templates | None = None,
    *,
    login_url: str | None = None,
    next_param: str = "next",
    token_cookie: str | None = None,
    token_scheme: str = "Bearer",  # noqa: S107 - an auth scheme name, not a secret
    api_prefixes: Sequence[str] = DEFAULT_API_PREFIXES,
    csrf: RouteCsrfCheck | None = None,
    translate_auth_errors: bool = False,
) -> type[APIRoute]:
    """Build the ``HyperAdminRoute`` class for one admin.

    Args:
        templates: The admin's templates. When set, a 403/404/409 ``HTTPException``
            a view raises is rendered inside the admin layout for people
            (``views/error_pages.py``); JSON stays for API callers.
        login_url: ``ExternalAuth.login_url``. Anonymous browsers are sent there
            with ``next_param=<admin path+query>``; without it they get a 401
            "Sign in to the host application" page.
        next_param: ``ExternalAuth.next_param``.
        token_cookie: ``TokenCookie.name`` when the token handoff is enabled;
            ``None`` disables the cookie bridge.
        token_scheme: ``TokenCookie.scheme``, the ``Authorization`` scheme the
            bridged header carries.
        api_prefixes: Admin-relative path prefixes whose auth errors are a bare
            401/403.
        csrf: The CSRF check, run after auth and before the handler. Required
            when ``token_cookie`` is set.
        translate_auth_errors: Map a 401/403 ``HTTPException`` raised while
            dependencies are solved to the B.2 auth responses. Only
            ``ExternalAuth`` mode turns this on: in built-in mode auth redirects
            stay in ``AuthenticationMiddleware``, and a host app-level
            dependency's own 401/403 (e.g. ``HTTPBasic``) must pass through.

    Raises:
        ValueError: ``token_cookie`` is set without a ``csrf`` check. A bridged
            cookie is ambient credentials a cross-site form could ride.
    """
    api_prefixes = tuple(api_prefixes)
    if token_cookie is not None and csrf is None:
        msg = "token_cookie requires a csrf check: a bridged cookie is ambient credentials"
        raise ValueError(msg)

    async def after_dependencies(request: Request) -> None:
        """Mark the end of dependency solving, then run the CSRF check (step 3)."""
        request.scope[_PHASE_KEY] = _PHASE_ENDPOINT
        if csrf is not None:
            failure = await csrf.verify(request)
            if failure is not None:
                raise _CsrfRejected(failure)

    marker = Depends(after_dependencies)

    def login_target(request: Request) -> str | None:
        if login_url is None:
            return None
        separator = "&" if "?" in login_url else "?"
        return f"{login_url}{separator}{urlencode({next_param: _next_target(request)})}"

    def authentication_required(request: Request, *, bridged: bool) -> Response:
        target = login_target(request)
        response: Response
        if _is_api_path(request, api_prefixes):
            response = PlainTextResponse("Authentication required", status_code=401)
        elif request.headers.get("hx-request"):
            response = Response(status_code=401)
            if target is None:
                response.headers["HX-Refresh"] = "true"
            else:
                response.headers["HX-Redirect"] = target
        elif target is None:
            response = HTMLResponse(_SIGN_IN_PAGE, status_code=401)
        else:
            response = RedirectResponse(target, status_code=303)
        if bridged:
            # The host rejected the cookie's token: drop it so it cannot loop.
            response.delete_cookie(token_cookie or "", path=admin_base_path(request) or "/")
        return response

    def access_denied(request: Request) -> Response:
        if _is_api_path(request, api_prefixes) or request.headers.get("hx-request"):
            return PlainTextResponse("Admin access denied", status_code=403)
        return HTMLResponse(_ACCESS_DENIED_PAGE, status_code=403)

    class HyperAdminRoute(APIRoute):
        def __init__(
            self,
            path: str,
            endpoint: Callable[..., Any],
            *,
            dependencies: Sequence[params.Depends] | None = None,
            **kwargs: Any,
        ) -> None:
            # The marker runs last, after every route and router dependency
            # (the admin principal included). include_router may rebuild the
            # route from its own dependencies, so keep exactly one, at the end.
            own = [dep for dep in dependencies or () if dep.dependency is not after_dependencies]
            super().__init__(path, endpoint, dependencies=[*own, marker], **kwargs)

        def get_route_handler(self) -> Callable[[Request], Coroutine[Any, Any, Response]]:
            handler = super().get_route_handler()

            async def route_handler(request: Request) -> Response:
                bridged = _bridge_token_cookie(request, token_cookie, token_scheme)
                request.scope[_PHASE_KEY] = _PHASE_DEPENDENCIES
                try:
                    response = await handler(request)
                except _CsrfRejected as exc:
                    return exc.response
                except AdminAuthenticationRequired:
                    return authentication_required(request, bridged=bridged)
                except AdminAccessDenied:
                    return access_denied(request)
                except StarletteHTTPException as exc:
                    if (
                        translate_auth_errors
                        and request.scope.get(_PHASE_KEY) == _PHASE_DEPENDENCIES
                    ):
                        if exc.status_code == 401:  # noqa: PLR2004
                            return authentication_required(request, bridged=bridged)
                        if exc.status_code == 403:  # noqa: PLR2004
                            return access_denied(request)
                    if (
                        templates is None
                        or exc.status_code not in HTML_ERROR_STATUSES
                        or not wants_html(request)
                    ):
                        raise
                    return render_error(templates, request, exc)
                if csrf is not None:
                    csrf.attach(request, response)
                return response

            return route_handler

    return HyperAdminRoute
