"""OAuth routes on a mounted admin: authorize, callback, link, unlink, settings (#443)."""

from __future__ import annotations

import subprocess
import sys
import time
from types import SimpleNamespace

import httpx
import pytest
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession
from sqlmodel import select

from hyperadmin.auth.backend import hash_password
from hyperadmin.auth.exceptions import OAuthConfigError
from hyperadmin.auth.models import OAuthToken, User
from hyperadmin.auth.oauth.backend import OAuthBackend, pkce_challenge
from hyperadmin.auth.oauth.providers import github_provider, google_provider
from hyperadmin.auth.oauth.session import OAUTH_FLOW_KEY, OAUTH_SESSION_KEY
from hyperadmin.auth.oauth.views import OAuthViews
from hyperadmin.auth.otp import PARTIAL_AUTH_SESSION_KEY
from tests.unit.oauth.conftest import (
    SECRET_KEY,
    TOKEN_SECRET,
    FakeProvider,
    session_of,
    sign_in,
    start,
)

pytestmark = pytest.mark.anyio


async def _users(engine: AsyncEngine) -> list[User]:
    async with AsyncSession(engine) as session:
        return list((await session.execute(select(User).order_by(User.id))).scalars())  # type: ignore[arg-type]


async def _tokens(engine: AsyncEngine) -> list[OAuthToken]:
    async with AsyncSession(engine) as session:
        return list((await session.execute(select(OAuthToken).order_by(OAuthToken.id))).scalars())  # type: ignore[arg-type]


async def _add_user(engine: AsyncEngine, username: str, email: str, **extra) -> User:
    async with AsyncSession(engine) as session:
        user = User(
            username=username,
            email=email,
            password_hash=hash_password("secret"),
            is_superuser=True,
            **extra,
        )
        session.add(user)
        await session.commit()
        await session.refresh(user)
        return user


async def _password_login(client: httpx.AsyncClient, username: str) -> None:
    response = await client.post(
        "/admin/login", data={"username": username, "password": "secret"}, follow_redirects=False
    )
    assert response.status_code == 302, response.text


# ── Authorize ─────────────────────────────────────────────────────────────


async def test_authorize_redirects_to_google_with_pkce_and_state(build_app) -> None:
    """
    Scenario: clicking the provider button redirects to authorize URL with PKCE
      Given Admin is configured with provider "google"
      When  GET /admin/oauth/authorize/google
      Then  the response is 302 to https://accounts.google.com/o/oauth2/v2/auth?...
      And   the URL includes code_challenge and code_challenge_method=S256
      And   request.session contains the matching code_verifier and state nonce
    """
    async with build_app().client() as client:
        response = await client.get("/admin/oauth/authorize/google", follow_redirects=False)
        query = await start(client)
        flow = (await session_of(client))[OAUTH_FLOW_KEY]

    assert response.status_code == 302
    assert response.headers["location"].startswith("https://accounts.google.com/o/oauth2/v2/auth?")
    assert query["client_id"] == "google-id"
    assert query["response_type"] == "code"
    assert query["scope"] == "openid email profile"
    assert query["redirect_uri"] == "http://test/admin/oauth/callback/google"
    assert query["code_challenge_method"] == "S256"
    assert query["state"] == flow["state"]
    assert query["code_challenge"] == pkce_challenge(flow["verifier"])
    assert flow["provider"] == "google"
    assert flow["link_user_id"] is None


async def test_authorize_for_an_unknown_provider_returns_404(build_app) -> None:
    """
    Scenario: GET /oauth/authorize/unknown returns 404
      Given no provider named "unknown" is configured
      When  GET /admin/oauth/authorize/unknown
      Then  response is 404
    """
    async with build_app().client() as client:
        authorize = await client.get("/admin/oauth/authorize/unknown", follow_redirects=False)
        callback = await client.get("/admin/oauth/callback/unknown?code=c&state=s")

    assert authorize.status_code == 404
    assert callback.status_code == 404


