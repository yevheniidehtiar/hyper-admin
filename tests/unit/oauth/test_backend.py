"""``OAuthBackend``: provider calls, provisioning and token storage (#441)."""

from __future__ import annotations

import asyncio
import builtins
import logging
import time
from datetime import timedelta
from types import SimpleNamespace
from urllib.parse import parse_qs, urlsplit

import httpx
import pytest
from cryptography.fernet import Fernet
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker
from sqlmodel import select

from hyperadmin.auth.backend import hash_password
from hyperadmin.auth.exceptions import (
    AccountDisabledError,
    AccountLinkRequiredError,
    LastSignInMethodError,
    OAuthConfigError,
    OAuthProviderError,
    OAuthSignupDisabledError,
)
from hyperadmin.auth.models import OAuthToken, User
from hyperadmin.auth.oauth import backend as backend_module
from hyperadmin.auth.oauth.backend import OAuthBackend, pkce_challenge
from hyperadmin.auth.oauth.providers import github_provider, google_provider
from hyperadmin.auth.oauth.tokens import configure_token_cipher
from hyperadmin.core.timezones import utc_now
from tests.unit.oauth.conftest import FakeProvider

pytestmark = pytest.mark.anyio

USERINFO = {"sub": "abc123", "email": "alice@acme.com", "email_verified": True}
TOKEN = {"access_token": "access-1", "refresh_token": "refresh-1", "expires_at": 4_102_444_800}


async def _users(engine: AsyncEngine) -> list[User]:
    async with AsyncSession(engine) as session:
        return list((await session.execute(select(User).order_by(User.id))).scalars())  # type: ignore[arg-type]


async def _tokens(engine: AsyncEngine) -> list[OAuthToken]:
    async with AsyncSession(engine) as session:
        return list((await session.execute(select(OAuthToken).order_by(OAuthToken.id))).scalars())  # type: ignore[arg-type]


async def _add_user(engine: AsyncEngine, username: str, email: str, **extra) -> User:
    async with AsyncSession(engine) as session:
        user = User(username=username, email=email, password_hash=hash_password("secret"), **extra)
        session.add(user)
        await session.commit()
        await session.refresh(user)
        return user


# ── Construction ──────────────────────────────────────────────────────────


def test_backend_needs_at_least_one_provider() -> None:
    with pytest.raises(OAuthConfigError, match="at least one provider"):
        OAuthBackend(providers={})


def test_provider_key_must_equal_its_name() -> None:
    with pytest.raises(OAuthConfigError, match="must equal its name"):
        OAuthBackend(providers={"g": google_provider("id", "secret")})


def test_missing_extra_names_the_install_command(monkeypatch: pytest.MonkeyPatch) -> None:
    real_import = builtins.__import__

    def fake_import(name: str, *args, **kwargs):
        if name.startswith("httpx_oauth"):
            raise ImportError(name)
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", fake_import)

    with pytest.raises(OAuthConfigError, match=r"hyper-admin\[oauth\]"):
        OAuthBackend(providers={"google": google_provider("id", "secret")})


async def test_bind_fills_in_a_missing_database_only(engine: AsyncEngine) -> None:
    unbound = OAuthBackend(providers={"google": google_provider("id", "secret")})
    factory = async_sessionmaker(engine)
    own = OAuthBackend({"google": google_provider("id", "secret")}, factory)

    unbound.bind(engine=engine)
    own.bind(engine=engine)

    assert unbound.engine is engine
    assert own.engine is None
    assert own.session_factory is factory


async def test_backend_without_a_database_reports_it() -> None:
    unbound = OAuthBackend(providers={"google": google_provider("id", "secret")})

    with pytest.raises(OAuthConfigError, match="no database"):
        await unbound.linked_providers(1)


async def test_provider_lookup(backend: OAuthBackend) -> None:
    google = backend.provider("google")

    assert google is not None
    assert google.name == "google"
    assert backend.provider("unknown") is None


async def test_unknown_provider_is_a_configuration_error(backend: OAuthBackend) -> None:
    with pytest.raises(OAuthConfigError, match="not configured"):
        await backend.exchange_code("unknown", "code", "https://app/cb")


# ── Authorization URL ─────────────────────────────────────────────────────


