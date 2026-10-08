"""Signed double-submit CSRF tokens.

Pure and stdlib-only (``hmac``, ``hashlib``, ``secrets``, ``base64``). The HTTP
side — reading the cookie, header or form field and checking ``Origin`` — lives in
``views/``; this module only issues and verifies tokens.

A token is ``"<nonce_b64url>.<hmac_b64url>"``: a random 32-byte nonce and its
HMAC-SHA256 under a key derived from the admin ``secret_key``.
"""

from __future__ import annotations

import base64
import binascii
import hashlib
import hmac
import secrets
from typing import Any

_NONCE_BYTES = 32
_KEY_CONTEXT = b"hyperadmin.csrf.v1"


def _b64encode(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode("ascii")


def _b64decode(text: str) -> bytes:
    """Decode unpadded base64url, accepting only the canonical encoding.

    Non-strict decoding ignores the unused low bits of the final character, so
    several spellings decode to the same bytes; re-encoding rejects all but one.

    Raises:
        ValueError: When ``text`` is not canonical unpadded base64url.
    """
    padded = text + "=" * (-len(text) % 4)
    raw = base64.b64decode(padded.encode("ascii"), altchars=b"-_", validate=True)
    if _b64encode(raw) != text:
        msg = "Non-canonical base64url encoding"
        raise ValueError(msg)
    return raw


class CsrfTokenSigner:
    """Issue and verify HMAC-signed CSRF tokens.

    Args:
        secret: The admin secret key. A purpose-specific signing key is derived
            from it, so CSRF signatures never collide with session signatures.

    Raises:
        ValueError: When ``secret`` is empty.
    """

    __slots__ = ("_key",)

    def __init__(self, secret: str | bytes) -> None:
        if not secret:
            msg = "CsrfTokenSigner requires a non-empty secret"
            raise ValueError(msg)
        secret_bytes = secret.encode("utf-8") if isinstance(secret, str) else secret
        self._key = hmac.new(secret_bytes, _KEY_CONTEXT, hashlib.sha256).digest()

    def _sign(self, nonce: bytes) -> bytes:
        return hmac.new(self._key, nonce, hashlib.sha256).digest()

    def issue(self) -> str:
        """Return a new token ``"<nonce>.<signature>"``."""
        nonce = secrets.token_bytes(_NONCE_BYTES)
        return f"{_b64encode(nonce)}.{_b64encode(self._sign(nonce))}"

    def is_valid(self, token: Any) -> bool:
        """Return ``True`` when ``token`` carries a valid signature (constant time)."""
        if not isinstance(token, str) or token.count(".") != 1:
            return False
        nonce_text, sig_text = token.split(".")
        if not nonce_text or not sig_text:
            return False
        try:
            nonce = _b64decode(nonce_text)
            signature = _b64decode(sig_text)
        except (binascii.Error, ValueError):
            return False
        if len(nonce) != _NONCE_BYTES:
            return False
        return hmac.compare_digest(signature, self._sign(nonce))

    @staticmethod
    def matches(cookie: Any, submitted: Any) -> bool:
        """Return ``True`` when the cookie and submitted tokens are identical."""
        if not isinstance(cookie, str) or not isinstance(submitted, str):
            return False
        if not cookie or not submitted:
            return False
        return hmac.compare_digest(cookie.encode("utf-8"), submitted.encode("utf-8"))
