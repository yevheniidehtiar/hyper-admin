"""Structured errors of the built-in authentication flows (OAuth sign-in, MFA).

They carry context only (provider, detail, user, redirect) so a view can map each
failure to a template and a status code. Everything derives from
:class:`HyperAdminAuthError`. See ``docs/specs/oauth-sso.md``.

This module imports nothing from the ORM models: importing it registers no table.
"""

from __future__ import annotations

from typing import Any


class HyperAdminAuthError(Exception):
    """Base class of every HyperAdmin authentication error."""


class OAuthConfigError(HyperAdminAuthError, ValueError):
    """OAuth is misconfigured: a missing secret, client id, extra or collaborator.

    Raised when the configuration is built (``OAuthProviderConfig``, ``OAuthBackend``,
    ``Admin(oauth_backend=...)``), so a deployment fails at start-up and not on the
    first sign-in. It is a ``ValueError`` too, like the other ``Admin`` wiring errors.
    """


class OAuthProviderError(HyperAdminAuthError):
    """An identity provider refused a request, answered garbage or was unreachable.

    Attributes:
        provider: Name of the provider (``"google"``).
        detail: Human-readable description; never contains a token or a secret.
        error_code: The provider's OAuth ``error`` code (``"invalid_grant"``) when it sent one.
        transient: ``True`` for a network failure or a 5xx answer, where a retry may work.
    """

    def __init__(
        self,
        provider: str,
        detail: str,
        *,
        error_code: str | None = None,
        transient: bool = False,
    ) -> None:
        self.provider = provider
        self.detail = detail
        self.error_code = error_code
        self.transient = transient
        super().__init__(f"OAuth provider {provider!r}: {detail}")


class OAuthStateError(HyperAdminAuthError):
    """The authorize ``state`` is missing, does not match or is expired (CSRF guard)."""

    def __init__(self, detail: str = "Invalid or expired OAuth state") -> None:
        self.detail = detail
        super().__init__(detail)


class AccountLinkRequiredError(HyperAdminAuthError):
    """The identity cannot be used as is: an account conflict needs an explicit link.

    HyperAdmin never links an identity to an existing account by email alone.

    Attributes:
        provider: Name of the provider the identity comes from.
        email: The email address the provider reported.
    """

    def __init__(self, provider: str, email: str) -> None:
        self.provider = provider
        self.email = email
        super().__init__(
            f"An account already exists for {email!r}; sign in with your password and "
            f"link {provider!r} from settings."
        )


class OAuthSignupDisabledError(HyperAdminAuthError):
    """An unknown identity signed in on a provider that does not create accounts."""

    def __init__(self, provider: str) -> None:
        self.provider = provider
        super().__init__(f"OAuth provider {provider!r} does not create new accounts.")


class AccountDisabledError(HyperAdminAuthError):
    """The identity belongs to a user whose ``is_active`` is false."""


class LastSignInMethodError(HyperAdminAuthError):
    """Unlinking would leave the user without any way to sign in."""

    def __init__(self, provider: str) -> None:
        self.provider = provider
        super().__init__("Set a password before unlinking your only sign-in method")


class MFARequiredError(HyperAdminAuthError):
    """The first factor succeeded and the user still owes a second one.

    Attributes:
        user: The user who passed the first factor.
        redirect: URL of the challenge page (``"/admin/mfa/challenge"``).
    """

    def __init__(self, user: Any, redirect: str) -> None:
        self.user = user
        self.redirect = redirect
        super().__init__(f"MFA required; continue at {redirect}")


__all__ = [
    "AccountDisabledError",
    "AccountLinkRequiredError",
    "HyperAdminAuthError",
    "LastSignInMethodError",
    "MFARequiredError",
    "OAuthConfigError",
    "OAuthProviderError",
    "OAuthSignupDisabledError",
    "OAuthStateError",
]