def test_pkce_challenge_matches_the_rfc_7636_example() -> None:
    verifier = "dBjftJeZ4CVP-mB92K27uhbUJU1p1r_wW1gFWFOEjXk"

    assert pkce_challenge(verifier) == "E9Melhoa2OwvFrEMTJguCHaoeK1t8URWbuGJSstw-cM"


async def test_authorization_url_carries_state_scopes_and_pkce(backend: OAuthBackend) -> None:
    url = await backend.authorization_url("google", "https://app/cb", "state-1", "verifier-1")

    parts = urlsplit(url)
    query = {key: values[0] for key, values in parse_qs(parts.query).items()}
    assert f"{parts.scheme}://{parts.netloc}{parts.path}" == (
        "https://accounts.google.com/o/oauth2/v2/auth"
    )
    assert query["response_type"] == "code"
    assert query["client_id"] == "google-id"
    assert query["redirect_uri"] == "https://app/cb"
    assert query["state"] == "state-1"
    assert query["scope"] == "openid email profile"
    assert query["code_challenge"] == pkce_challenge("verifier-1")
    assert query["code_challenge_method"] == "S256"
    assert query["access_type"] == "offline"
    assert "google-secret" not in url


async def test_authorization_url_without_extra_parameters(backend: OAuthBackend) -> None:
    url = await backend.authorization_url("github", "https://app/cb", "s", "v")

    assert url.startswith("https://github.com/login/oauth/authorize?")
    assert "access_type" not in url


# ── Code exchange ─────────────────────────────────────────────────────────


async def test_exchange_code_returns_access_token_from_google(
    backend: OAuthBackend, idp: FakeProvider
) -> None:
    """
    Scenario: exchange_code returns access_token from Google
      Given a valid authorization code from Google OAuth
      When  exchange_code(code, redirect_uri) is called
      Then  an access_token and refresh_token are returned
    """
    token = await backend.exchange_code("google", "code-1", "https://app/cb", "verifier-1")

    assert token["access_token"] == "access-1"
    assert token["refresh_token"] == "refresh-1"
    assert token["expires_at"] > time.time()
    sent = idp.form()
    assert str(idp.requests[-1].url) == "https://oauth2.googleapis.com/token"
    assert sent["grant_type"] == "authorization_code"
    assert sent["code"] == "code-1"
    assert sent["redirect_uri"] == "https://app/cb"
    assert sent["code_verifier"] == "verifier-1"
    assert sent["client_id"] == "google-id"


async def test_exchange_code_handles_invalid_authorization_code(
    backend: OAuthBackend, idp: FakeProvider
) -> None:
    """
    Scenario: exchange_code handles invalid authorization code
      Given an expired or invalid authorization code
      When  exchange_code(code, redirect_uri) is called
      Then  an OAuthProviderError is raised
    """
    idp.token = (400, {"error": "invalid_grant", "error_description": "Bad Request"})

    with pytest.raises(OAuthProviderError) as caught:
        await backend.exchange_code("google", "expired", "https://app/cb")

    assert caught.value.provider == "google"
    assert caught.value.error_code == "invalid_grant"
    assert caught.value.transient is False
    assert "HTTP 400" in caught.value.detail


async def test_github_provider_uses_correct_token_exchange_endpoint(
    backend: OAuthBackend, idp: FakeProvider
) -> None:
    """
    Scenario: GitHub provider uses correct token exchange endpoint
      Given a GitHub OAuth provider configuration
      When  exchange_code() is called with a GitHub code
      Then  the request is sent to https://github.com/login/oauth/access_token
    """
    idp.token = (200, {"access_token": "gho_1", "scope": "read:user,user:email"})

    token = await backend.exchange_code("github", "code-1", "https://app/cb")

    request = idp.requests[-1]
    assert str(request.url) == "https://github.com/login/oauth/access_token"
    assert request.headers["accept"] == "application/json"
    assert token["access_token"] == "gho_1"
    assert "expires_at" not in token


async def test_exchange_code_rejects_an_error_document_answered_with_200(
    backend: OAuthBackend, idp: FakeProvider
) -> None:
    idp.token = (200, {"error": "bad_verification_code"})

    with pytest.raises(OAuthProviderError) as caught:
        await backend.exchange_code("github", "stale", "https://app/cb")

    assert caught.value.error_code == "bad_verification_code"


