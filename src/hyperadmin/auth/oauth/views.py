"""Route handlers of the OAuth sign-in (``docs/specs/oauth-sso.md``).

``authorize`` sends the browser to the provider with a single-use ``state`` and a
PKCE verifier kept in the session; ``callback`` validates the state, exchanges the
code and signs the user in through the ``auth_backend`` the ``Admin`` was built
with, so an OAuth session is an ordinary admin session (and still goes through the
MFA challenge). ``link`` / ``unlink`` / ``settings`` manage the identities of the
signed-in user.
"""

from __future__ import annotations

import hmac
import logging
import secrets
import time
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from fastapi import HTTPException
from starlette.responses import PlainTextResponse, RedirectResponse

from hyperadmin.auth.exceptions import (
    AccountDisabledError,
    AccountLinkRequiredError,
    HyperAdminAuthError,
    LastSignInMethodError,
    OAuthProviderError,
    OAuthSignupDisabledError,
    OAuthStateError,
)
from hyperadmin.auth.oauth.session import (
    OAUTH_FLOW_KEY,
    OAUTH_SESSION_KEY,
    mark_oauth_session,
    pop_flash,
    read_oauth_session,
    set_flash,
)
from hyperadmin.auth.otp import PARTIAL_AUTH_SESSION_KEY, RateLimitError
from hyperadmin.i18n import gettext as _
from hyperadmin.views.urls import admin_url_for

if TYPE_CHECKING:
    from collections.abc import Callable

    from fastapi.templating import Jinja2Templates
    from starlette.requests import Request
    from starlette.responses import Response

    from hyperadmin.auth.oauth.backend import OAuthBackend
    from hyperadmin.auth.oauth.providers import OAuthProviderConfig
    from hyperadmin.core.rate_limit import RateLimiter

logger = logging.getLogger("hyperadmin")

#: Route name of the callback; the redirect URI is resolved from it.
CALLBACK_ROUTE = "admin-oauth-callback"

_BAD_REQUEST = 400
_FORBIDDEN = 403
_CONFLICT = 409
_BAD_GATEWAY = 502


def _failure(exc: HyperAdminAuthError) -> tuple[int, str]:
    """Return the status code and the user-facing message of a failed sign-in."""
    if isinstance(exc, OAuthProviderError):
        return (_BAD_GATEWAY if exc.transient else _BAD_REQUEST), exc.detail
    if isinstance(exc, AccountLinkRequiredError):
        return _CONFLICT, _("Account exists. Sign in with your password and link from settings.")
    if isinstance(exc, OAuthSignupDisabledError):
        return _FORBIDDEN, _("No account is linked to this sign-in. Ask an administrator.")
    if isinstance(exc, AccountDisabledError):
        return _FORBIDDEN, _("This account is disabled.")
    return _BAD_REQUEST, _("This sign-in request is invalid or has expired. Please try again.")