async def test_configured_redirect_uri_wins_over_the_request_url(
    build_app, engine: AsyncEngine, idp: FakeProvider
) -> None:
    public = "https://admin.acme.com/admin/oauth/callback/google"
    oauth = OAuthBackend(
        providers={"google": google_provider("id", "secret", redirect_uri=public)},
        engine=engine,
        transport=httpx.MockTransport(idp),
    )

    async with build_app(oauth=oauth).client() as client:
        query = await start(client)
        response = await client.get(
            "/admin/oauth/callback/google",
            params={"code": "c", "state": query["state"]},
            follow_redirects=False,
        )

    assert query["redirect_uri"] == public
    assert response.status_code == 302
    assert idp.form(0)["redirect_uri"] == public


# ── Callback: sign-in ─────────────────────────────────────────────────────


async def test_callback_exchanges_code_and_provisions_a_new_user(
    build_app, engine: AsyncEngine, idp: FakeProvider
) -> None:
    """
    Scenario: callback exchanges code for tokens and provisions a new user
      Given Admin is configured with provider "google"
      And   the IdP returns userinfo {"email": "alice@acme.com", "sub": "abc123"}
      And   no local user exists with that email
      When  GET /oauth/callback/google?code=...&state=<valid-state>
      Then  a new User row is created with email "alice@acme.com"
      And   an OAuthToken row stores the encrypted access and refresh tokens
      And   a full session is created
      And   the response redirects to /admin/
    """
    async with build_app().client() as client:
        query = await start(client)
        flow = (await session_of(client))[OAUTH_FLOW_KEY]
        response = await client.get(
            "/admin/oauth/callback/google",
            params={"code": "code-1", "state": query["state"]},
            follow_redirects=False,
        )
        session = await session_of(client)
        settings_page = await client.get("/admin/oauth/settings")

    assert response.status_code == 302
    assert response.headers["location"] == "/admin/"
    (user,) = await _users(engine)
    assert user.email == "alice@acme.com"
    assert user.oauth_only is True
    (row,) = await _tokens(engine)
    assert (row.user_id, row.provider, row.sub) == (user.id, "google", "abc123")
    assert b"access-1" not in row.access_token_encrypted
    assert (row.access_token, row.refresh_token) == ("access-1", "refresh-1")
    sent = idp.form(0)
    assert sent["code"] == "code-1"
    assert sent["code_verifier"] == flow["verifier"]
    assert sent["redirect_uri"] == "http://test/admin/oauth/callback/google"
    assert session["user_id"] == user.id
    assert OAUTH_FLOW_KEY not in session
    assert session[OAUTH_SESSION_KEY]["provider"] == "google"
    assert session[OAUTH_SESSION_KEY]["user_id"] == user.id
    assert session[OAUTH_SESSION_KEY]["expires_at"] > time.time()
    assert settings_page.status_code == 200


async def test_callback_signs_a_returning_user_in(build_app, engine: AsyncEngine, idp) -> None:
    """
    Scenario: callback links a returning user
      Given a User exists with provider="google" sub="abc123"
      When  GET /oauth/callback/google?code=...&state=<valid-state> with the same sub
      Then  no new User row is created
      And   the existing OAuthToken row is updated with new access / refresh values
      And   a full session is created
    """
    app = build_app()
    async with app.client() as first:
        await sign_in(first)
    idp.token = (200, {"access_token": "access-9", "refresh_token": "refresh-9"})

    async with app.client() as client:
        response = await sign_in(client)
        session = await session_of(client)

    assert response.status_code == 302
    (user,) = await _users(engine)
    (row,) = await _tokens(engine)
    assert (row.access_token, row.refresh_token) == ("access-9", "refresh-9")
    assert session["user_id"] == user.id
    assert session[OAUTH_SESSION_KEY]["expires_at"] is None