async def test_exchange_code_rejects_an_answer_without_access_token(
    backend: OAuthBackend, idp: FakeProvider
) -> None:
    idp.token = (200, {"token_type": "bearer"})

    with pytest.raises(OAuthProviderError, match="no access token"):
        await backend.exchange_code("google", "code", "https://app/cb")


async def test_exchange_code_marks_an_unreachable_provider_as_transient(
    backend: OAuthBackend, idp: FakeProvider
) -> None:
    idp.network_error = httpx.ConnectError("boom")

    with pytest.raises(OAuthProviderError) as caught:
        await backend.exchange_code("google", "code", "https://app/cb")

    assert caught.value.transient is True
    assert caught.value.error_code is None


@pytest.mark.parametrize("payload", ["<html>bad gateway</html>", ["not", "a", "dict"]])
async def test_a_server_error_without_error_code_is_transient(
    backend: OAuthBackend, idp: FakeProvider, payload: object
) -> None:
    idp.token = (502, payload)

    with pytest.raises(OAuthProviderError) as caught:
        await backend.exchange_code("google", "code", "https://app/cb")

    assert caught.value.transient is True
    assert caught.value.error_code is None


# ── Userinfo ──────────────────────────────────────────────────────────────


async def test_get_userinfo_returns_user_profile_from_google(
    backend: OAuthBackend, idp: FakeProvider
) -> None:
    """
    Scenario: get_userinfo returns user profile from Google
      Given a valid access_token for Google
      When  get_userinfo(access_token) is called
      Then  the user's email, name, and picture URL are returned
    """
    idp.userinfo = (
        200,
        {"sub": "abc123", "email": "alice@acme.com", "name": "Alice", "picture": "https://p/a"},
    )

    profile = await backend.get_userinfo("google", "access-1")

    assert profile["email"] == "alice@acme.com"
    assert profile["name"] == "Alice"
    assert profile["picture"] == "https://p/a"
    request = idp.requests[-1]
    assert str(request.url) == "https://openidconnect.googleapis.com/v1/userinfo"
    assert request.headers["authorization"] == "Bearer access-1"


async def test_github_private_email_is_read_from_the_emails_endpoint(
    backend: OAuthBackend, idp: FakeProvider
) -> None:
    idp.userinfo = (200, {"id": 42, "login": "alice", "email": None})
    idp.emails = (
        200,
        [
            {"email": "old@acme.com", "primary": False, "verified": True},
            {"email": "spoof@acme.com", "primary": True, "verified": False},
            {"email": "alice@acme.com", "primary": True, "verified": True},
        ],
    )

    profile = await backend.get_userinfo("github", "gho_1")

    assert profile["email"] == "alice@acme.com"
    assert [str(request.url) for request in idp.requests] == [
        "https://api.github.com/user",
        "https://api.github.com/user/emails",
    ]


@pytest.mark.parametrize("emails", [[], {"message": "nope"}, [{"email": "a@b.c"}]])
async def test_github_without_a_verified_email_leaves_it_empty(
    backend: OAuthBackend, idp: FakeProvider, emails: object
) -> None:
    idp.userinfo = (200, {"id": 42})
    idp.emails = (200, emails)

    profile = await backend.get_userinfo("github", "gho_1")

    assert not profile.get("email")


@pytest.mark.parametrize(("status", "transient"), [(401, False), (503, True)])
async def test_get_userinfo_reports_a_refused_request(
    backend: OAuthBackend, idp: FakeProvider, status: int, transient: bool
) -> None:
    idp.userinfo = (status, {"error": "invalid_token"})

    with pytest.raises(OAuthProviderError) as caught:
        await backend.get_userinfo("google", "bad")

    assert caught.value.transient is transient
    assert caught.value.error_code == "invalid_token"
    assert f"HTTP {status}" in caught.value.detail


async def test_get_userinfo_reports_an_unreachable_provider(
    backend: OAuthBackend, idp: FakeProvider
) -> None:
    idp.network_error = httpx.ReadTimeout("slow")

    with pytest.raises(OAuthProviderError) as caught:
        await backend.get_userinfo("google", "access-1")

    assert caught.value.transient is True


