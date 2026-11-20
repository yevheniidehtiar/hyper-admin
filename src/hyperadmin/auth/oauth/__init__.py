"""OAuth2/OIDC single sign-on for the built-in auth (``docs/specs/oauth-sso.md``).

Opt-in: nothing here is imported unless the host passes ``Admin(oauth_backend=...)``,
and the HTTP client and the token cipher need ``pip install 'hyper-admin[oauth]'``.

Exports are resolved lazily (PEP 562), so importing this package, its provider
configuration or its exceptions loads neither the ORM models nor the extra.
"""

from __future__ import annotations

import importlib
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from hyperadmin.auth.exceptions import (
        AccountLinkRequiredError,
        MFARequiredError,
        OAuthConfigError,
        OAuthProviderError,
    )
    from hyperadmin.auth.oauth.backend import OAuthBackend, OAuthIdentity
    from hyperadmin.auth.oauth.providers import (
        OAuthProviderConfig,
        github_provider,
        google_provider,
    )
    from hyperadmin.auth.oauth.tokens import (
        FernetTokenCipher,
        configure_token_cipher,
        token_cipher,
    )

_BACKEND_MODULE = "hyperadmin.auth.oauth.backend"
_EXCEPTIONS_MODULE = "hyperadmin.auth.exceptions"
_PROVIDERS_MODULE = "hyperadmin.auth.oauth.providers"
_TOKENS_MODULE = "hyperadmin.auth.oauth.tokens"
_LAZY_EXPORTS: dict[str, str] = {
    "OAuthBackend": _BACKEND_MODULE,
    "OAuthIdentity": _BACKEND_MODULE,
    "AccountLinkRequiredError": _EXCEPTIONS_MODULE,
    "MFARequiredError": _EXCEPTIONS_MODULE,
    "OAuthConfigError": _EXCEPTIONS_MODULE,
    "OAuthProviderError": _EXCEPTIONS_MODULE,
    "OAuthProviderConfig": _PROVIDERS_MODULE,
    "github_provider": _PROVIDERS_MODULE,
    "google_provider": _PROVIDERS_MODULE,
    "FernetTokenCipher": _TOKENS_MODULE,
    "configure_token_cipher": _TOKENS_MODULE,
    "token_cipher": _TOKENS_MODULE,
}

__all__ = [
    "AccountLinkRequiredError",
    "FernetTokenCipher",
    "MFARequiredError",
    "OAuthBackend",
    "OAuthConfigError",
    "OAuthIdentity",
    "OAuthProviderConfig",
    "OAuthProviderError",
    "configure_token_cipher",
    "github_provider",
    "google_provider",
    "token_cipher",
]


def __getattr__(name: str) -> Any:
    """Resolve an export on first access and cache it on the module."""
    module_name = _LAZY_EXPORTS.get(name)
    if module_name is None:
        msg = f"module {__name__!r} has no attribute {name!r}"
        raise AttributeError(msg)
    value = getattr(importlib.import_module(module_name), name)
    globals()[name] = value
    return value


def __dir__() -> list[str]:
    return sorted({*globals(), *__all__})