async def test_callback_with_email_of_a_local_user_answers_409(
    build_app, engine: AsyncEngine
) -> None:
    """
    Scenario: callback with email matching a local-only user does NOT auto-link
      Given a local User exists with email "alice@acme.com" and no OAuthToken
      When  GET /oauth/callback/google with userinfo email="alice@acme.com"
      Then  the response is 409 Conflict
      And   the page renders "Account exists. Sign in with your password and link from settings."
      And   no User or OAuthToken rows are created
    """
    await _add_user(engine, "alice", "alice@acme.com")

    async with build_app().client() as client:
        response = await sign_in(client)
        session = await session_of(client)

    assert response.status_code == 409
    assert "Account exists. Sign in with your password and link from settings." in response.text
    assert 'data-testid="oauth-link-required"' in response.text
    assert len(await _users(engine)) == 1
    assert await _tokens(engine) == []
    assert "user_id" not in session


async def test_callback_rejects_a_mismatched_state(build_app, idp: FakeProvider) -> None:
    """
    Scenario: callback rejects mismatched state nonce (CSRF protection)
      Given the session has state="abc"
      When  GET /oauth/callback/google?state=xyz&code=...
      Then  the response is 400 Bad Request
      And   no token exchange is attempted
    """
    async with build_app().client() as client:
        await start(client)
        response = await client.get("/admin/oauth/callback/google?state=xyz&code=code-1")

    assert response.status_code == 400
    assert "invalid or has expired" in response.text
    assert idp.requests == []


async def test_callback_rejects_an_expired_state(build_app, idp: FakeProvider) -> None:
    """
    Scenario: callback rejects expired state (10-minute TTL)
      Given the session-stored state was issued 11 minutes ago
      When  the OAuth callback arrives with that state
      Then  the response is 400 Bad Request
    """
    async with build_app().client() as client:
        query = await start(client)
        await client.get("/admin/login/_test/backdate?seconds=660")
        response = await client.get(
            "/admin/oauth/callback/google", params={"code": "c", "state": query["state"]}
        )

    assert response.status_code == 400
    assert idp.requests == []


async def test_state_is_single_use(build_app, idp: FakeProvider) -> None:
    async with build_app().client() as client:
        query = await start(client)
        params = {"code": "code-1", "state": query["state"]}
        first = await client.get(
            "/admin/oauth/callback/google", params=params, follow_redirects=False
        )
        replay = await client.get("/admin/oauth/callback/google", params=params)

    assert first.status_code == 302
    assert replay.status_code == 400
    assert len(idp.calls("/token")) == 1


@pytest.mark.parametrize("query", ["?code=c&state=s", "?state=", ""])
async def test_callback_without_a_flow_in_the_session_is_rejected(
    build_app, idp: FakeProvider, query: str
) -> None:
    async with build_app().client() as client:
        response = await client.get(f"/admin/oauth/callback/google{query}")

    assert response.status_code == 400
    assert idp.requests == []


async def test_callback_of_another_provider_is_rejected(build_app, idp: FakeProvider) -> None:
    async with build_app().client() as client:
        query = await start(client, "google")
        response = await client.get(
            "/admin/oauth/callback/github", params={"code": "c", "state": query["state"]}
        )

    assert response.status_code == 400
    assert idp.requests == []


async def test_callback_without_a_code_is_rejected(build_app, idp: FakeProvider) -> None:
    async with build_app().client() as client:
        query = await start(client)
        response = await client.get(
            "/admin/oauth/callback/google", params={"state": query["state"]}
        )

    assert response.status_code == 400
    assert idp.requests == []


async def test_provider_error_surfaces_a_clear_message(build_app, idp: FakeProvider) -> None:
    """
    Scenario: provider error from IdP surfaces a clear message
      Given the IdP returns ?error=access_denied
      When  the user is redirected back to /oauth/callback/google
      Then  the response is 400 Bad Request
      And   the body contains "OAuth provider denied access"
    """
    async with build_app().client() as client:
        query = await start(client)
        response = await client.get(
            "/admin/oauth/callback/google",
            params={"error": "access_denied", "state": query["state"]},
        )
        session = await session_of(client)

    assert response.status_code == 400
    assert "OAuth provider denied access" in response.text
    assert 'data-testid="login-form"' in response.text
    assert OAUTH_FLOW_KEY not in session
    assert idp.requests == []