@pytest.mark.parametrize(
    ("payload", "message"),
    [("not json", "not valid JSON"), (["a"], "not a JSON object")],
)
async def test_get_userinfo_rejects_garbage(
    backend: OAuthBackend, idp: FakeProvider, payload: object, message: str
) -> None:
    idp.userinfo = (200, payload)

    with pytest.raises(OAuthProviderError, match=message):
        await backend.get_userinfo("google", "access-1")


# ── Identity ──────────────────────────────────────────────────────────────


async def test_identity_reads_the_configured_claims(backend: OAuthBackend) -> None:
    identity = backend.identity("github", {"id": 42, "email": " alice@acme.com "})

    assert (identity.provider, identity.sub, identity.email) == ("github", "42", "alice@acme.com")
    assert identity.claims["id"] == 42


@pytest.mark.parametrize(
    ("userinfo", "message"),
    [
        ({"email": "alice@acme.com"}, "no 'sub' claim"),
        ({"sub": "", "email": "alice@acme.com"}, "no 'sub' claim"),
        ({"sub": "1"}, "Email required"),
        ({"sub": "1", "email": "not-an-email"}, "Email required"),
        ({"sub": "1", "email": f"{'a' * 100}@acme.com"}, "Email required"),
        ({"sub": "1", "email": "a@acme.com", "email_verified": False}, "not verified"),
        ({"sub": "1", "email": "a@acme.com", "email_verified": "false"}, "not verified"),
    ],
)
async def test_identity_rejects_unusable_userinfo(
    backend: OAuthBackend, userinfo: dict, message: str
) -> None:
    with pytest.raises(OAuthProviderError, match=message):
        backend.identity("google", userinfo)


async def test_identity_enforces_required_claims(engine: AsyncEngine) -> None:
    workspace = OAuthBackend(
        providers={"google": google_provider("id", "secret", hosted_domain="acme.com")},
        engine=engine,
    )

    assert workspace.identity("google", {**USERINFO, "hd": "acme.com"}).sub == "abc123"
    with pytest.raises(OAuthProviderError, match="hd mismatch"):
        workspace.identity("google", {**USERINFO, "hd": "evil.com"})
    with pytest.raises(OAuthProviderError, match="hd mismatch"):
        workspace.identity("google", USERINFO)


# ── Provisioning ──────────────────────────────────────────────────────────


async def test_provision_user_creates_new_user_on_first_oauth_login(
    backend: OAuthBackend, engine: AsyncEngine
) -> None:
    """
    Scenario: provision_user creates new user on first OAuth login
      Given no user exists with email "alice@gmail.com"
      When  provision_user(userinfo) is called
      Then  a new User is created with email="alice@gmail.com", is_active=True
      And   an OAuthToken is created linking the user to the Google provider
    """
    userinfo = {"sub": "abc123", "email": "alice@gmail.com", "name": "Alice Liddell"}

    user = await backend.provision_user("google", userinfo, {**TOKEN, "scope": "openid email"})

    assert user.id is not None
    assert (user.email, user.username, user.is_active) == ("alice@gmail.com", "alice", True)
    assert (user.first_name, user.last_name) == ("Alice", "Liddell")
    assert user.is_superuser is False
    assert user.oauth_only is True
    (row,) = await _tokens(engine)
    assert (row.user_id, row.provider, row.sub) == (user.id, "google", "abc123")
    assert row.access_token == "access-1"
    assert row.refresh_token == "refresh-1"
    assert row.scopes == ["openid", "email"]
    assert row.expires_at is not None
    assert row.expires_at.timestamp() == TOKEN["expires_at"]


async def test_provision_user_returns_existing_user_on_subsequent_oauth_login(
    backend: OAuthBackend, engine: AsyncEngine
) -> None:
    """
    Scenario: provision_user links existing user on subsequent OAuth login
      Given user alice already signed in with Google once
      When  provision_user(userinfo) is called for alice's Google login
      Then  the existing User is returned
      And   the OAuthToken is updated with new access_token
    """
    first = await backend.provision_user("google", USERINFO, TOKEN)

    again = await backend.provision_user("google", USERINFO, {"access_token": "access-2"})

    assert again.id == first.id
    assert len(await _users(engine)) == 1
    (row,) = await _tokens(engine)
    assert row.access_token == "access-2"
    # Google sends the refresh token once; the stored one must survive.
    assert row.refresh_token == "refresh-1"
    assert row.expires_at is None
    assert row.scopes == ["openid", "email", "profile"]


