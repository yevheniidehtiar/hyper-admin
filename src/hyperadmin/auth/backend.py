from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError

ph = PasswordHasher()


def hash_password(plain: str) -> str:
    """Hashes a plain text password using Argon2."""
    return ph.hash(plain)


def verify_password(plain: str, hashed: str) -> bool:
    """Verifies a plain text password against a hashed one."""
    if not plain:
        return False
    try:
        return ph.verify(hashed, plain)
    except VerifyMismatchError:
        return False
