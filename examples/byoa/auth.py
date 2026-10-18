"""The host application's own authentication (``examples/byoa``).

A typical bearer-token setup: ``OAuth2PasswordBearer`` plus a signed JWT. It is
written with the standard library only (HS256 through ``hmac``, PBKDF2 password
hashes) so the example needs no extra dependency. A real app would use its JWT
library of choice; HyperAdmin does not care how the token is checked, only that
``get_current_user`` returns a user or ``None``.

Demo-only: the signing secret comes from ``BYOA_JWT_SECRET``; when it is unset a
fixed demo value is used and a warning is logged (see ``examples/byoa/config.py``).
Never ship a default secret.
"""

from __future__ import annotations

import base64
import binascii
import hashlib
import hmac
import json
import secrets
import time
from typing import Any

from fastapi import Depends, Request
from fastapi.security import OAuth2PasswordBearer
from sqlmodel import select

from examples.byoa.config import demo_secret
from examples.byoa.models import Account

# Demo-only fallback, never ship this: a real app reads os.environ["BYOA_JWT_SECRET"].
JWT_SECRET = demo_secret("BYOA_JWT_SECRET", "byoa-demo-jwt-secret")
TOKEN_TTL_SECONDS = 3600
_PBKDF2_ROUNDS = 100_000

#: ``auto_error=False``: an anonymous request resolves to ``None`` instead of a
#: 401, so HyperAdmin can send a browser to the login page.
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/token", auto_error=False)


# ── Passwords ───────────────────────────────────────────────────────────────


def hash_password(password: str, *, salt: str | None = None) -> str:
    """Return ``pbkdf2_sha256$<rounds>$<salt>$<hex digest>``."""
    salt = salt or secrets.token_hex(8)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), _PBKDF2_ROUNDS)
    return f"pbkdf2_sha256${_PBKDF2_ROUNDS}${salt}${digest.hex()}"


def verify_password(password: str, stored: str) -> bool:
    """Check ``password`` against a :func:`hash_password` value in constant time.

    A malformed ``stored`` value (wrong field count, non-numeric, non-positive or
    out-of-range rounds) is a failed check, not an error.
    """
    try:
        _, rounds, salt, expected = stored.split("$")
        digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), int(rounds))
    except (ValueError, OverflowError):
        return False
    return hmac.compare_digest(digest.hex().encode(), expected.encode())


# ── JWT (HS256) ─────────────────────────────────────────────────────────────


def _b64(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode()


def _unb64(text: str) -> bytes:
    return base64.urlsafe_b64decode(text + "=" * (-len(text) % 4))


def _sign(signing_input: str, secret: str) -> str:
    return _b64(hmac.new(secret.encode(), signing_input.encode(), hashlib.sha256).digest())


def issue_token(
    username: str, *, ttl_seconds: int = TOKEN_TTL_SECONDS, secret: str = JWT_SECRET
) -> str:
    """Return an HS256 JWT for ``username`` that expires in ``ttl_seconds``."""
    header = _b64(json.dumps({"alg": "HS256", "typ": "JWT"}).encode())
    claims = {"sub": username, "exp": int(time.time()) + ttl_seconds}
    payload = _b64(json.dumps(claims).encode())
    signing_input = f"{header}.{payload}"
    return f"{signing_input}.{_sign(signing_input, secret)}"


def decode_token(token: str, *, secret: str = JWT_SECRET) -> dict[str, Any] | None:
    """Return the claims of a valid, unexpired token, else ``None``."""
    parts = token.split(".")
    if len(parts) != 3:  # noqa: PLR2004 - header.payload.signature
        return None
    header, payload, signature = parts
    # Compare bytes: compare_digest refuses str values with non-ASCII characters.
    expected = _sign(f"{header}.{payload}", secret)
    if not hmac.compare_digest(signature.encode(), expected.encode()):
        return None
    try:
        claims = json.loads(_unb64(payload))
    except (binascii.Error, ValueError):
        return None
    if not isinstance(claims, dict) or claims.get("exp", 0) < time.time():
        return None
    return claims


# ── The host dependency HyperAdmin reuses ───────────────────────────────────


async def get_current_user(
    request: Request,
    token: str | None = Depends(oauth2_scheme),
) -> Account | None:
    """Resolve the bearer token to an ``Account``, or ``None`` when anonymous.

    It reads the session factory from ``request.app.state``, as many host apps
    do. That works under ``/admin`` too: the admin sub-application shares the
    host's ``state`` and ``dependency_overrides``.
    """
    claims = decode_token(token) if token else None
    if claims is None:
        return None
    async with request.app.state.sessionmaker() as session:
        result = await session.execute(select(Account).where(Account.username == claims["sub"]))
        return result.scalars().first()


async def authenticate(request: Request, username: str, password: str) -> Account | None:
    """Return the account when ``password`` matches, else ``None``."""
    async with request.app.state.sessionmaker() as session:
        result = await session.execute(select(Account).where(Account.username == username))
        account = result.scalars().first()
    if account is None or not verify_password(password, account.password_hash):
        return None
    return account