async def test_callback_with_email_of_a_local_user_does_not_auto_link(
    backend: OAuthBackend, engine: AsyncEngine
) -> None:
    """
    Scenario: callback with email matching a local-only user does NOT auto-link
      Given a local User exists with email "alice@acme.com" and no OAuthToken
      When  an identity with email="Alice@Acme.com" signs in
      Then  AccountLinkRequiredError is raised
      And   no User or OAuthToken rows are created
    """
    await _add_user(engine, "alice", "alice@acme.com")

    with pytest.raises(AccountLinkRequiredError) as caught:
        await backend.provision_user("google", {**USERINFO, "email": "Alice@Acme.com"}, TOKEN)

    assert caught.value.provider == "google"
    assert len(await _users(engine)) == 1
    assert await _tokens(engine) == []


async def test_same_email_from_another_provider_is_a_link_conflict(
    backend: OAuthBackend, engine: AsyncEngine
) -> None:
    await backend.provision_user("google", USERINFO, TOKEN)

    with pytest.raises(AccountLinkRequiredError):
        await backend.provision_user("github", {"id": 42, "email": "alice@acme.com"}, TOKEN)

    assert len(await _tokens(engine)) == 1


async def test_inactive_user_cannot_sign_in_with_oauth(
    backend: OAuthBackend, engine: AsyncEngine
) -> None:
    user = await backend.provision_user("google", USERINFO, TOKEN)
    async with AsyncSession(engine) as session:
        stored = await session.get(User, user.id)
        assert stored is not None
        stored.is_active = False
        await session.commit()

    with pytest.raises(AccountDisabledError):
        await backend.provision_user("google", USERINFO, TOKEN)


async def test_signup_can_be_disabled_per_provider(engine: AsyncEngine) -> None:
    closed = OAuthBackend(
        providers={"github": github_provider("id", "secret", allow_signup=False)}, engine=engine
    )

    with pytest.raises(OAuthSignupDisabledError):
        await closed.provision_user("github", {"id": 42, "email": "eve@evil.com"}, TOKEN)

    assert await _users(engine) == []


async def test_username_is_made_unique_and_safe(backend: OAuthBackend, engine: AsyncEngine) -> None:
    await _add_user(engine, "alice", "alice@other.com")
    await _add_user(engine, "alice-2", "alice2@other.com")

    plain = await backend.provision_user("google", USERINFO, TOKEN)
    odd = await backend.provision_user(
        "github", {"id": 7, "email": "+++@acme.com", "name": "Mononym"}, TOKEN
    )

    assert plain.username == "alice-3"
    assert odd.username == "user"
    assert (odd.first_name, odd.last_name) == ("Mononym", "")


async def test_concurrent_first_sign_in_becomes_a_returning_sign_in(
    backend: OAuthBackend, engine: AsyncEngine, monkeypatch: pytest.MonkeyPatch
) -> None:
    original = OAuthBackend._provision
    calls = 0

    async def racing(self, identity, token):
        nonlocal calls
        calls += 1
        if calls == 1:
            # The other tab wins the race: its rows exist when this commit fails.
            await original(self, identity, token)
            raise IntegrityError("insert", {}, Exception("unique"))
        return await original(self, identity, token)

    monkeypatch.setattr(OAuthBackend, "_provision", racing)

    user = await backend.provision_user("google", USERINFO, {"access_token": "latest"})

    assert calls == 2
    assert len(await _users(engine)) == 1
    (row,) = await _tokens(engine)
    assert row.user_id == user.id
    assert row.access_token == "latest"


# ── Tenant claim ──────────────────────────────────────────────────────────


def _tenant_backend(resolver=None) -> OAuthBackend:
    return OAuthBackend(
        providers={"google": google_provider("id", "secret", tenant_id_claim="hd")},
        tenant_resolver=resolver,
    )


