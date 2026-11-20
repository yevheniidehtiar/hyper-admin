"""Attach OAuth sign-in to an ``Admin`` (``docs/specs/oauth-sso.md``).

``core/app.py`` calls these functions only when ``Admin(oauth_backend=...)`` was
given, so an admin without OAuth imports nothing from this package.
"""

from __future__ import annotations

from typing import Any

# Imported at runtime: FastAPI resolves the handlers' ``Request`` annotations from here.
from starlette.requests import Request  # noqa: TC002

from hyperadmin.auth.exceptions import OAuthConfigError
from hyperadmin.auth.oauth.refresh import OAuthRefreshMiddleware
from hyperadmin.auth.oauth.session import pop_flash
from hyperadmin.auth.oauth.tokens import TOKEN_SECRET_ENV, configure_token_cipher
from hyperadmin.auth.oauth.views import CALLBACK_ROUTE, OAuthViews
from hyperadmin.core.rate_limit import InMemoryRateLimiter
from hyperadmin.views.urls import request_admin_path

#: Admin paths the OAuth sign-in needs open to signed-out visitors.
PUBLIC_PATHS: tuple[str, ...] = ("/oauth/authorize/", "/oauth/callback/")


def configure(admin: Any, backend: Any) -> None:
    """Validate ``Admin(oauth_backend=...)`` and bind the backend to the admin.

    Called from ``Admin.__init__``, so a misconfiguration stops the application at
    start-up.

    Raises:
        OAuthConfigError: OAuth is combined with ``auth=``, has no ``auth_backend=``
            to issue sessions, or no token encryption key is configured.
    """
    if admin.auth is not None:
        msg = (
            "Admin(oauth_backend=...) and Admin(auth=...) are mutually exclusive: with "
            "bring-your-own-auth the host application owns sign-in, including OAuth."
        )
        raise OAuthConfigError(msg)
    if admin.auth_backend is None:
        msg = (
            "Admin(oauth_backend=...) needs Admin(auth_backend=...): OAuth signs built-in "
            "users in, and the auth backend issues their session."
        )
        raise OAuthConfigError(msg)
    secret = admin.settings.oauth_token_secret
    if secret is None or not secret.get_secret_value().strip():
        msg = (
            f"Admin(oauth_backend=...) needs a token encryption key: set {TOKEN_SECRET_ENV} "
            "(or HyperAdminSettings(oauth_token_secret=...)) to a Fernet key."
        )
        raise OAuthConfigError(msg)
    configure_token_cipher(secret.get_secret_value())
    backend.bind(engine=admin.engine, session_factory=admin.session_factory)


def register_routes(admin: Any, path: str) -> None:
    """Register the authorize, callback, link, unlink and settings routes."""
    admin_prefix = path.rstrip("/")
    settings = admin.settings
    requests, window = settings.oauth_callback_rate_limit
    views = OAuthViews(
        backend=admin.oauth_backend,
        auth_backend=admin.auth_backend,
        templates=admin.templates,
        otp_service=admin.otp_service,
        state_ttl=settings.oauth_state_ttl_seconds,
        login_redirect=settings.oauth_login_redirect,
        callback_limiter=InMemoryRateLimiter(requests, window),
    )

    # Redirects use the per-request admin path (SDD C.1), as the login routes do.
    async def authorize_get(request: Request, provider: str):
        return await views.authorize(request, provider)

    async def callback_get(request: Request, provider: str):
        return await views.callback(request, provider, request_admin_path(request, admin_prefix))

    async def settings_get(request: Request):
        return await views.settings(request, request_admin_path(request, admin_prefix))

    async def link_get(request: Request, provider: str):
        return await views.link(request, provider, request_admin_path(request, admin_prefix))

    async def unlink_post(request: Request, provider: str):
        return await views.unlink(request, provider, request_admin_path(request, admin_prefix))

    router = admin.router
    router.add_api_route(
        "/oauth/authorize/{provider}",
        authorize_get,
        methods=["GET"],
        name="admin-oauth-authorize",
    )
    router.add_api_route(
        "/oauth/callback/{provider}", callback_get, methods=["GET"], name=CALLBACK_ROUTE
    )
    router.add_api_route(
        "/oauth/settings", settings_get, methods=["GET"], name="admin-oauth-settings"
    )
    router.add_api_route(
        "/oauth/link/{provider}", link_get, methods=["GET"], name="admin-oauth-link"
    )
    router.add_api_route(
        "/oauth/unlink/{provider}", unlink_post, methods=["POST"], name="admin-oauth-unlink"
    )
    # The login page shows the one-shot message the refresh middleware leaves,
    # and one "Sign in with ..." button per configured provider.
    admin.templates.env.globals["oauth_flash"] = pop_flash
    admin.templates.env.globals["oauth_providers"] = [
        {"name": config.name, "label": config.label, "icon": config.button_icon}
        for config in admin.oauth_backend.providers.values()
    ]


def add_refresh_middleware(admin: Any, target: Any) -> None:
    """Add the token refresh middleware to ``target``.

    Call it after the authentication middleware and before the session middleware
    are added (``add_middleware`` prepends), so it runs between the two.
    """
    target.add_middleware(
        OAuthRefreshMiddleware,
        backend=admin.oauth_backend,
        leeway_seconds=admin.settings.oauth_refresh_leeway_seconds,
    )


__all__ = ["PUBLIC_PATHS", "add_refresh_middleware", "configure", "register_routes"]
