"""Authentication middleware for HyperAdmin.

Redirects unauthenticated requests to the login page and populates
``request.state.user`` for authenticated requests. Adds a partial-auth
gate (C3-A, #487) that bounces users mid-MFA back to the challenge page
for any admin route other than the MFA endpoints themselves.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.responses import RedirectResponse, Response

from hyperadmin.auth.otp import PARTIAL_AUTH_SESSION_KEY

if TYPE_CHECKING:
    from starlette.requests import Request


class AuthenticationMiddleware(BaseHTTPMiddleware):
    """Starlette middleware that enforces authentication on admin routes."""

    # Paths that don't require authentication (relative to admin prefix)
    PUBLIC_SUFFIXES = ("/login", "/login/")
    # Paths an in-flight MFA user MUST be allowed to reach so they can
    # resolve their partial-auth state. Without this, the gate below
    # would loop the user infinitely on /admin/mfa/challenge.
    MFA_PREFIX = "/mfa/"

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

        # MFA endpoints are reachable in BOTH partial-auth and full-auth states.
        # Partial-auth: the user is resolving the challenge.
        # Full-auth:    the user is managing /mfa/settings.
        # The endpoints themselves enforce the appropriate guard internally.
        on_mfa_route = relative.startswith(self.MFA_PREFIX)

        # Check authentication
        user = await self.auth_backend.get_current_user(request)
        if user is None:
            # Anonymous + partial-auth marker present → redirect to challenge
            # so the user can complete the OTP step. Anonymous + no marker →
            # redirect to login as before. Either way, MFA routes themselves
            # remain reachable so the user has a way out.
            if on_mfa_route:
                return await call_next(request)
            if _has_partial_auth(request):
                challenge_url = f"{self.admin_prefix}/mfa/challenge"
                return RedirectResponse(url=challenge_url, status_code=302)
            login_url = f"{self.admin_prefix}/login"
            return RedirectResponse(url=login_url, status_code=302)

        # Full-auth user — pass through. Defensive: if a partial-auth marker
        # somehow lingers alongside a full session (e.g. cookie tampering),
        # the marker is meaningless and we ignore it; full auth wins.
        request.state.user = user
        return await call_next(request)


def _has_partial_auth(request: Request) -> bool:
    """Return True iff the session carries a well-formed partial-auth marker.

    Mirrors the validation in ``hyperadmin.auth.views._read_partial_auth`` —
    the marker must be a dict with ``stage == "mfa_pending"`` and an integer
    ``user_id``. Anything else (a stale bare-int from earlier drafts, a
    truncated dict from a buggy cookie, etc.) is treated as absent so the
    user is bounced to /login rather than into a broken MFA loop.
    """
    try:
        raw = request.session.get(PARTIAL_AUTH_SESSION_KEY)
    except (AssertionError, AttributeError):
        # SessionMiddleware not installed → session attribute missing.
        return False
    if not isinstance(raw, dict):
        return False
    if raw.get("stage") != "mfa_pending":
        return False
    return isinstance(raw.get("user_id"), int)