def test_tenant_id_claim_provisions_tenant_on_first_login() -> None:
    """
    Scenario: tenant_id_claim provisions tenant on first login
      Given OAuthProviderConfig has tenant_id_claim="hd"
      And   the IdP returns userinfo {"email": "alice@acme.com", "hd": "acme.com"}
      And   the host app maps domain "acme.com" → tenant_id 7
      When  the user is created
      Then  the new user has tenant_id = 7
    """
    backend = _tenant_backend({"acme.com": 7}.get)
    user = SimpleNamespace(tenant_id=None)

    backend._apply_tenant(user, backend.providers["google"], {"hd": "acme.com"})

    assert user.tenant_id == 7


@pytest.mark.parametrize(
    ("resolver", "claims"),
    [(None, {"hd": "acme.com"}), ({"acme.com": 7}.get, {"hd": "other.com"}), (str, {})],
)
def test_unmapped_tenant_claim_leaves_the_user_without_tenant(
    resolver, claims: dict, caplog: pytest.LogCaptureFixture
) -> None:
    backend = _tenant_backend(resolver)
    user = SimpleNamespace(tenant_id=None)

    with caplog.at_level(logging.INFO, logger="hyperadmin"):
        backend._apply_tenant(user, backend.providers["google"], claims)

    assert user.tenant_id is None
    assert "no tenant for claim hd" in caplog.text


def test_tenant_is_only_logged_while_the_user_model_has_no_tenant_column(
    caplog: pytest.LogCaptureFixture,
) -> None:
    backend = _tenant_backend({"acme.com": 7}.get)
    user = SimpleNamespace()

    with caplog.at_level(logging.INFO, logger="hyperadmin"):
        backend._apply_tenant(user, backend.providers["google"], {"hd": "acme.com"})

    assert not hasattr(user, "tenant_id")
    assert "has no tenant_id" in caplog.text


async def test_provider_without_tenant_claim_never_calls_the_resolver(
    backend: OAuthBackend,
) -> None:
    def resolver(value: object) -> int:
        raise AssertionError(value)

    backend.tenant_resolver = resolver
    user = SimpleNamespace(tenant_id=None)

    backend._apply_tenant(user, backend.providers["google"], {"hd": "acme.com"})

    assert user.tenant_id is None


# ── Link / unlink ─────────────────────────────────────────────────────────


async def test_linking_an_oauth_identity_keeps_the_user_email(
    backend: OAuthBackend, engine: AsyncEngine
) -> None:
    """
    Scenario: linking an OAuth identity from settings
      Given alice is fully authenticated
      When  alice completes the OAuth flow with a Google identity
      Then  an OAuthToken row is created for alice with provider="google"
      And   alice's User.email is unchanged
    """
    alice = await _add_user(engine, "alice", "alice@acme.com")
    assert alice.id is not None

    await backend.link_identity(
        "google", alice.id, {"sub": "g-1", "email": "alice@gmail.com"}, TOKEN
    )

    (row,) = await _tokens(engine)
    assert (row.user_id, row.provider, row.sub) == (alice.id, "google", "g-1")
    assert row.access_token == "access-1"
    assert (await _users(engine))[0].email == "alice@acme.com"
    assert await backend.linked_providers(alice.id) == {"google"}


async def test_linking_again_updates_the_same_row(
    backend: OAuthBackend, engine: AsyncEngine
) -> None:
    alice = await _add_user(engine, "alice", "alice@acme.com")
    assert alice.id is not None
    userinfo = {"sub": "g-1", "email": "alice@gmail.com"}
    await backend.link_identity("google", alice.id, userinfo, TOKEN)

    await backend.link_identity("google", alice.id, userinfo, {"access_token": "access-2"})
    await backend.link_identity(
        "google", alice.id, {"sub": "g-2", "email": "a2@gmail.com"}, {"access_token": "access-3"}
    )

    (row,) = await _tokens(engine)
    assert row.sub == "g-2"
    assert row.access_token == "access-3"


async def test_identity_of_another_user_cannot_be_linked(
    backend: OAuthBackend, engine: AsyncEngine
) -> None:
    owner = await backend.provision_user("google", USERINFO, TOKEN)
    bob = await _add_user(engine, "bob", "bob@acme.com")
    assert bob.id is not None

    with pytest.raises(AccountLinkRequiredError):
        await backend.link_identity("google", bob.id, USERINFO, TOKEN)

    (row,) = await _tokens(engine)
    assert row.user_id == owner.id


