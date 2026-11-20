"""OAuth2/OIDC backend: provider calls, user provisioning and token storage.

:class:`OAuthBackend` holds the configured providers and does everything that is
not HTTP handling of the admin itself: it builds the authorization URL (PKCE
``S256``), exchanges the code, reads userinfo, maps an identity to a ``User`` and
keeps the encrypted tokens fresh. The route handlers live in
``hyperadmin.auth.oauth.views``; the session itself is still issued by the
``auth_backend`` the ``Admin`` was built with. See ``docs/specs/oauth-sso.md``.

Needs ``pip install 'hyper-admin[oauth]'`` (``httpx-oauth``, ``cryptography``).
"""

from __future__ import annotations

import asyncio
import base64
import hashlib
import logging
import re
import weakref
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import TYPE_CHECKING, Any

from sqlalchemy import func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import noload
from sqlmodel import col, select

from hyperadmin.auth.backend import make_unusable_password
from hyperadmin.auth.exceptions import (
    AccountDisabledError,
    AccountLinkRequiredError,
    LastSignInMethodError,
    OAuthConfigError,
    OAuthProviderError,
    OAuthSignupDisabledError,
)
from hyperadmin.auth.models import OAuthToken, User
from hyperadmin.core.adapters import open_session
from hyperadmin.core.timezones import utc_now

if TYPE_CHECKING:
    from collections.abc import Callable, Mapping
    from contextlib import AbstractAsyncContextManager

    from hyperadmin.auth.oauth.providers import OAuthProviderConfig
    from hyperadmin.core.adapters import AsyncSessionLike, SessionFactory

logger = logging.getLogger("hyperadmin")

_INSTALL_HINT = "Install the OAuth extra: pip install 'hyper-admin[oauth]'."
_USERNAME_UNSAFE = re.compile(r"[^A-Za-z0-9._-]")
_USERNAME_MAX = 50
_NAME_MAX = 50
_EMAIL_MAX = 100
_SERVER_ERROR = 500


@dataclass(frozen=True, slots=True)
class OAuthIdentity:
    """Who the provider says signed in.

    Attributes:
        provider: Name of the provider.
        sub: The provider's stable id of the user, as a string.
        email: The user's email address.
        claims: The raw userinfo document.
    """

    provider: str
    sub: str
    email: str
    claims: Mapping[str, Any]


def pkce_challenge(code_verifier: str) -> str:
    """Return the PKCE ``S256`` code challenge of ``code_verifier`` (RFC 7636)."""
    digest = hashlib.sha256(code_verifier.encode("ascii")).digest()
    return base64.urlsafe_b64encode(digest).rstrip(b"=").decode("ascii")


def _build_client(config: OAuthProviderConfig, transport: Any, timeout: float) -> Any:
    """Build the ``httpx-oauth`` client of one provider."""
    try:
        import httpx  # noqa: PLC0415
        from httpx_oauth.oauth2 import BaseOAuth2  # noqa: PLC0415
    except ImportError as exc:
        msg = f"OAuth sign-in needs the 'httpx-oauth' package. {_INSTALL_HINT}"
        raise OAuthConfigError(msg) from exc

    class _Client(BaseOAuth2[dict[str, Any]]):
        def get_httpx_client(self) -> Any:
            return httpx.AsyncClient(transport=transport, timeout=timeout)

    return _Client(
        config.client_id,
        config.client_secret,
        config.authorize_url,
        config.token_url,
        refresh_token_endpoint=config.token_url,
        name=config.name,
        base_scopes=list(config.scopes),
    )


def _error_code(response: Any) -> str | None:
    """Return the OAuth ``error`` code of a provider response, if it carries one."""
    try:
        payload = response.json()
    except ValueError:
        return None
    code = payload.get("error") if isinstance(payload, dict) else None
    return code if isinstance(code, str) else None


def _split_scopes(raw: Any, default: tuple[str, ...]) -> list[str]:
    """Parse a token response ``scope`` (space- or comma-separated) into a list."""
    if isinstance(raw, str) and raw.strip():
        return [scope for scope in re.split(r"[\s,]+", raw.strip()) if scope]
    return list(default)


def _names(claims: Mapping[str, Any]) -> tuple[str, str]:
    """Return ``(first_name, last_name)`` from OIDC name claims, best effort."""
    first, last = claims.get("given_name"), claims.get("family_name")
    if not first and not last and isinstance(claims.get("name"), str):
        first, _, last = claims["name"].strip().partition(" ")
    return str(first or "")[:_NAME_MAX], str(last or "")[:_NAME_MAX]


