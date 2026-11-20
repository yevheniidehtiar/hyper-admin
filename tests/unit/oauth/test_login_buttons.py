"""OAuth buttons on the login page and the public exports (#445)."""

from __future__ import annotations

import subprocess
import sys

import httpx
import pytest
from sqlalchemy.ext.asyncio import AsyncEngine

from hyperadmin.auth.oauth.backend import OAuthBackend
from hyperadmin.auth.oauth.providers import OAuthProviderConfig, google_provider
from tests.unit.oauth.conftest import SECRET_KEY, FakeProvider

pytestmark = pytest.mark.anyio


async def test_login_page_shows_configured_oauth_provider_buttons(build_app) -> None:
    """
    Scenario: login page shows configured OAuth provider buttons
      Given Google and GitHub OAuth providers are configured
      When  GET /admin/login
      Then  "Sign in with Google" and "Sign in with GitHub" buttons are visible
    """
    async with build_app().client() as client:
        page = await client.get("/admin/login")

    assert page.status_code == 200
    assert 'data-testid="oauth-btn-google"' in page.text
    assert 'href="/admin/oauth/authorize/google"' in page.text
    assert "Sign in with Google" in page.text
    assert 'data-testid="oauth-btn-github"' in page.text
    assert "Sign in with GitHub" in page.text
    assert "or sign in with" in page.text
    assert 'data-testid="login-form"' in page.text


async def test_login_page_shows_buttons_only_for_configured_providers(
    build_app, engine: AsyncEngine, idp: FakeProvider
) -> None:
    """
    Scenario: login page shows OAuth buttons only for configured providers
      Given Admin is configured with provider "google"
      And   provider "github" is NOT configured
      When  the user navigates to /admin/login
      Then  the page shows a "Sign in with Google" button
      And   the page does NOT show a "Sign in with GitHub" button
    """
    oauth = OAuthBackend(
        providers={"google": google_provider("id", "secret")},
        engine=engine,
        transport=httpx.MockTransport(idp),
    )

    async with build_app(oauth=oauth).client() as client:
        page = await client.get("/admin/login")

    assert "Sign in with Google" in page.text
    assert "Sign in with GitHub" not in page.text
    assert "oauth-btn-github" not in page.text


async def test_login_page_shows_no_oauth_buttons_when_no_providers_configured(
    engine: AsyncEngine,
) -> None:
    """
    Scenario: login page shows no OAuth buttons when no providers configured
      Given no OAuth providers are configured
      When  GET /admin/login
      Then  only the username/password form is shown
    """
    from fastapi import FastAPI

    from hyperadmin.auth.session import SessionAuthBackend
    from hyperadmin.core.app import Admin
    from hyperadmin.core.registry import site
    from hyperadmin.core.settings import HyperAdminSettings

    site._registry.clear()
    app = FastAPI()
    Admin(
        app,
        engine=engine,
        settings=HyperAdminSettings(secret_key=SECRET_KEY),
        auth_backend=SessionAuthBackend(engine=engine),
    ).mount("/admin")

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        page = await client.get("/admin/login")

    assert page.status_code == 200
    assert 'data-testid="login-form"' in page.text
    assert "oauth-btn-" not in page.text
    assert "oauth-divider" not in page.text
    assert "login-notice" not in page.text


async def test_custom_provider_button_shows_its_label_and_icon(
    build_app, engine: AsyncEngine, idp: FakeProvider
) -> None:
    acme = OAuthProviderConfig(
        name="acme",
        client_id="id",
        client_secret="secret",
        scopes=("openid", "email"),
        authorize_url="https://idp.acme.com/authorize",
        token_url="https://idp.acme.com/token",
        userinfo_url="https://idp.acme.com/userinfo",
        button_label="Acme SSO",
        button_icon="/assets/acme.svg",
    )
    oauth = OAuthBackend(
        providers={"acme": acme}, engine=engine, transport=httpx.MockTransport(idp)
    )

    async with build_app(oauth=oauth).client() as client:
        page = await client.get("/admin/login")

    assert "Sign in with Acme SSO" in page.text
    assert 'src="/assets/acme.svg"' in page.text
    assert 'data-testid="oauth-btn-acme"' in page.text


def test_oauth_names_are_importable_from_the_top_level_package() -> None:
    import hyperadmin
    import hyperadmin.auth
    from hyperadmin.auth import oauth
    from hyperadmin.auth.exceptions import AccountLinkRequiredError, OAuthProviderError

    assert hyperadmin.OAuthBackend is OAuthBackend
    assert hyperadmin.OAuthProviderConfig is OAuthProviderConfig
    assert hyperadmin.google_provider is google_provider
    assert hyperadmin.github_provider is oauth.github_provider
    assert hyperadmin.OAuthProviderError is OAuthProviderError
    assert hyperadmin.AccountLinkRequiredError is AccountLinkRequiredError
    assert hyperadmin.auth.OAuthBackend is OAuthBackend
    assert hyperadmin.auth.OAuthProviderConfig is OAuthProviderConfig
    with pytest.raises(AttributeError, match="no_such_name"):
        hyperadmin.no_such_name  # noqa: B018 - attribute access is the behaviour under test


def test_importing_hyperadmin_loads_no_oauth_code_and_no_tables() -> None:
    code = (
        "import sys\n"
        "from hyperadmin import *\n"
        "from hyperadmin import google_provider\n"
        "from sqlmodel import SQLModel\n"
        "print([n for n in sys.modules if n.startswith(('httpx_oauth', 'cryptography'))],"
        " 'hyperadmin.auth.oauth.backend' in sys.modules,"
        " sorted(t for t in SQLModel.metadata.tables if t.startswith('hyperadmin_')))"
    )
    result = subprocess.run(
        [sys.executable, "-c", code], check=False, capture_output=True, text=True
    )

    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == "[] False []"