async def test_unlinking_an_oauth_identity_keeps_password_login(
    backend: OAuthBackend, engine: AsyncEngine
) -> None:
    """
    Scenario: unlinking an OAuth identity from settings
      Given alice has an OAuthToken row for provider="google"
      And   alice has a usable password (i.e. is not OAuth-only)
      When  alice unlinks google
      Then  the OAuthToken row is deleted
      And   alice can still log in with password
    """
    alice = await _add_user(engine, "alice", "alice@acme.com")
    assert alice.id is not None
    await backend.link_identity("google", alice.id, USERINFO, TOKEN)

    removed = await backend.unlink_identity("google", alice.id)

    assert removed is True
    assert await _tokens(engine) == []
    assert (await _users(engine))[0].oauth_only is False
    assert await backend.unlink_identity("google", alice.id) is False


async def test_cannot_unlink_the_only_auth_method(
    backend: OAuthBackend, engine: AsyncEngine
) -> None:
    """
    Scenario: cannot unlink the only auth method
      Given alice has an OAuthToken for provider="google"
      And   alice has no usable password (provisioned via OAuth)
      When  alice unlinks google
      Then  LastSignInMethodError is raised
    """
    alice = await backend.provision_user("google", USERINFO, TOKEN)
    assert alice.id is not None

    with pytest.raises(LastSignInMethodError, match="Set a password before unlinking"):
        await backend.unlink_identity("google", alice.id)

    assert len(await _tokens(engine)) == 1


async def test_oauth_only_user_may_unlink_one_of_two_providers(
    backend: OAuthBackend, engine: AsyncEngine
) -> None:
    alice = await backend.provision_user("google", USERINFO, TOKEN)
    assert alice.id is not None
    await backend.link_identity("github", alice.id, {"id": 42, "email": "a@acme.com"}, TOKEN)

    assert await backend.unlink_identity("google", alice.id) is True
    assert await backend.linked_providers(alice.id) == {"github"}


# ── Refresh ───────────────────────────────────────────────────────────────


async def _expiring(backend: OAuthBackend, engine: AsyncEngine, seconds: float, **token) -> int:
    user = await backend.provision_user(
        "google", USERINFO, {**TOKEN, "expires_at": time.time() + seconds, **token}
    )
    assert user.id is not None
    return user.id


async def test_near_expiry_token_is_refreshed(
    backend: OAuthBackend, engine: AsyncEngine, idp: FakeProvider
) -> None:
    """
    Scenario: token refresh middleware refreshes near-expiry tokens
      Given alice has an OAuthToken with expires_at in 30 seconds
      When  the token is refreshed with a leeway of 60 seconds
      Then  the refresh_token is exchanged for a new access token
      And   the OAuthToken row is updated with the new access and expires_at
    """
    user_id = await _expiring(backend, engine, 30)

    expires_at = await backend.refresh_token("google", user_id, leeway=60)

    assert expires_at is not None
    assert expires_at > time.time() + 3000
    sent = idp.form()
    assert sent["grant_type"] == "refresh_token"
    assert sent["refresh_token"] == "refresh-1"
    (row,) = await _tokens(engine)
    assert row.access_token == "access-2"
    assert row.refresh_token == "refresh-1"
    assert row.expires_at is not None
    assert row.expires_at - utc_now() > timedelta(minutes=50)


async def test_rotated_refresh_token_is_stored(
    backend: OAuthBackend, engine: AsyncEngine, idp: FakeProvider
) -> None:
    user_id = await _expiring(backend, engine, -5)
    idp.refresh = (200, {"access_token": "access-2", "refresh_token": "refresh-2"})

    expires_at = await backend.refresh_token("google", user_id, leeway=60)

    assert expires_at is None
    (row,) = await _tokens(engine)
    assert row.refresh_token == "refresh-2"
    assert row.expires_at is None


async def test_fresh_token_is_not_refreshed(
    backend: OAuthBackend, engine: AsyncEngine, idp: FakeProvider
) -> None:
    user_id = await _expiring(backend, engine, 3600)

    expires_at = await backend.refresh_token("google", user_id, leeway=60)

    assert expires_at is not None
    assert expires_at > time.time() + 3000
    assert idp.requests == []