@dataclass(frozen=True, slots=True)
class OAuthViews:
    """The OAuth handlers, bound to their collaborators.

    Attributes:
        backend: The configured :class:`~hyperadmin.auth.oauth.backend.OAuthBackend`.
        auth_backend: The admin's ``AuthBackend``; it issues the session.
        templates: The admin's templates.
        otp_service: The MFA service, or ``None`` when MFA is not configured.
        state_ttl: Seconds a sign-in may take between authorize and callback.
        login_redirect: Where a completed sign-in lands; ``None`` is the admin index.
        callback_limiter: Per-client limit on callback requests, or ``None``.
        clock: Wall clock in epoch seconds (injectable for tests).
    """

    backend: OAuthBackend
    auth_backend: Any
    templates: Jinja2Templates
    otp_service: Any = None
    state_ttl: int = 600
    login_redirect: str | None = None
    callback_limiter: RateLimiter | None = None
    clock: Callable[[], float] = time.time

    # ── Authorize ─────────────────────────────────────────────────────────

    async def authorize(self, request: Request, provider: str) -> Response:
        """``GET /oauth/authorize/{provider}``: start a sign-in at the provider."""
        return await self._start(request, self._provider_or_404(provider), link_user_id=None)

    async def link(self, request: Request, provider: str, admin_path: str) -> Response:
        """``GET /oauth/link/{provider}``: start linking a provider to the signed-in user."""
        config = self._provider_or_404(provider)
        user_id = getattr(getattr(request.state, "user", None), "id", None)
        if user_id is None:
            return RedirectResponse(url=f"{admin_path}/login", status_code=302)
        return await self._start(request, config, link_user_id=user_id)

    async def _start(
        self, request: Request, config: OAuthProviderConfig, *, link_user_id: int | None
    ) -> Response:
        state = secrets.token_urlsafe(32)
        code_verifier = secrets.token_urlsafe(64)
        redirect_uri = config.redirect_uri or str(
            admin_url_for(request, CALLBACK_ROUTE, provider=config.name)
        )
        request.session[OAUTH_FLOW_KEY] = {
            "provider": config.name,
            "state": state,
            "verifier": code_verifier,
            "redirect_uri": redirect_uri,
            "issued_at": self.clock(),
            "link_user_id": link_user_id,
        }
        url = await self.backend.authorization_url(config.name, redirect_uri, state, code_verifier)
        return RedirectResponse(url=url, status_code=302)

    # ── Callback ──────────────────────────────────────────────────────────

    async def callback(self, request: Request, provider: str, admin_path: str) -> Response:
        """``GET /oauth/callback/{provider}``: finish the sign-in or the link."""
        limited = await self._rate_limited(request)
        if limited is not None:
            return limited
        self._provider_or_404(provider)
        # Single use: the stored state is gone whatever happens next.
        flow = request.session.pop(OAUTH_FLOW_KEY, None)
        linking = isinstance(flow, dict) and flow.get("link_user_id") is not None
        try:
            checked = self._checked_flow(request, provider, flow)
            code = request.query_params.get("code")
            if not code:
                raise OAuthStateError("Authorization code missing")
            token = await self.backend.exchange_code(
                provider, code, checked["redirect_uri"], checked["verifier"]
            )
            userinfo = await self.backend.get_userinfo(provider, token["access_token"])
            if linking:
                return await self._finish_link(request, checked, userinfo, token, admin_path)
            user = await self.backend.provision_user(provider, userinfo, token)
        except HyperAdminAuthError as exc:
            status, message = _failure(exc)
            logger.warning("OAuth sign-in with %s failed (%d): %s", provider, status, exc)
            if linking:
                set_flash(request.session, message, "error")
                return RedirectResponse(url=f"{admin_path}/oauth/settings", status_code=302)
            return self._login_page(request, admin_path, message, status)
        return await self._finish_login(request, user, provider, token, admin_path)

    def _checked_flow(self, request: Request, provider: str, flow: Any) -> dict[str, Any]:
        """Validate the provider answer against the stored flow, or raise."""
        params = request.query_params
        error = params.get("error")
        if error:
            raise OAuthProviderError(provider, "OAuth provider denied access", error_code=error)
        if not isinstance(flow, dict) or flow.get("provider") != provider:
            raise OAuthStateError("No sign-in in progress for this provider")
        expected, received = str(flow.get("state") or ""), params.get("state") or ""
        if not expected or not hmac.compare_digest(expected.encode(), received.encode()):
            raise OAuthStateError("State mismatch")
        issued_at = flow.get("issued_at")
        if not isinstance(issued_at, (int, float)) or self.clock() - issued_at > self.state_ttl:
            raise OAuthStateError("State expired")
        return flow

    async def _finish_link(
        self,
        request: Request,
        flow: dict[str, Any],
        userinfo: dict[str, Any],
        token: dict[str, Any],
        admin_path: str,
    ) -> Response:
        """Attach the identity to the user who started the link flow."""
        provider = flow["provider"]
        user = await self.auth_backend.get_current_user(request)
        if user is None or user.id != flow["link_user_id"]:
            raise OAuthStateError("The user who started the link is no longer signed in")
        await self.backend.link_identity(provider, user.id, userinfo, token)
        label = self.backend.providers[provider].label
        set_flash(request.session, _("%(provider)s account linked.") % {"provider": label})
        return RedirectResponse(url=f"{admin_path}/oauth/settings", status_code=302)

    async def _finish_login(
        self, request: Request, user: Any, provider: str, token: dict[str, Any], admin_path: str
    ) -> Response:
        """Issue the session, or hand over to the MFA challenge first."""
        expires_at = token.get("expires_at")
        if user.mfa_enabled and self.otp_service is not None:
            # Same partial-auth state as the password login (auth/views.py): the
            # full session is granted by the MFA verify step, which keeps the marker.
            request.session[PARTIAL_AUTH_SESSION_KEY] = {"stage": "mfa_pending", "user_id": user.id}
            mark_oauth_session(
                request.session, user_id=user.id, provider=provider, expires_at=expires_at
            )
            try:
                await self.otp_service.generate_and_send(user, request.session)
            except RateLimitError:
                logger.info("OAuth sign-in: OTP rate limit hit for user %s", user.id)
            except Exception:
                logger.exception("OAuth sign-in: could not send the verification code")
                request.session.pop(PARTIAL_AUTH_SESSION_KEY, None)
                request.session.pop(OAUTH_SESSION_KEY, None)
                message = _("Could not send verification code. Please try again.")
                return self._login_page(request, admin_path, message, _BAD_GATEWAY)
            return RedirectResponse(url=f"{admin_path}/mfa/challenge", status_code=302)
        await self.auth_backend.login(request, user)
        mark_oauth_session(
            request.session, user_id=user.id, provider=provider, expires_at=expires_at
        )
        return RedirectResponse(url=self.login_redirect or f"{admin_path}/", status_code=302)

    # ── Settings ──────────────────────────────────────────────────────────

    async def settings(
        self, request: Request, admin_path: str, *, error: str | None = None, status_code: int = 200
    ) -> Response:
        """``GET /oauth/settings``: the signed-in user's linked providers."""
        user = getattr(request.state, "user", None)
        user_id = getattr(user, "id", None)
        if user_id is None:
            return RedirectResponse(url=f"{admin_path}/login", status_code=302)
        linked = await self.backend.linked_providers(user_id)
        flash = pop_flash(request)
        if flash is not None and flash["level"] == "error":
            error, flash = error or flash["message"], None
        context = {
            "request": request,
            "admin_prefix": admin_path,
            "identities": [
                {"name": config.name, "label": config.label, "linked": config.name in linked}
                for config in self.backend.providers.values()
            ],
            "error": error,
            "flash": flash["message"] if flash is not None else None,
        }
        return self.templates.TemplateResponse(
            request, "auth/oauth_settings.html", context, status_code=status_code
        )

    async def unlink(self, request: Request, provider: str, admin_path: str) -> Response:
        """``POST /oauth/unlink/{provider}``: remove a linked provider."""
        config = self._provider_or_404(provider)
        user_id = getattr(getattr(request.state, "user", None), "id", None)
        if user_id is None:
            return RedirectResponse(url=f"{admin_path}/login", status_code=302)
        try:
            removed = await self.backend.unlink_identity(provider, user_id)
        except LastSignInMethodError:
            message = _("Set a password before unlinking your only sign-in method")
            return await self.settings(request, admin_path, error=message, status_code=_BAD_REQUEST)
        if not removed:
            raise HTTPException(status_code=404, detail="Provider is not linked")
        marker = read_oauth_session(request.session, user_id=user_id)
        if marker is not None and marker["provider"] == provider:
            request.session.pop(OAUTH_SESSION_KEY, None)
        set_flash(request.session, _("%(provider)s account unlinked.") % {"provider": config.label})
        return RedirectResponse(url=f"{admin_path}/oauth/settings", status_code=303)

    # ── Helpers ───────────────────────────────────────────────────────────

    def _provider_or_404(self, provider: str) -> OAuthProviderConfig:
        config = self.backend.provider(provider)
        if config is None:
            raise HTTPException(status_code=404, detail="Unknown OAuth provider")
        return config

    async def _rate_limited(self, request: Request) -> Response | None:
        if self.callback_limiter is None:
            return None
        client = request.client
        decision = await self.callback_limiter.acquire(client.host if client else "unknown")
        if decision.allowed:
            return None
        return PlainTextResponse(
            "Too many requests. Try again later.",
            status_code=429,
            headers={"Retry-After": str(decision.retry_after)},
        )

    def _login_page(self, request: Request, admin_path: str, error: str, status: int) -> Response:
        """Render the login page with ``error``; the conflict case gets its own page."""
        template = "auth/oauth_link_required.html" if status == _CONFLICT else "login.html"
        context = {"request": request, "error": error, "admin_prefix": admin_path}
        return self.templates.TemplateResponse(request, template, context, status_code=status)


__all__ = ["CALLBACK_ROUTE", "OAuthViews"]
