"""Identity-provider configuration for OAuth2/OIDC sign-in (``docs/specs/oauth-sso.md``).

One :class:`OAuthProviderConfig` describes how to talk to a provider: its endpoints,
the scopes to request and the userinfo claims that carry the stable user id and the
email. It is wired in host code, so it is a frozen dataclass and not a settings
model. :func:`google_provider` and :func:`github_provider` fill in the endpoints;
any other OIDC provider needs only its own ``OAuthProviderConfig``.

This module has no third-party imports: building a configuration needs no extra.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from hyperadmin.auth.exceptions import OAuthConfigError

GOOGLE_AUTHORIZE_URL = "https://accounts.google.com/o/oauth2/v2/auth"
GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"  # noqa: S105 - a public URL
GOOGLE_USERINFO_URL = "https://openidconnect.googleapis.com/v1/userinfo"
GOOGLE_SCOPES: tuple[str, ...] = ("openid", "email", "profile")

GITHUB_AUTHORIZE_URL = "https://github.com/login/oauth/authorize"
GITHUB_TOKEN_URL = "https://github.com/login/oauth/access_token"  # noqa: S105 - a public URL
GITHUB_USERINFO_URL = "https://api.github.com/user"
GITHUB_EMAILS_URL = "https://api.github.com/user/emails"
GITHUB_SCOPES: tuple[str, ...] = ("read:user", "user:email")

#: A provider name is a URL segment and the ``OAuthToken.provider`` value (32 chars).
_NAME = re.compile(r"^[a-z0-9][a-z0-9_-]{0,31}$")
_URL = re.compile(r"^https?://\S+$")


@dataclass(frozen=True, slots=True)
class OAuthProviderConfig:
    """One OAuth2/OIDC identity provider.

    Attributes:
        name: Lower-case name used in URLs and stored on ``OAuthToken.provider``.
        client_id: OAuth client id issued by the provider.
        client_secret: OAuth client secret (left out of ``repr``).
        scopes: Scopes requested at authorization.
        authorize_url: Authorization endpoint.
        token_url: Token endpoint (code exchange and refresh).
        userinfo_url: Endpoint returning the signed-in user's profile as JSON.
        sub_claim: Userinfo key of the stable user id (OIDC ``sub``, GitHub ``id``).
        email_claim: Userinfo key of the email address.
        tenant_id_claim: Userinfo key (Google ``hd``) handed to the backend's
            ``tenant_resolver`` when a user is created; ``None`` skips it.
        button_label: Text after "Sign in with" on the login page; defaults to the
            capitalised ``name``.
        button_icon: URL of an image shown on the button, used as is.
        redirect_uri: Callback URL registered at the provider. ``None`` builds it
            from the request (``{admin}/oauth/callback/{name}``); set it when the
            admin sits behind a proxy that hides the public host.
        emails_url: Endpoint listing the user's addresses, asked when userinfo
            carries no email (GitHub accounts with a private address).
        authorize_params: Extra query parameters of the authorization request.
        required_claims: Userinfo ``(key, value)`` pairs that must match, or the
            sign-in is refused (Google ``hd`` for a Workspace domain).
        allow_signup: ``False`` refuses identities that are not linked to a user
            yet, so only existing users who linked the provider can sign in.

    Raises:
        OAuthConfigError: A required value is empty or malformed (a ``ValueError``).
    """

    name: str
    client_id: str
    client_secret: str = field(repr=False)
    scopes: tuple[str, ...]
    authorize_url: str
    token_url: str
    userinfo_url: str
    sub_claim: str = "sub"
    email_claim: str = "email"
    tenant_id_claim: str | None = None
    button_label: str | None = None
    button_icon: str | None = None
    redirect_uri: str | None = None
    emails_url: str | None = None
    authorize_params: tuple[tuple[str, str], ...] = ()
    required_claims: tuple[tuple[str, str], ...] = ()
    allow_signup: bool = True

    def __post_init__(self) -> None:
        if not _NAME.fullmatch(self.name or ""):
            msg = (
                f"OAuth provider name {self.name!r} is invalid: use 1-32 lower-case "
                "letters, digits, '_' or '-'."
            )
            raise OAuthConfigError(msg)
        for attribute in ("client_id", "client_secret"):
            if not getattr(self, attribute):
                msg = f"OAuth provider {self.name!r}: {attribute} is required."
                raise OAuthConfigError(msg)
        for attribute in ("authorize_url", "token_url", "userinfo_url"):
            self._check_url(attribute, optional=False)
        for attribute in ("emails_url", "redirect_uri"):
            self._check_url(attribute, optional=True)
        # A list is a natural way to write scopes; keep the frozen value hashable.
        object.__setattr__(self, "scopes", tuple(self.scopes))

    def _check_url(self, attribute: str, *, optional: bool) -> None:
        value = getattr(self, attribute)
        if value is None and optional:
            return
        if not value or not _URL.fullmatch(value):
            msg = f"OAuth provider {self.name!r}: {attribute} must be an http(s) URL."
            raise OAuthConfigError(msg)

    @property
    def label(self) -> str:
        """The provider's display name on the login button (``"Google"``)."""
        return self.button_label or self.name.replace("_", " ").replace("-", " ").title()


