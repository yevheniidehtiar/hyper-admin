"""Structured auth exceptions (#442, docs/specs/oauth-sso.md)."""

from __future__ import annotations

import subprocess
import sys
from types import SimpleNamespace

import pytest

from hyperadmin.auth.exceptions import (
    AccountDisabledError,
    AccountLinkRequiredError,
    HyperAdminAuthError,
    LastSignInMethodError,
    MFARequiredError,
    OAuthConfigError,
    OAuthProviderError,
    OAuthSignupDisabledError,
    OAuthStateError,
)


def test_oauth_provider_error_carries_provider_name_and_detail() -> None:
    """
    Scenario: OAuthProviderError carries provider name and detail
      Given an OAuth failure from Google
      When  OAuthProviderError("google", "Token exchange failed") is raised
      Then  str(exc) contains "google" and "Token exchange failed"
    """
    with pytest.raises(OAuthProviderError) as caught:
        raise OAuthProviderError("google", "Token exchange failed")

    exc = caught.value
    assert "google" in str(exc)
    assert "Token exchange failed" in str(exc)
    assert (exc.provider, exc.detail) == ("google", "Token exchange failed")
    assert exc.error_code is None
    assert exc.transient is False


def test_oauth_provider_error_keeps_the_error_code_and_transient_flag() -> None:
    exc = OAuthProviderError("google", "revoked", error_code="invalid_grant", transient=True)

    assert exc.error_code == "invalid_grant"
    assert exc.transient is True


def test_mfa_required_error_carries_the_user_and_redirect_url() -> None:
    """
    Scenario: MFARequiredError carries the user and redirect URL
      Given user alice requires MFA
      When  MFARequiredError(user=alice, redirect="/admin/mfa/challenge") is raised
      Then  exc.user is alice and exc.redirect is "/admin/mfa/challenge"
    """
    alice = SimpleNamespace(username="alice")

    with pytest.raises(MFARequiredError) as caught:
        raise MFARequiredError(user=alice, redirect="/admin/mfa/challenge")

    assert caught.value.user is alice
    assert caught.value.redirect == "/admin/mfa/challenge"
    assert "/admin/mfa/challenge" in str(caught.value)


def test_every_error_derives_from_the_auth_base_class() -> None:
    errors = [
        OAuthConfigError("no secret"),
        OAuthProviderError("google", "boom"),
        OAuthStateError(),
        AccountLinkRequiredError("google", "alice@acme.com"),
        OAuthSignupDisabledError("github"),
        AccountDisabledError("alice"),
        LastSignInMethodError("google"),
        MFARequiredError(user=None, redirect="/admin/mfa/challenge"),
    ]

    assert all(isinstance(error, HyperAdminAuthError) for error in errors)


def test_config_error_is_also_a_value_error() -> None:
    with pytest.raises(ValueError, match="no secret"):
        raise OAuthConfigError("no secret")


def test_context_is_kept_on_the_account_errors() -> None:
    link = AccountLinkRequiredError("google", "alice@acme.com")
    signup = OAuthSignupDisabledError("github")
    last = LastSignInMethodError("google")
    state = OAuthStateError("expired")

    assert (link.provider, link.email) == ("google", "alice@acme.com")
    assert "alice@acme.com" in str(link)
    assert signup.provider == "github"
    assert last.provider == "google"
    assert str(last) == "Set a password before unlinking your only sign-in method"
    assert state.detail == "expired"
    assert OAuthStateError().detail == "Invalid or expired OAuth state"


def test_importing_the_exceptions_registers_no_table() -> None:
    code = (
        "import hyperadmin.auth.exceptions\n"
        "from sqlmodel import SQLModel\n"
        "print(sorted(t for t in SQLModel.metadata.tables if t.startswith('hyperadmin_')))"
    )
    result = subprocess.run(
        [sys.executable, "-c", code], check=False, capture_output=True, text=True
    )

    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == "[]"
