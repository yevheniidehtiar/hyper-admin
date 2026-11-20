import secrets

from argon2 import PasswordHasher

_ph = PasswordHasher()

#: First character of a ``password_hash`` that no password matches (an Argon2 hash
#: starts with ``$``). Marks users who sign in through an identity provider only.
UNUSABLE_PASSWORD_PREFIX = "!"  # noqa: S105 - a marker, not a password


def hash_password(password: str) -> str:
    """Hashes a password using Argon2."""
    return _ph.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    """Verifies a password against an Argon2 hash."""
    try:
        return _ph.verify(password_hash, password)
    except Exception:
        return False


def make_unusable_password() -> str:
    """Return a ``password_hash`` value that no password verifies against.

    Used for users created by an OAuth sign-in: ``password_hash`` stays ``NOT NULL``
    (no migration for existing databases) and password login is impossible for them
    until a real password is set. The random tail keeps two such values distinct.
    """
    return UNUSABLE_PASSWORD_PREFIX + secrets.token_urlsafe(32)


def is_password_usable(password_hash: str | None) -> bool:
    """Return ``False`` for an empty hash or one made by :func:`make_unusable_password`."""
    return bool(password_hash) and not str(password_hash).startswith(UNUSABLE_PASSWORD_PREFIX)