@pytest.mark.parametrize(
    ("answer", "status", "text"),
    [
        ("token_400", 400, "Token exchange failed"),
        ("userinfo_503", 502, "Userinfo request failed"),
        ("no_email", 400, "Email required"),
    ],
)
async def test_provider_failures_render_the_login_page(
    build_app, engine: AsyncEngine, idp: FakeProvider, answer: str, status: int, text: str
) -> None:
    if answer == "token_400":
        idp.token = (400, {"error": "invalid_grant"})
    elif answer == "userinfo_503":
        idp.userinfo = (503, {})
    else:
        idp.userinfo = (200, {"sub": "abc123"})

    async with build_app().client() as client:
        response = await sign_in(client)

    assert response.status_code == status
    assert text in response.text
    assert await _users(engine) == []


async def test_unknown_identity_is_refused_when_signup_is_off(
    build_app, engine: AsyncEngine, idp: FakeProvider
) -> None:
    oauth = OAuthBackend(
        providers={"github": github_provider("id", "secret", allow_signup=False)},
        engine=engine,
        transport=httpx.MockTransport(idp),
    )
    idp.userinfo = (200, {"id": 42, "email": "eve@evil.com"})

    async with build_app(oauth=oauth).client() as client:
        response = await sign_in(client, "github")

    assert response.status_code == 403
    assert "No account is linked to this sign-in" in response.text
    assert await _users(engine) == []


async def test_disabled_user_is_refused(build_app, engine: AsyncEngine) -> None:
    app = build_app()
    async with app.client() as first:
        await sign_in(first)
    async with AsyncSession(engine) as session:
        user = (await session.execute(select(User))).scalar_one()
        user.is_active = False
        await session.commit()

    async with app.client() as client:
        response = await sign_in(client)
        session_data = await session_of(client)

    assert response.status_code == 403
    assert "This account is disabled." in response.text
    assert "user_id" not in session_data


async def test_sign_in_lands_on_the_configured_redirect(build_app) -> None:
    async with build_app(oauth_login_redirect="/admin/user/").client() as client:
        response = await sign_in(client)

    assert response.headers["location"] == "/admin/user/"


async def test_callback_is_rate_limited_per_client(build_app) -> None:
    async with build_app(oauth_callback_rate_limit=(2, 60)).client() as client:
        statuses = [
            (await client.get("/admin/oauth/callback/google?code=c&state=s")).status_code
            for _ in range(2)
        ]
        limited = await client.get("/admin/oauth/callback/google?code=c&state=s")

    assert statuses == [400, 400]
    assert limited.status_code == 429
    assert int(limited.headers["retry-after"]) >= 1


async def test_callback_without_a_limiter_and_without_client_address() -> None:
    limiter_calls: list[str] = []

    class Limiter:
        async def acquire(self, key: str):
            limiter_calls.append(key)
            return SimpleNamespace(allowed=True, retry_after=0)

    request = SimpleNamespace(client=None)

    assert await OAuthViews(None, None, None)._rate_limited(request) is None  # type: ignore[arg-type]
    limited = OAuthViews(None, None, None, callback_limiter=Limiter())  # type: ignore[arg-type]
    assert await limited._rate_limited(request) is None  # type: ignore[arg-type]
    assert limiter_calls == ["unknown"]


# ── Callback: MFA ─────────────────────────────────────────────────────────


async def _enable_mfa(engine: AsyncEngine) -> None:
    async with AsyncSession(engine) as session:
        user = (await session.execute(select(User))).scalar_one()
        user.mfa_enabled = True
        user.mfa_method = "email"
        await session.commit()