async def test_nothing_to_refresh_without_link_expiry_or_refresh_token(
    backend: OAuthBackend, engine: AsyncEngine, idp: FakeProvider
) -> None:
    bob = await _add_user(engine, "bob", "bob@acme.com")
    assert bob.id is not None
    await backend.link_identity(
        "github", bob.id, {"id": 1, "email": "b@acme.com"}, {"access_token": "gho_1"}
    )
    await backend.link_identity(
        "google",
        bob.id,
        {"sub": "g-9", "email": "b@gmail.com"},
        {"access_token": "access-1", "expires_at": time.time() - 5},
    )

    assert await backend.refresh_token("google", 999, leeway=60) is None
    assert await backend.refresh_token("github", bob.id, leeway=60) is None
    assert await backend.refresh_token("google", bob.id, leeway=60) is None
    assert idp.requests == []


async def test_revoked_refresh_token_is_a_hard_failure(
    backend: OAuthBackend, engine: AsyncEngine, idp: FakeProvider
) -> None:
    user_id = await _expiring(backend, engine, 30)
    idp.refresh = (400, {"error": "invalid_grant"})

    with pytest.raises(OAuthProviderError) as caught:
        await backend.refresh_token("google", user_id, leeway=60)

    assert caught.value.error_code == "invalid_grant"
    assert caught.value.transient is False
    (row,) = await _tokens(engine)
    assert row.access_token == "access-1"


async def test_refresh_error_document_answered_with_200_is_a_hard_failure(
    backend: OAuthBackend, engine: AsyncEngine, idp: FakeProvider
) -> None:
    user_id = await _expiring(backend, engine, 30)
    idp.refresh = (200, {"error": "bad_refresh_token"})

    with pytest.raises(OAuthProviderError) as caught:
        await backend.refresh_token("google", user_id, leeway=60)

    assert caught.value.error_code == "bad_refresh_token"
    assert caught.value.transient is False


async def test_unreachable_provider_is_a_transient_refresh_failure(
    backend: OAuthBackend, engine: AsyncEngine, idp: FakeProvider
) -> None:
    user_id = await _expiring(backend, engine, 30)
    idp.network_error = httpx.ConnectError("down")

    with pytest.raises(OAuthProviderError) as caught:
        await backend.refresh_token("google", user_id, leeway=60)

    assert caught.value.transient is True


async def test_token_written_with_a_lost_key_is_a_hard_failure(
    backend: OAuthBackend, engine: AsyncEngine, idp: FakeProvider
) -> None:
    user_id = await _expiring(backend, engine, 30)
    configure_token_cipher(Fernet.generate_key().decode())

    with pytest.raises(OAuthProviderError, match="cannot be decrypted") as caught:
        await backend.refresh_token("google", user_id, leeway=60)

    assert caught.value.transient is False
    assert idp.requests == []


async def test_concurrent_refreshes_use_the_refresh_token_once(
    backend: OAuthBackend, engine: AsyncEngine, idp: FakeProvider
) -> None:
    user_id = await _expiring(backend, engine, 30)

    results = await asyncio.gather(
        backend.refresh_token("google", user_id, leeway=60),
        backend.refresh_token("google", user_id, leeway=60),
    )

    assert results[0] == results[1]
    assert len(idp.calls("/token")) == 1


# ── Helpers ───────────────────────────────────────────────────────────────


def test_scope_parsing() -> None:
    split = backend_module._split_scopes

    assert split("openid email", ()) == ["openid", "email"]
    assert split("read:user,user:email", ()) == ["read:user", "user:email"]
    assert split("  ", ("a",)) == ["a"]
    assert split(None, ("a", "b")) == ["a", "b"]


def test_name_claims() -> None:
    names = backend_module._names

    assert names({"given_name": "Alice", "family_name": "Liddell"}) == ("Alice", "Liddell")
    assert names({"name": "Alice Pleasance Liddell"}) == ("Alice", "Pleasance Liddell")
    assert names({"name": None}) == ("", "")
    assert names({"given_name": "x" * 80})[0] == "x" * 50