class OAuthBackend:
    """OAuth2/OIDC sign-in for the built-in users.

    Pass it to ``Admin(oauth_backend=...)`` next to ``auth_backend=``::

        Admin(
            app,
            engine=engine,
            auth_backend=SessionAuthBackend(engine=engine),
            oauth_backend=OAuthBackend(
                providers={"google": google_provider(client_id, client_secret)}
            ),
        )

    Args:
        providers: Provider configurations by name; each key must equal its
            configuration's ``name``.
        session_factory: Session factory to store users and tokens with. When
            neither it nor ``engine`` is given, ``Admin`` binds its own.
        engine: An async SQLAlchemy engine, as an alternative to ``session_factory``.
        tenant_resolver: Maps the value of a provider's ``tenant_id_claim`` to a
            tenant id when a user is created; return ``None`` for "no tenant".
        transport: ``httpx`` transport for every provider call (tests, proxies).
        timeout: Seconds a provider call may take.

    Raises:
        OAuthConfigError: No provider, a key that differs from its provider name,
            or the ``oauth`` extra is not installed.
    """

    def __init__(
        self,
        providers: Mapping[str, OAuthProviderConfig],
        session_factory: SessionFactory | None = None,
        *,
        engine: Any = None,
        tenant_resolver: Callable[[Any], Any] | None = None,
        transport: Any = None,
        timeout: float = 10.0,
    ) -> None:
        if not providers:
            msg = "OAuthBackend needs at least one provider."
            raise OAuthConfigError(msg)
        for key, config in providers.items():
            if key != config.name:
                msg = f"OAuth provider key {key!r} must equal its name {config.name!r}."
                raise OAuthConfigError(msg)
        self.providers: dict[str, OAuthProviderConfig] = dict(providers)
        self.session_factory = session_factory
        self.engine = engine
        self.tenant_resolver = tenant_resolver
        self._clients = {
            name: _build_client(config, transport, timeout)
            for name, config in self.providers.items()
        }
        self._refresh_locks: weakref.WeakValueDictionary[tuple[int, str], asyncio.Lock] = (
            weakref.WeakValueDictionary()
        )

    # ── Wiring ────────────────────────────────────────────────────────────

    def bind(self, *, engine: Any = None, session_factory: SessionFactory | None = None) -> None:
        """Use ``engine`` / ``session_factory`` unless the backend already has its own."""
        if self.engine is None and self.session_factory is None:
            self.engine = engine
            self.session_factory = session_factory

    def provider(self, name: str) -> OAuthProviderConfig | None:
        """Return the provider configured as ``name``, or ``None``."""
        return self.providers.get(name)

    def _config(self, name: str) -> OAuthProviderConfig:
        config = self.providers.get(name)
        if config is None:
            msg = f"OAuth provider {name!r} is not configured."
            raise OAuthConfigError(msg)
        return config

    def _session(self) -> AbstractAsyncContextManager[AsyncSessionLike]:
        if self.engine is None and self.session_factory is None:
            msg = (
                "OAuthBackend has no database: pass engine= or session_factory=, or hand "
                "it to Admin(oauth_backend=...)."
            )
            raise OAuthConfigError(msg)
        return open_session(self.engine, self.session_factory)

    # ── Provider calls ────────────────────────────────────────────────────

    async def authorization_url(
        self, provider: str, redirect_uri: str, state: str, code_verifier: str
    ) -> str:
        """Return the provider URL the browser is sent to, with ``state`` and PKCE."""
        config = self._config(provider)
        return await self._clients[provider].get_authorization_url(
            redirect_uri,
            state=state,
            code_challenge=pkce_challenge(code_verifier),
            code_challenge_method="S256",
            extras_params=dict(config.authorize_params) or None,
        )

    async def exchange_code(
        self, provider: str, code: str, redirect_uri: str, code_verifier: str | None = None
    ) -> dict[str, Any]:
        """Exchange an authorization ``code`` for tokens.

        Returns:
            The token response: ``access_token``, and when the provider sends them
            ``refresh_token``, ``expires_at`` (epoch seconds) and ``scope``.

        Raises:
            OAuthProviderError: The provider rejected the code or was unreachable.
        """
        self._config(provider)
        from httpx_oauth.oauth2 import GetAccessTokenError  # noqa: PLC0415

        try:
            token = await self._clients[provider].get_access_token(
                code, redirect_uri, code_verifier
            )
        except GetAccessTokenError as exc:
            raise self._request_error(provider, "Token exchange failed", exc) from exc
        return self._checked_token(provider, token, "Token exchange failed")

    async def get_userinfo(self, provider: str, access_token: str) -> dict[str, Any]:
        """Return the provider's profile of the token's user.

        When the profile has no email and the provider has an ``emails_url``
        (GitHub), the primary verified address is looked up and added.

        Raises:
            OAuthProviderError: The provider refused the token or was unreachable.
        """
        config = self._config(provider)
        claims = await self._get_json(provider, config.userinfo_url, access_token)
        if not isinstance(claims, dict):
            raise OAuthProviderError(provider, "Userinfo is not a JSON object")
        if not claims.get(config.email_claim) and config.emails_url:
            emails = await self._get_json(provider, config.emails_url, access_token)
            email = _primary_email(emails)
            if email:
                claims[config.email_claim] = email
        return claims

    async def _get_json(self, provider: str, url: str, access_token: str) -> Any:
        import httpx  # noqa: PLC0415

        headers = {"Authorization": f"Bearer {access_token}", "Accept": "application/json"}
        try:
            async with self._clients[provider].get_httpx_client() as http:
                response = await http.get(url, headers=headers)
        except httpx.HTTPError as exc:
            detail = "Userinfo request failed: provider unreachable"
            raise OAuthProviderError(provider, detail, transient=True) from exc
        if response.is_error:
            raise OAuthProviderError(
                provider,
                f"Userinfo request failed (HTTP {response.status_code})",
                error_code=_error_code(response),
                transient=response.status_code >= _SERVER_ERROR,
            )
        try:
            return response.json()
        except ValueError as exc:
            raise OAuthProviderError(provider, "Userinfo is not valid JSON") from exc

    @staticmethod
    def _request_error(provider: str, what: str, exc: Any) -> OAuthProviderError:
        """Turn an ``httpx-oauth`` request error into an :class:`OAuthProviderError`."""
        response = getattr(exc, "response", None)
        if response is None:
            return OAuthProviderError(provider, f"{what}: provider unreachable", transient=True)
        code = _error_code(response)
        detail = f"{what} (HTTP {response.status_code}{f', {code}' if code else ''})"
        return OAuthProviderError(
            provider,
            detail,
            error_code=code,
            transient=response.status_code >= _SERVER_ERROR,
        )

    @staticmethod
    def _checked_token(provider: str, token: Mapping[str, Any], what: str) -> dict[str, Any]:
        """Reject a 200 answer that is an error document (GitHub) or has no access token."""
        error = token.get("error")
        if error or not token.get("access_token"):
            code = error if isinstance(error, str) else None
            detail = f"{what} ({code})" if code else f"{what}: no access token returned"
            raise OAuthProviderError(provider, detail, error_code=code)
        return dict(token)

    # ── Identity ──────────────────────────────────────────────────────────

    def identity(self, provider: str, userinfo: Mapping[str, Any]) -> OAuthIdentity:
        """Validate ``userinfo`` and return the identity it describes.

        Raises:
            OAuthProviderError: No stable id, no usable email, an unverified
                email or a ``required_claims`` mismatch.
        """
        config = self._config(provider)
        sub = userinfo.get(config.sub_claim)
        if sub is None or sub == "":
            raise OAuthProviderError(provider, f"Userinfo has no {config.sub_claim!r} claim")
        email = userinfo.get(config.email_claim)
        if not isinstance(email, str) or "@" not in email or len(email) > _EMAIL_MAX:
            raise OAuthProviderError(provider, "Email required")
        if userinfo.get("email_verified") in (False, "false"):
            raise OAuthProviderError(provider, "Email address is not verified")
        for claim, expected in config.required_claims:
            if userinfo.get(claim) != expected:
                raise OAuthProviderError(provider, f"Account is not allowed ({claim} mismatch)")
        return OAuthIdentity(provider, str(sub), email.strip(), userinfo)

    # ── Users and tokens ──────────────────────────────────────────────────

    async def provision_user(
        self, provider: str, userinfo: Mapping[str, Any], token: Mapping[str, Any]
    ) -> User:
        """Return the user of this identity, creating it on the first sign-in.

        A known ``(provider, sub)`` returns its user and stores the new tokens.
        An unknown identity creates a user with no usable password, unless its
        email already belongs to a user: accounts are never linked by email.

        Raises:
            AccountLinkRequiredError: The email belongs to an existing user.
            AccountDisabledError: The identity's user is not active.
            OAuthSignupDisabledError: Unknown identity and ``allow_signup=False``.
            OAuthProviderError: ``userinfo`` is unusable (see :meth:`identity`).
        """
        identity = self.identity(provider, userinfo)
        try:
            return await self._provision(identity, token)
        except IntegrityError:
            # A concurrent callback of the same identity created the rows first:
            # this one is now a returning sign-in (or an email conflict).
            return await self._provision(identity, token)

    async def _provision(self, identity: OAuthIdentity, token: Mapping[str, Any]) -> User:
        config = self._config(identity.provider)
        async with self._session() as session:
            row = await self._row_by_sub(session, identity)
            if row is not None:
                user = await session.get(User, row.user_id)
                if user is None or not user.is_active:
                    raise AccountDisabledError(identity.email)
                self._store_token(row, config, token)
                session.add(row)
                await session.commit()
                await session.refresh(user)
                return user
            taken = select(User.id).where(func.lower(User.email) == identity.email.lower())
            if (await session.execute(taken)).first() is not None:
                raise AccountLinkRequiredError(identity.provider, identity.email)
            if not config.allow_signup:
                raise OAuthSignupDisabledError(identity.provider)
            first_name, last_name = _names(identity.claims)
            user = User(
                username=await self._free_username(session, identity.email),
                email=identity.email,
                password_hash=make_unusable_password(),
                first_name=first_name,
                last_name=last_name,
            )
            self._apply_tenant(user, config, identity.claims)
            row = OAuthToken(provider=identity.provider, sub=identity.sub, user=user)
            self._store_token(row, config, token)
            session.add_all([user, row])
            await session.commit()
            await session.refresh(user)
            return user

    async def link_identity(
        self, provider: str, user_id: int, userinfo: Mapping[str, Any], token: Mapping[str, Any]
    ) -> None:
        """Link this identity to the signed-in user ``user_id`` and store its tokens.

        A provider the user linked before is re-pointed to the new identity.

        Raises:
            AccountLinkRequiredError: The identity is linked to another user.
            OAuthProviderError: ``userinfo`` is unusable (see :meth:`identity`).
        """
        identity = self.identity(provider, userinfo)
        config = self._config(provider)
        async with self._session() as session:
            row = await self._row_by_sub(session, identity)
            if row is not None and row.user_id != user_id:
                raise AccountLinkRequiredError(provider, identity.email)
            if row is None:
                row = await self._row_by_user(session, user_id, provider)
            if row is None:
                row = OAuthToken(user_id=user_id, provider=provider, sub=identity.sub)
            row.sub = identity.sub
            self._store_token(row, config, token)
            session.add(row)
            await session.commit()

    async def unlink_identity(self, provider: str, user_id: int) -> bool:
        """Delete the user's link to ``provider``; ``False`` when there was none.

        Raises:
            LastSignInMethodError: The user has no usable password and no other
                linked provider.
        """
        async with self._session() as session:
            stmt = select(OAuthToken).where(OAuthToken.user_id == user_id).options(_NO_USER)
            rows = list((await session.execute(stmt)).scalars())
            row = next((candidate for candidate in rows if candidate.provider == provider), None)
            if row is None:
                return False
            user = await session.get(User, user_id)
            if len(rows) == 1 and (user is None or user.oauth_only):
                raise LastSignInMethodError(provider)
            await session.delete(row)
            await session.commit()
            return True

    async def linked_providers(self, user_id: int) -> set[str]:
        """Return the names of the providers ``user_id`` has linked."""
        async with self._session() as session:
            stmt = select(OAuthToken.provider).where(OAuthToken.user_id == user_id)
            return set((await session.execute(stmt)).scalars())

    async def refresh_token(self, provider: str, user_id: int, *, leeway: float) -> float | None:
        """Make sure the user's access token outlives ``leeway`` seconds.

        Asks the provider for a new access token when the stored one expires within
        ``leeway`` seconds. Concurrent calls for one user and provider run one after
        another, so a rotating refresh token is used once.

        Returns:
            The expiry of the (possibly new) access token as epoch seconds, or
            ``None`` when there is nothing to refresh: no link, no expiry or no
            refresh token.

        Raises:
            OAuthProviderError: The refresh failed. ``transient`` tells a network
                or server failure from a refusal (a revoked refresh token).
        """
        config = self._config(provider)
        key = (user_id, provider)
        lock = self._refresh_locks.get(key)
        if lock is None:
            lock = self._refresh_locks[key] = asyncio.Lock()
        async with lock, self._session() as session:
            row = await self._row_by_user(session, user_id, provider)
            if row is None or row.expires_at is None:
                return None
            if row.expires_at - utc_now() > timedelta(seconds=leeway):
                return _epoch(row.expires_at)
            try:
                refresh_token = row.refresh_token
            except OAuthConfigError as exc:
                raise OAuthProviderError(provider, "Stored token cannot be decrypted") from exc
            if refresh_token is None:
                return None
            token = await self._request_refresh(provider, refresh_token)
            self._store_token(row, config, token)
            session.add(row)
            await session.commit()
            return token.get("expires_at")

    async def _request_refresh(self, provider: str, refresh_token: str) -> dict[str, Any]:
        from httpx_oauth.oauth2 import RefreshTokenError  # noqa: PLC0415

        try:
            token = await self._clients[provider].refresh_token(refresh_token)
        except RefreshTokenError as exc:
            raise self._request_error(provider, "Token refresh failed", exc) from exc
        return self._checked_token(provider, token, "Token refresh failed")

    # ── Helpers ───────────────────────────────────────────────────────────

    @staticmethod
    async def _row_by_sub(session: AsyncSessionLike, identity: OAuthIdentity) -> OAuthToken | None:
        stmt = (
            select(OAuthToken)
            .where(OAuthToken.provider == identity.provider, OAuthToken.sub == identity.sub)
            .options(_NO_USER)
        )
        return (await session.execute(stmt)).scalar_one_or_none()

    @staticmethod
    async def _row_by_user(
        session: AsyncSessionLike, user_id: int, provider: str
    ) -> OAuthToken | None:
        stmt = (
            select(OAuthToken)
            .where(OAuthToken.user_id == user_id, OAuthToken.provider == provider)
            .options(_NO_USER)
        )
        return (await session.execute(stmt)).scalar_one_or_none()

    @staticmethod
    def _store_token(
        row: OAuthToken, config: OAuthProviderConfig, token: Mapping[str, Any]
    ) -> None:
        """Copy a token response onto ``row`` (encrypting the tokens)."""
        row.access_token = str(token["access_token"])
        # Providers send a refresh token on the first consent only (Google) or on
        # every refresh (rotation); without a new one the stored one stays valid.
        if token.get("refresh_token"):
            row.refresh_token = str(token["refresh_token"])
        expires_at = token.get("expires_at")
        row.expires_at = (
            datetime.fromtimestamp(float(expires_at), tz=timezone.utc)
            if expires_at is not None
            else None
        )
        row.scopes = _split_scopes(token.get("scope"), config.scopes)
        row.updated_at = utc_now()

    @staticmethod
    async def _free_username(session: AsyncSessionLike, email: str) -> str:
        """Derive a unique username from the email's local part."""
        base = _USERNAME_UNSAFE.sub("", email.partition("@")[0])[: _USERNAME_MAX - 10] or "user"
        stmt = select(User.username).where(col(User.username).startswith(base, autoescape=True))
        taken = set((await session.execute(stmt)).scalars())
        candidate, suffix = base, 1
        while candidate in taken:
            suffix += 1
            candidate = f"{base}-{suffix}"
        return candidate

    def _apply_tenant(
        self, user: Any, config: OAuthProviderConfig, claims: Mapping[str, Any]
    ) -> None:
        """Set ``user.tenant_id`` from the provider's tenant claim, when one maps.

        The built-in ``User`` has no ``tenant_id`` column before multi-tenancy
        (v0.5.3); the resolved value is then only logged.
        """
        if config.tenant_id_claim is None:
            return
        value = claims.get(config.tenant_id_claim)
        resolver = self.tenant_resolver
        tenant_id = resolver(value) if resolver is not None and value is not None else None
        if tenant_id is None:
            logger.info(
                "OAuth provider %s: no tenant for claim %s=%r; the new user has no tenant.",
                config.name,
                config.tenant_id_claim,
                value,
            )
            return
        if not hasattr(user, "tenant_id"):
            logger.info(
                "OAuth provider %s: tenant %r resolved, but the user model has no tenant_id.",
                config.name,
                tenant_id,
            )
            return
        user.tenant_id = tenant_id


#: Token queries never need the user relationship (it would load groups and permissions).
_NO_USER = noload(OAuthToken.user)  # type: ignore[arg-type]


def _epoch(moment: datetime | None) -> float | None:
    return moment.timestamp() if moment is not None else None


def _primary_email(emails: Any) -> str | None:
    """Pick the primary verified address from a GitHub ``/user/emails`` answer."""
    if not isinstance(emails, list):
        return None
    verified = [
        entry
        for entry in emails
        if isinstance(entry, dict) and entry.get("verified") and isinstance(entry.get("email"), str)
    ]
    verified.sort(key=lambda entry: not entry.get("primary"))
    return verified[0]["email"] if verified else None


__all__ = ["OAuthBackend", "OAuthIdentity", "pkce_challenge"]