async def test_oauth_login_still_triggers_mfa(build_app, engine: AsyncEngine) -> None:
    """
    Scenario: OAuth login still triggers MFA when user.mfa_enabled is True
      Given user "alice" has mfa_enabled=True
      When  GET /oauth/callback/google completes successfully
      Then  a partial-auth session is created (no admin access)
      And   an OTP code is sent to alice's email
      And   the response redirects to /admin/mfa/challenge
    """
    app = build_app(mfa=True)
    async with app.client() as first:
        await sign_in(first)
    await _enable_mfa(engine)

    async with app.client() as client:
        response = await sign_in(client)
        partial = await session_of(client)
        gated = await client.get("/admin/", follow_redirects=False)
        code = app.sender.calls[-1][1]
        verify = await client.post("/admin/mfa/verify", data={"code": code}, follow_redirects=False)
        full = await session_of(client)

    assert response.status_code == 302
    assert response.headers["location"] == "/admin/mfa/challenge"
    assert app.sender.calls[-1][0] == "alice@acme.com"
    assert partial[PARTIAL_AUTH_SESSION_KEY]["stage"] == "mfa_pending"
    assert "user_id" not in partial
    assert gated.headers["location"] == "/admin/mfa/challenge"
    assert verify.headers["location"] == "/admin/"
    assert full["user_id"] == partial[PARTIAL_AUTH_SESSION_KEY]["user_id"]
    # The refresh marker survives the session reset of the MFA verify step.
    assert full[OAUTH_SESSION_KEY]["provider"] == "google"
    assert full[OAUTH_SESSION_KEY]["user_id"] == full["user_id"]


async def test_mfa_code_that_cannot_be_sent_fails_the_sign_in(
    build_app, engine: AsyncEngine
) -> None:
    app = build_app(mfa=True)
    async with app.client() as first:
        await sign_in(first)
    await _enable_mfa(engine)
    app.sender.error = RuntimeError("smtp down")

    async with app.client() as client:
        response = await sign_in(client)
        session = await session_of(client)

    assert response.status_code == 502
    assert "Could not send verification code" in response.text
    assert PARTIAL_AUTH_SESSION_KEY not in session
    assert OAUTH_SESSION_KEY not in session
    assert "user_id" not in session


async def test_mfa_rate_limit_still_leads_to_the_challenge(
    build_app, engine: AsyncEngine, monkeypatch: pytest.MonkeyPatch
) -> None:
    from hyperadmin.auth.otp import EmailOTPService, RateLimitError

    app = build_app(mfa=True)
    async with app.client() as first:
        await sign_in(first)
    await _enable_mfa(engine)

    async def limited(self, user, session) -> None:
        raise RateLimitError

    monkeypatch.setattr(EmailOTPService, "generate_and_send", limited)

    async with app.client() as client:
        response = await sign_in(client)

    assert response.headers["location"] == "/admin/mfa/challenge"


async def test_password_mfa_login_has_no_oauth_marker(build_app, engine: AsyncEngine) -> None:
    await _add_user(engine, "bob", "bob@acme.com", mfa_enabled=True, mfa_method="email")
    app = build_app(mfa=True)

    async with app.client() as client:
        await _password_login(client, "bob")
        code = app.sender.calls[-1][1]
        await client.post("/admin/mfa/verify", data={"code": code}, follow_redirects=False)
        session = await session_of(client)

    assert "user_id" in session
    assert OAUTH_SESSION_KEY not in session


# ── Link ──────────────────────────────────────────────────────────────────


