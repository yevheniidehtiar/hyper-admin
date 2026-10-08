"""Unit tests for ``hyperadmin.core.csrf.CsrfTokenSigner`` and core auth exceptions."""

from __future__ import annotations

import ast
import base64
from pathlib import Path
from typing import Any

import pytest

from hyperadmin.core import AdminAccessDenied, AdminAuthenticationRequired
from hyperadmin.core.csrf import CsrfTokenSigner

SECRET = "s3cret-key-for-tests"


def _flip_signature_byte(token: str) -> str:
    nonce, sig = token.split(".")
    raw = bytearray(base64.urlsafe_b64decode(sig + "=" * (-len(sig) % 4)))
    raw[0] ^= 0x01
    tampered = base64.urlsafe_b64encode(bytes(raw)).rstrip(b"=").decode()
    return f"{nonce}.{tampered}"


# ---------------------------------------------------------------------------
# Story scenarios (st-v058-byoa-18)
# ---------------------------------------------------------------------------


def test_issued_token_validates() -> None:
    """
    Scenario: issued token validates
      Given a signer with secret S
      When  a token is issued and checked
      Then  is_valid returns True
    """
    signer = CsrfTokenSigner(SECRET)

    token = signer.issue()

    assert signer.is_valid(token) is True


def test_tampered_token_fails() -> None:
    """
    Scenario: tampered token fails
      Given an issued token with one signature byte changed
      When  is_valid runs
      Then  False is returned
    """
    signer = CsrfTokenSigner(SECRET)
    token = _flip_signature_byte(signer.issue())

    assert signer.is_valid(token) is False


def test_foreign_secret_fails() -> None:
    """
    Scenario: foreign secret fails
      Given a token signed with a different secret
      When  is_valid runs
      Then  False is returned
    """
    foreign = CsrfTokenSigner("another-secret").issue()

    assert CsrfTokenSigner(SECRET).is_valid(foreign) is False


def test_mismatched_pair_fails() -> None:
    """
    Scenario: mismatched pair fails
      Given two different valid tokens
      When  matches(a, b) runs
      Then  False is returned
    """
    signer = CsrfTokenSigner(SECRET)
    a, b = signer.issue(), signer.issue()

    assert signer.is_valid(a) and signer.is_valid(b)
    assert signer.matches(a, b) is False


# ---------------------------------------------------------------------------
# Token format and robustness
# ---------------------------------------------------------------------------


def test_token_format_is_nonce_dot_signature_in_base64url() -> None:
    token = CsrfTokenSigner(SECRET).issue()

    nonce, sig = token.split(".")
    alphabet = set("ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-_")
    assert set(nonce) <= alphabet
    assert set(sig) <= alphabet
    assert len(base64.urlsafe_b64decode(nonce + "=" * (-len(nonce) % 4))) == 32


def test_tokens_are_unique() -> None:
    signer = CsrfTokenSigner(SECRET)

    assert len({signer.issue() for _ in range(50)}) == 50


def test_bytes_secret_is_accepted() -> None:
    assert CsrfTokenSigner(SECRET.encode()).is_valid(CsrfTokenSigner(SECRET).issue())


def test_matching_pair_passes() -> None:
    signer = CsrfTokenSigner(SECRET)
    token = signer.issue()

    assert signer.matches(token, token) is True


@pytest.mark.parametrize(
    ("cookie", "submitted"),
    [(None, "x"), ("x", None), ("", ""), (None, None), (1, 1)],
)
def test_matches_rejects_missing_values(cookie: Any, submitted: Any) -> None:
    assert CsrfTokenSigner(SECRET).matches(cookie, submitted) is False


@pytest.mark.parametrize(
    "token",
    [
        None,
        "",
        "no-dot",
        "a.b.c",
        ".",
        "abc.",
        ".abc",
        "!!!.###",
        "é.é",
        12345,
    ],
)
def test_malformed_tokens_are_invalid(token: Any) -> None:
    assert CsrfTokenSigner(SECRET).is_valid(token) is False


def test_nonce_tampering_fails() -> None:
    signer = CsrfTokenSigner(SECRET)
    nonce, sig = signer.issue().split(".")
    other_nonce = signer.issue().split(".")[0]

    assert signer.is_valid(f"{other_nonce}.{sig}") is False
    assert signer.is_valid(f"{nonce}.{sig}") is True


def test_empty_secret_is_rejected() -> None:
    with pytest.raises(ValueError, match="secret"):
        CsrfTokenSigner("")


def test_csrf_module_is_stdlib_only() -> None:
    tree = ast.parse(Path("src/hyperadmin/core/csrf.py").read_text())
    imported = {
        (node.module or "").split(".")[0]
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom)
    } | {
        alias.name.split(".")[0]
        for node in ast.walk(tree)
        if isinstance(node, ast.Import)
        for alias in node.names
    }

    assert imported <= {"__future__", "base64", "binascii", "hashlib", "hmac", "secrets", "typing"}


# ---------------------------------------------------------------------------
# Auth exceptions
# ---------------------------------------------------------------------------


def test_authentication_required_carries_a_message() -> None:
    exc = AdminAuthenticationRequired("sign in first")

    assert isinstance(exc, Exception)
    assert str(exc) == "sign in first"


def test_access_denied_is_distinct_from_authentication_required() -> None:
    assert not issubclass(AdminAccessDenied, AdminAuthenticationRequired)
    assert not issubclass(AdminAuthenticationRequired, AdminAccessDenied)

    with pytest.raises(AdminAccessDenied):
        raise AdminAccessDenied


def test_exceptions_have_default_messages() -> None:
    assert str(AdminAuthenticationRequired()) == "Authentication required"
    assert str(AdminAccessDenied()) == "Admin access denied"
