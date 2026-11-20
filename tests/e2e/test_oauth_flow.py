"""End-to-end tests for the OAuth sign-in (#446, docs/specs/oauth-sso.md).

Each test maps 1:1 to a scenario of issue #446 (plus the login-button scenario of the
spec). The fixture app (``tests/e2e/apps/oauth.py``) configures one provider, ``google``,
whose endpoints are a fake identity provider served by the same application: its consent
page lists the accounts it knows, and choosing one redirects back to the admin.
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from urllib.parse import parse_qs, urlsplit

import pytest
from playwright.sync_api import Page, expect

if TYPE_CHECKING:
    from collections.abc import Callable


@pytest.fixture
def oauth_base_url(start_server: Callable[..., str], e2e_port: int) -> str:
    """Start the OAuth app; its fake provider URLs point back at the same server."""
    wanted = f"http://localhost:{e2e_port}"
    base = start_server("tests.e2e.apps.oauth", extra_env={"E2E_OAUTH_IDP_URL": wanted})
    if base != wanted:
        # The port was taken between choosing and binding it, and the server moved.
        pytest.skip(f"OAuth test server moved from {wanted} to {base}")
    return base


def _click_google(page: Page, base_url: str) -> None:
    page.goto(f"{base_url}/admin/login")
    page.get_by_role("link", name="Sign in with Google").click()


def test_login_page_shows_oauth_buttons_only_for_configured_providers(
    page: Page, oauth_base_url: str
) -> None:
    """
    Scenario: login page shows OAuth buttons only for configured providers
      Given Admin is configured with provider "google"
      And   provider "github" is NOT configured
      When  the user navigates to /admin/login
      Then  the page shows a "Sign in with Google" button
      And   the page does NOT show a "Sign in with GitHub" button
    """
    # Given Admin is configured with provider "google" only (the fixture app)

    # When the user navigates to /admin/login
    page.goto(f"{oauth_base_url}/admin/login")

    # Then the page shows a "Sign in with Google" button next to the password form
    expect(page.get_by_test_id("oauth-btn-google")).to_be_visible()
    expect(page.get_by_role("link", name="Sign in with Google")).to_be_visible()
    expect(page.get_by_label("Username")).to_be_visible()

    # And the page does NOT show a "Sign in with GitHub" button
    expect(page.get_by_role("link", name="Sign in with GitHub")).to_have_count(0)


def test_oauth_login_button_redirects_to_provider(page: Page, oauth_base_url: str) -> None:
    """
    Scenario: OAuth login button redirects to provider
      Given Google OAuth is configured
      When  user clicks "Sign in with Google"
      Then  the browser navigates to the Google authorization URL
    """
    # Given Google OAuth is configured (the fixture app)

    # When user clicks "Sign in with Google"
    _click_google(page, oauth_base_url)

    # Then the browser navigates to the provider's authorization URL
    expect(page.get_by_role("heading", name="Choose an account")).to_be_visible()
    url = urlsplit(page.url)
    query = {key: values[0] for key, values in parse_qs(url.query).items()}
    assert url.path == "/_idp/authorize"
    assert query["response_type"] == "code"
    assert query["client_id"] == "e2e-client-id"
    assert query["redirect_uri"] == f"{oauth_base_url}/admin/oauth/callback/google"
    assert query["scope"] == "openid email profile"
    assert query["code_challenge_method"] == "S256"
    assert query["code_challenge"]
    assert query["state"]


def test_oauth_callback_creates_user_and_session(page: Page, oauth_base_url: str) -> None:
    """
    Scenario: OAuth callback creates user and session
      Given a mock OAuth callback with valid code
      When  the callback URL is visited
      Then  the user is created and redirected to the dashboard
    """
    # Given the provider knows newcomer@example.com, who has no admin user yet
    _click_google(page, oauth_base_url)

    # When the account is chosen and the provider redirects to the callback with a code
    page.get_by_role("link", name="Continue as newcomer@example.com").click()

    # Then the user is created and redirected to the dashboard
    expect(page).to_have_url(f"{oauth_base_url}/admin/")
    expect(page.get_by_test_id("sidebar")).to_be_visible()

    # And the new user's Google identity is listed as linked
    page.goto(f"{oauth_base_url}/admin/oauth/settings")
    expect(page.get_by_test_id("oauth-identity-google")).to_have_attribute("data-linked", "true")


def test_oauth_login_with_mfa_enabled_triggers_mfa_challenge(
    page: Page, oauth_base_url: str
) -> None:
    """
    Scenario: OAuth login with MFA enabled triggers MFA challenge
      Given user alice logged in via Google with MFA enabled
      When  the OAuth callback completes
      Then  alice is redirected to the MFA challenge page
    """
    # Given alice has MFA enabled and her Google identity linked (seeded by the app)
    _click_google(page, oauth_base_url)

    # When alice's OAuth callback completes
    page.get_by_role("link", name="Continue as alice@example.com").click()

    # Then alice is redirected to the MFA challenge page
    expect(page).to_have_url(f"{oauth_base_url}/admin/mfa/challenge")
    expect(page.get_by_label("Verification code")).to_be_visible()

    # And the admin stays closed until the code is entered
    page.goto(f"{oauth_base_url}/admin/")
    expect(page).to_have_url(f"{oauth_base_url}/admin/mfa/challenge")