async def test_linking_an_oauth_identity_from_settings(
    build_app, engine: AsyncEngine, idp: FakeProvider
) -> None:
    """
    Scenario: linking an OAuth identity from settings
      Given alice is fully authenticated and visits /admin/oauth/link/google
      When  alice completes the OAuth flow
      Then  an OAuthToken row is created for alice with provider="google"
      And   alice's User.email is unchanged
      And   the response redirects to /admin/oauth/settings with a success flash
    """
    alice = await _add_user(engine, "alice", "alice@acme.com")
    idp.userinfo = (200, {"sub": "g-1", "email": "alice@gmail.com"})

    async with build_app().client() as client:
        await _password_login(client, "alice")
        before = await client.get("/admin/oauth/settings")
        response = await sign_in(client, path="link")
        page = await client.get("/admin/oauth/settings")
        reloaded = await client.get("/admin/oauth/settings")
        session = await session_of(client)

    assert 'data-testid="oauth-link-google"' in before.text
    assert response.status_code == 302
    assert response.headers["location"] == "/admin/oauth/settings"
    (row,) = await _tokens(engine)
    assert (row.user_id, row.provider, row.sub) == (alice.id, "google", "g-1")
    (user,) = await _users(engine)
    assert user.email == "alice@acme.com"
    assert "Google account linked." in page.text
    assert 'data-testid="oauth-unlink-google"' in page.text
    assert 'data-testid="oauth-link-github"' in page.text
    assert "Google account linked." not in reloaded.text
    # A password session that links a provider stays a password session.
    assert OAUTH_SESSION_KEY not in session


async def test_link_requires_a_signed_in_user(build_app) -> None:
    async with build_app().client() as client:
        link = await client.get("/admin/oauth/link/google", follow_redirects=False)
        settings = await client.get("/admin/oauth/settings", follow_redirects=False)
        unlink = await client.post("/admin/oauth/unlink/google", follow_redirects=False)

    assert link.headers["location"] == "/admin/login"
    assert settings.headers["location"] == "/admin/login"
    assert unlink.headers["location"] == "/admin/login"


async def test_handlers_redirect_when_the_request_has_no_user() -> None:
    backend = SimpleNamespace(provider=lambda name: SimpleNamespace(name=name, label="Google"))
    views = OAuthViews(backend, None, None)  # type: ignore[arg-type]
    request = SimpleNamespace(state=SimpleNamespace(user=None))

    link = await views.link(request, "google", "/admin")  # type: ignore[arg-type]
    settings = await views.settings(request, "/admin")  # type: ignore[arg-type]
    unlink = await views.unlink(request, "google", "/admin")  # type: ignore[arg-type]

    assert [r.headers["location"] for r in (link, settings, unlink)] == ["/admin/login"] * 3


async def test_identity_of_another_user_is_not_linked(
    build_app, engine: AsyncEngine, idp: FakeProvider
) -> None:
    app = build_app()
    async with app.client() as first:
        await sign_in(first)
    await _add_user(engine, "bob", "bob@acme.com")

    async with app.client() as client:
        await _password_login(client, "bob")
        response = await sign_in(client, path="link")
        page = await client.get("/admin/oauth/settings")

    assert response.headers["location"] == "/admin/oauth/settings"
    assert 'data-testid="oauth-settings-error"' in page.text
    assert "Account exists." in page.text
    assert len(await _tokens(engine)) == 1


async def test_link_callback_after_logout_links_nothing(
    build_app, engine: AsyncEngine, idp: FakeProvider
) -> None:
    await _add_user(engine, "alice", "alice@acme.com")

    async with build_app().client() as client:
        await _password_login(client, "alice")
        query = await start(client, path="link")
        flow = (await session_of(client))[OAUTH_FLOW_KEY]
        await client.post("/admin/logout", follow_redirects=False)
        # The flow of the previous session, replayed by a signed-out browser.
        response = await client.get(
            "/admin/oauth/callback/google",
            params={"code": "c", "state": query["state"]},
            follow_redirects=False,
        )

    assert isinstance(flow["link_user_id"], int)
    assert response.status_code == 400
    assert await _tokens(engine) == []


