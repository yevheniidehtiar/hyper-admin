from argon2 import PasswordHasher

_ph = PasswordHasher()


def hash_password(password: str) -> str:
    """Hashes a password using Argon2."""
    return _ph.hash(password)


def verify_password(password: str, hash: str) -> bool:
    """Verifies a password against an Argon2 hash."""
    try:
        return _ph.verify(hash, password)
    except Exception:
        return False
