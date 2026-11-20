"""Encryption of OAuth tokens at rest (``docs/specs/oauth-sso.md``).

Access and refresh tokens are bearer credentials, so ``OAuthToken`` stores only their
Fernet ciphertext. The key comes from ``settings.oauth_token_secret``
(``HYPERADMIN_OAUTH_TOKEN_SECRET``): one url-safe base64 32-byte key, or several
separated by commas for rotation. Encryption uses the first key, decryption tries
each one in order.

``cryptography`` ships with the ``oauth`` extra and is imported only when a cipher
is built, so importing this module (and ``hyperadmin.auth.models``) never needs it.
"""

from __future__ import annotations

import os
from typing import Any

from hyperadmin.auth.exceptions import OAuthConfigError

#: Environment variable holding the Fernet key(s).
TOKEN_SECRET_ENV = "HYPERADMIN_OAUTH_TOKEN_SECRET"  # noqa: S105 - a variable name, not a secret

_INSTALL_HINT = "Install the OAuth extra: pip install 'hyper-admin[oauth]'."
_KEY_HINT = (
    "Generate a key with: "
    'python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"'
)


class FernetTokenCipher:
    """Encrypt and decrypt token strings with one or more Fernet keys.

    Args:
        secret: One url-safe base64 Fernet key, or several separated by commas
            (the first encrypts, all of them decrypt).

    Raises:
        OAuthConfigError: ``secret`` is empty or not a valid key, or ``cryptography``
            is not installed.
    """

    def __init__(self, secret: str) -> None:
        keys = [part.strip() for part in secret.split(",") if part.strip()]
        if not keys:
            msg = f"OAuth needs a token encryption key: set {TOKEN_SECRET_ENV}. {_KEY_HINT}"
            raise OAuthConfigError(msg)
        try:
            from cryptography.fernet import Fernet, InvalidToken, MultiFernet  # noqa: PLC0415
        except ImportError as exc:
            msg = f"OAuth token encryption needs the 'cryptography' package. {_INSTALL_HINT}"
            raise OAuthConfigError(msg) from exc
        try:
            fernets = [Fernet(key.encode()) for key in keys]
        except ValueError as exc:
            msg = (
                f"{TOKEN_SECRET_ENV} holds an invalid Fernet key: each key must be 32 "
                f"url-safe base64-encoded bytes. {_KEY_HINT}"
            )
            raise OAuthConfigError(msg) from exc
        self._fernet: Any = MultiFernet(fernets)
        self._invalid_token: type[Exception] = InvalidToken

    def encrypt(self, plaintext: str) -> bytes:
        """Return the ciphertext of ``plaintext`` under the first key."""
        return self._fernet.encrypt(plaintext.encode())

    def decrypt(self, ciphertext: bytes) -> str:
        """Return the plaintext of ``ciphertext``.

        Raises:
            OAuthConfigError: No configured key decrypts it (the key was replaced
                without keeping the old one in the list).
        """
        try:
            return self._fernet.decrypt(bytes(ciphertext)).decode()
        except self._invalid_token as exc:
            msg = (
                f"A stored OAuth token cannot be decrypted with {TOKEN_SECRET_ENV}. When "
                "rotating the key, keep the old one after the new one, separated by a comma."
            )
            raise OAuthConfigError(msg) from exc


#: The process-wide cipher; a one-item list so it can be swapped without ``global``.
_configured: list[FernetTokenCipher] = []


def configure_token_cipher(secret: str | None) -> None:
    """Set the process-wide cipher from ``secret``; ``None`` drops it.

    ``Admin(oauth_backend=...)`` calls this with ``settings.oauth_token_secret``.
    Without it, :func:`token_cipher` reads ``HYPERADMIN_OAUTH_TOKEN_SECRET``.

    Raises:
        OAuthConfigError: ``secret`` is not a usable key.
    """
    cipher = FernetTokenCipher(secret) if secret is not None else None
    _configured.clear()
    if cipher is not None:
        _configured.append(cipher)


def token_cipher() -> FernetTokenCipher:
    """Return the process-wide cipher, building it from the environment when unset.

    Raises:
        OAuthConfigError: No usable key is configured.
    """
    if not _configured:
        _configured.append(FernetTokenCipher(os.environ.get(TOKEN_SECRET_ENV, "")))
    return _configured[0]


__all__ = ["TOKEN_SECRET_ENV", "FernetTokenCipher", "configure_token_cipher", "token_cipher"]