async def test_link_flow_needs_the_user_who_started_it(build_app, engine: AsyncEngine) -> None:
    app = build_app()
    request = SimpleNamespace(session={})

    class Anonymous:
        async def get_current_user(self, request: object) -> None:
            return None

    views = OAuthViews(app.backend, Anonymous(), app.admin.templates)
    flow = {"provider": "google", "link_user_id": 7}

    from hyperadmin.auth.exceptions import OAuthStateError

    with pytest.raises(OAuthStateError, match="no longer signed in"):
        await views._finish_link(request, flow, {}, {}, "/admin")  # type: ignore[arg-type]
    assert await _tokens(engine) == []


# ── Unlink ────────────────────────────────────────────────────────────────


async def test_unlinking_an_oauth_identity_from_settings(
    build_app, engine: AsyncEngine, idp: FakeProvider
) -> None:
    """
    Scenario: unlinking an OAuth identity from settings
      Given alice has an OAuthToken row for provider="google"
      And   alice has a usable password (i.e. is not OAuth-only)
      When  alice POSTs /admin/oauth/unlink/google
      Then  the OAuthToken row is deleted
      And   alice can still log in with password
    """
    await _add_user(engine, "alice", "alice@acme.com")
    idp.userinfo = (200, {"sub": "g-1", "email": "alice@gmail.com"})
    app = build_app()

    async with app.client() as client:
        await _password_login(client, "alice")
        await sign_in(client, path="link")
        response = await client.post("/admin/oauth/unlink/google", follow_redirects=False)
        page = await client.get("/admin/oauth/settings")
        again = await client.post("/admin/oauth/unlink/google", follow_redirects=False)
        unknown = await client.post("/admin/oauth/unlink/unknown", follow_redirects=False)

    assert response.status_code == 303
    assert response.headers["location"] == "/admin/oauth/settings"
    assert "Google account unlinked." in page.text
    assert await _tokens(engine) == []
    assert again.status_code == 404
    assert unknown.status_code == 404
    async with app.client() as fresh:
        await _password_login(fresh, "alice")
        assert (await fresh.get("/admin/")).status_code == 200


async def test_cannot_unlink_the_only_auth_method(build_app, engine: AsyncEngine) -> None:
    """
    Scenario: cannot unlink the only auth method
      Given alice has an OAuthToken for provider="google"
      And   alice has no usable password (provisioned via OAuth)
      When  alice POSTs /admin/oauth/unlink/google
      Then  the response is 400 Bad Request
      And   the body contains "Set a password before unlinking your only sign-in method"
    """
    async with build_app().client() as client:
        await sign_in(client)
        response = await client.post("/admin/oauth/unlink/google", follow_redirects=False)

    assert response.status_code == 400
    assert "Set a password before unlinking your only sign-in method" in response.text
    assert len(await _tokens(engine)) == 1


async def test_unlinking_the_provider_of_the_session_drops_its_marker(
    build_app, engine: AsyncEngine, idp: FakeProvider
) -> None:
    async with build_app().client() as client:
        await sign_in(client)
        idp.userinfo = (200, {"id": 42, "email": "alice@users.noreply.github.com"})
        await sign_in(client, "github", path="link")
        kept = await client.post("/admin/oauth/unlink/github", follow_redirects=False)
        with_marker = await session_of(client)
        await sign_in(client, "github", path="link")
        dropped = await client.post("/admin/oauth/unlink/google", follow_redirects=False)
        without_marker = await session_of(client)

    assert kept.status_code == 303
    assert with_marker[OAUTH_SESSION_KEY]["provider"] == "google"
    assert dropped.status_code == 303
    assert OAUTH_SESSION_KEY not in without_marker
    assert without_marker["user_id"] == with_marker["user_id"]
    assert [row.provider for row in await _tokens(engine)] == ["github"]


# ── Wiring ────────────────────────────────────────────────────────────────


def _admin(**kwargs):
    from fastapi import FastAPI

    from hyperadmin.core.app import Admin
    from hyperadmin.core.registry import site
    from hyperadmin.core.settings import HyperAdminSettings

    site._registry.clear()
    settings = kwargs.pop("settings", None) or HyperAdminSettings(
        secret_key=SECRET_KEY, oauth_token_secret=TOKEN_SECRET
    )
    return Admin(FastAPI(), settings=settings, **kwargs)