def google_provider(
    client_id: str,
    client_secret: str,
    *,
    hosted_domain: str | None = None,
    tenant_id_claim: str | None = None,
    scopes: tuple[str, ...] = GOOGLE_SCOPES,
    redirect_uri: str | None = None,
    allow_signup: bool = True,
) -> OAuthProviderConfig:
    """Build the Google (OIDC) provider.

    Args:
        client_id: OAuth client id from the Google Cloud console.
        client_secret: Its client secret.
        hosted_domain: A Google Workspace domain (``"acme.com"``). Google is asked
            to show only its accounts, and a sign-in whose ``hd`` claim differs is
            refused.
        tenant_id_claim: See :class:`OAuthProviderConfig` (usually ``"hd"``).
        scopes: Scopes to request.
        redirect_uri: See :class:`OAuthProviderConfig`.
        allow_signup: See :class:`OAuthProviderConfig`.
    """
    # access_type=offline makes Google issue a refresh token on the first consent.
    authorize_params: tuple[tuple[str, str], ...] = (("access_type", "offline"),)
    required_claims: tuple[tuple[str, str], ...] = ()
    if hosted_domain:
        authorize_params = (*authorize_params, ("hd", hosted_domain))
        required_claims = (("hd", hosted_domain),)
    return OAuthProviderConfig(
        name="google",
        client_id=client_id,
        client_secret=client_secret,
        scopes=scopes,
        authorize_url=GOOGLE_AUTHORIZE_URL,
        token_url=GOOGLE_TOKEN_URL,
        userinfo_url=GOOGLE_USERINFO_URL,
        tenant_id_claim=tenant_id_claim,
        button_label="Google",
        redirect_uri=redirect_uri,
        authorize_params=authorize_params,
        required_claims=required_claims,
        allow_signup=allow_signup,
    )


def github_provider(
    client_id: str,
    client_secret: str,
    *,
    scopes: tuple[str, ...] = GITHUB_SCOPES,
    redirect_uri: str | None = None,
    allow_signup: bool = True,
) -> OAuthProviderConfig:
    """Build the GitHub provider (OAuth2 with GitHub's own userinfo API).

    GitHub is not OIDC: the stable user id is the numeric ``id`` of ``/user``, and
    an account with a private email is resolved through ``/user/emails``.

    Args:
        client_id: Client id of the GitHub OAuth app.
        client_secret: Its client secret.
        scopes: Scopes to request; ``user:email`` is needed for private addresses.
        redirect_uri: See :class:`OAuthProviderConfig`.
        allow_signup: See :class:`OAuthProviderConfig`.
    """
    return OAuthProviderConfig(
        name="github",
        client_id=client_id,
        client_secret=client_secret,
        scopes=scopes,
        authorize_url=GITHUB_AUTHORIZE_URL,
        token_url=GITHUB_TOKEN_URL,
        userinfo_url=GITHUB_USERINFO_URL,
        sub_claim="id",
        button_label="GitHub",
        redirect_uri=redirect_uri,
        emails_url=GITHUB_EMAILS_URL,
        allow_signup=allow_signup,
    )


__all__ = [
    "GITHUB_AUTHORIZE_URL",
    "GITHUB_EMAILS_URL",
    "GITHUB_SCOPES",
    "GITHUB_TOKEN_URL",
    "GITHUB_USERINFO_URL",
    "GOOGLE_AUTHORIZE_URL",
    "GOOGLE_SCOPES",
    "GOOGLE_TOKEN_URL",
    "GOOGLE_USERINFO_URL",
    "OAuthProviderConfig",
    "github_provider",
    "google_provider",
]
