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
    from hyperadmin.auth.oauth.tokens import (
        FernetTokenCipher,
        configure_token_cipher,
        token_cipher,
    )

_LAZY_EXPORTS: dict[str, str] = {
    "FernetTokenCipher": "hyperadmin.auth.oauth.tokens",
    "configure_token_cipher": "hyperadmin.auth.oauth.tokens",
    "token_cipher": "hyperadmin.auth.oauth.tokens",
}

__all__ = [
    "FernetTokenCipher",
    "configure_token_cipher",
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