async def test_oauth_without_a_token_secret_refuses_to_start(
    engine: AsyncEngine, backend: OAuthBackend, monkeypatch: pytest.MonkeyPatch
) -> None:
    from hyperadmin.auth.session import SessionAuthBackend
    from hyperadmin.core.settings import HyperAdminSettings

    monkeypatch.delenv("HYPERADMIN_OAUTH_TOKEN_SECRET", raising=False)

    for secret in (None, "  "):
        with pytest.raises(OAuthConfigError, match="HYPERADMIN_OAUTH_TOKEN_SECRET"):
            _admin(
                engine=engine,
                settings=HyperAdminSettings(secret_key=SECRET_KEY, oauth_token_secret=secret),
                auth_backend=SessionAuthBackend(engine=engine),
                oauth_backend=backend,
            )


async def test_oauth_needs_the_built_in_auth_backend(
    engine: AsyncEngine, backend: OAuthBackend
) -> None:
    with pytest.raises(ValueError, match=r"needs Admin\(auth_backend"):
        _admin(engine=engine, oauth_backend=backend)


async def test_oauth_and_bring_your_own_auth_are_mutually_exclusive(
    engine: AsyncEngine, backend: OAuthBackend
) -> None:
    from hyperadmin.auth.bridge import ExternalAuth

    async def get_user() -> None:
        return None

    with pytest.raises(OAuthConfigError, match="mutually exclusive"):
        _admin(engine=engine, auth=ExternalAuth(get_user=get_user), oauth_backend=backend)


async def test_admin_binds_its_database_to_the_backend(engine: AsyncEngine) -> None:
    from hyperadmin.auth.session import SessionAuthBackend

    oauth = OAuthBackend(providers={"google": google_provider("id", "secret")})

    admin = _admin(
        engine=engine, auth_backend=SessionAuthBackend(engine=engine), oauth_backend=oauth
    )

    assert admin.oauth_backend is oauth
    assert oauth.engine is engine


async def test_admin_without_oauth_has_no_oauth_routes(engine: AsyncEngine) -> None:
    """
    Scenario: an admin without OAuth is unchanged
      Given Admin is built without oauth_backend
      When  a signed-out visitor requests an OAuth path
      Then  the path is not public and no OAuth route exists
    """
    from hyperadmin.auth.session import SessionAuthBackend

    admin = _admin(engine=engine, auth_backend=SessionAuthBackend(engine=engine))
    admin.mount("/admin")
    transport = httpx.ASGITransport(app=admin.app)

    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/admin/oauth/authorize/google", follow_redirects=False)

    assert admin.oauth_backend is None
    assert response.status_code == 302
    assert response.headers["location"] == "/admin/login"
    assert not [route for route in admin.router.routes if "oauth" in getattr(route, "path", "")]


def test_admin_without_oauth_imports_no_oauth_code() -> None:
    code = """
import sys
from fastapi import FastAPI
from sqlalchemy.ext.asyncio import create_async_engine
from hyperadmin import Admin, HyperAdminSettings
from hyperadmin.auth.session import SessionAuthBackend

engine = create_async_engine("sqlite+aiosqlite:///:memory:")
admin = Admin(
    FastAPI(),
    engine=engine,
    settings=HyperAdminSettings(secret_key="s3cret-for-the-test"),
    auth_backend=SessionAuthBackend(engine=engine),
)
admin.mount("/admin")
loaded = [
    name for name in sys.modules
    if name.startswith(("httpx_oauth", "cryptography"))
    or name in ("hyperadmin.auth.oauth.backend", "hyperadmin.auth.oauth.views",
                "hyperadmin.auth.oauth.wiring")
]
print(loaded)
"""
    result = subprocess.run(
        [sys.executable, "-c", code], check=False, capture_output=True, text=True
    )

    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == "[]"
