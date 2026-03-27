"""Authentication middleware for HyperAdmin.

Redirects unauthenticated requests to the login page and populates
``request.state.user`` for authenticated requests.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.responses import RedirectResponse, Response

if TYPE_CHECKING:
    from starlette.requests import Request


class AuthenticationMiddleware(BaseHTTPMiddleware):
    """Starlette middleware that enforces authentication on admin routes."""

    # Paths that don't require authentication (relative to admin prefix)
    PUBLIC_SUFFIXES = ("/login", "/login/")

    def __init__(self, app: Any, auth_backend: Any, admin_prefix: str = "/admin") -> None:
        super().__init__(app)
        self.auth_backend = auth_backend
        self.admin_prefix = admin_prefix.rstrip("/")

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        path = request.url.path

        # Only enforce auth on admin routes
        if not path.startswith(self.admin_prefix):
            return await call_next(request)

        # Allow public paths (login page, static assets)
        relative = path[len(self.admin_prefix) :]
        if any(
            relative == suffix or relative.startswith(suffix) for suffix in self.PUBLIC_SUFFIXES
        ):
            request.state.user = None
            return await call_next(request)

        # Allow static assets
        if relative.startswith("/static"):
            return await call_next(request)

        # Check authentication
        user = await self.auth_backend.get_current_user(request)
        if user is None:
            login_url = f"{self.admin_prefix}/login"
            return RedirectResponse(url=login_url, status_code=302)

        request.state.user = user
        return await call_next(request)
