"""OAuth provider configuration and settings (#440, docs/specs/oauth-sso.md)."""

from __future__ import annotations

import dataclasses

import pytest
from pydantic import ValidationError

from hyperadmin.auth.exceptions import OAuthConfigError
from hyperadmin.auth.oauth.providers import (
    GITHUB_EMAILS_URL,
    GITHUB_USERINFO_URL,
    GOOGLE_USERINFO_URL,
    OAuthProviderConfig,
    github_provider,
    google_provider,
)
from hyperadmin.core.settings import HyperAdminSettings


def _config(**overrides) -> OAuthProviderConfig:
    values = {
        "name": "acme",
        "client_id": "id",
        "client_secret": "secret",
        "scopes": ("openid", "email"),
        "authorize_url": "https://idp.acme.com/authorize",
        "token_url": "https://idp.acme.com/token",
        "userinfo_url": "https://idp.acme.com/userinfo",
    }
    return OAuthProviderConfig(**{**values, **overrides})


def test_google_oauth_provider_is_configured_with_its_endpoints() -> None:
    """
    Scenario: Google OAuth provider is configured via settings
      Given a Google provider built with a client id and a client secret
      When  the configuration is read
      Then  the Google provider config is accessible with correct authorize_url and token_url
    """
    google = google_provider("client-id", "client-secret")

    assert google.name == "google"
    assert google.authorize_url == "https://accounts.google.com/o/oauth2/v2/auth"
    assert google.token_url == "https://oauth2.googleapis.com/token"
    assert google.userinfo_url == GOOGLE_USERINFO_URL
    assert google.scopes == ("openid", "email", "profile")
    assert (google.sub_claim, google.email_claim) == ("sub", "email")
    assert google.authorize_params == (("access_type", "offline"),)
    assert google.required_claims == ()
    assert google.label == "Google"
    assert google.allow_signup is True


def test_google_hosted_domain_is_requested_and_enforced() -> None:
    google = google_provider("id", "secret", hosted_domain="acme.com", tenant_id_claim="hd")

    assert ("hd", "acme.com") in google.authorize_params
    assert google.required_claims == (("hd", "acme.com"),)
    assert google.tenant_id_claim == "hd"


def test_github_provider_uses_its_own_endpoints_and_claims() -> None:
    github = github_provider("id", "secret", allow_signup=False)

    assert github.name == "github"
    assert github.authorize_url == "https://github.com/login/oauth/authorize"
    assert github.token_url == "https://github.com/login/oauth/access_token"
    assert github.userinfo_url == GITHUB_USERINFO_URL
    assert github.emails_url == GITHUB_EMAILS_URL
    assert github.sub_claim == "id"
    assert github.scopes == ("read:user", "user:email")
    assert github.label == "GitHub"
    assert github.allow_signup is False


def test_missing_client_id_raises_validation_error() -> None:
    """
    Scenario: missing client_id raises validation error
      Given OAuthProviderConfig with client_id=""
      When  validation runs
      Then  a ValueError is raised indicating client_id is required
    """
    with pytest.raises(ValueError, match="client_id is required") as caught:
        _config(client_id="")

    assert isinstance(caught.value, OAuthConfigError)


def test_missing_client_secret_raises_validation_error() -> None:
    with pytest.raises(OAuthConfigError, match="client_secret is required"):
        _config(client_secret="")


@pytest.mark.parametrize("name", ["", "Google", "with space", "a/b", "x" * 33])
def test_provider_name_must_be_a_short_url_segment(name: str) -> None:
    with pytest.raises(OAuthConfigError, match="name"):
        _config(name=name)


@pytest.mark.parametrize("attribute", ["authorize_url", "token_url", "userinfo_url"])
@pytest.mark.parametrize("value", ["", "idp.acme.com/x", None])
def test_endpoints_must_be_http_urls(attribute: str, value: str | None) -> None:
    with pytest.raises(OAuthConfigError, match=attribute):
        _config(**{attribute: value})


@pytest.mark.parametrize("attribute", ["emails_url", "redirect_uri"])
def test_optional_urls_are_checked_only_when_set(attribute: str) -> None:
    assert getattr(_config(), attribute) is None
    assert getattr(_config(**{attribute: "http://localhost:8000/x"}), attribute)
    with pytest.raises(OAuthConfigError, match=attribute):
        _config(**{attribute: "/relative"})


def test_config_is_frozen_and_hides_the_client_secret() -> None:
    config = _config(client_secret="top-secret", scopes=["openid"])

    assert "top-secret" not in repr(config)
    assert config.scopes == ("openid",)
    assert config.label == "Acme"
    assert _config(button_label="Acme SSO").label == "Acme SSO"
    assert _config(name="my-idp").label == "My Idp"
    with pytest.raises(dataclasses.FrozenInstanceError):
        config.client_id = "other"  # type: ignore[misc]


def test_oauth_settings_have_safe_defaults() -> None:
    settings = HyperAdminSettings()

    assert settings.oauth_token_secret is None
    assert settings.oauth_state_ttl_seconds == 600
    assert settings.oauth_refresh_leeway_seconds == 60
    assert settings.oauth_login_redirect is None
    assert settings.oauth_callback_rate_limit == (20, 60)


def test_oauth_settings_load_from_the_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("HYPERADMIN_OAUTH_TOKEN_SECRET", "key-from-env")
    monkeypatch.setenv("HYPERADMIN_OAUTH_STATE_TTL_SECONDS", "120")
    monkeypatch.setenv("HYPERADMIN_OAUTH_REFRESH_LEEWAY_SECONDS", "300")
    monkeypatch.setenv("HYPERADMIN_OAUTH_LOGIN_REDIRECT", "/admin/orders/")
    monkeypatch.setenv("HYPERADMIN_OAUTH_CALLBACK_RATE_LIMIT", "[5, 30]")

    settings = HyperAdminSettings()

    assert settings.oauth_token_secret is not None
    assert settings.oauth_token_secret.get_secret_value() == "key-from-env"
    assert "key-from-env" not in repr(settings)
    assert settings.oauth_state_ttl_seconds == 120
    assert settings.oauth_refresh_leeway_seconds == 300
    assert settings.oauth_login_redirect == "/admin/orders/"
    assert settings.oauth_callback_rate_limit == (5, 30)


def test_oauth_state_ttl_must_be_positive() -> None:
    with pytest.raises(ValidationError):
        HyperAdminSettings(oauth_state_ttl_seconds=0)
