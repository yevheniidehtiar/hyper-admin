"""Token refresh middleware for OAuth sessions (#444, docs/specs/oauth-sso.md)."""

from __future__ import annotations

import time
from types import SimpleNamespace
from typing import Any

import httpx
import pytest
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession
from sqlmodel import select

from hyperadmin.auth.backend import hash_password
from hyperadmin.auth.exceptions import OAuthProviderError
from hyperadmin.auth.models import OAuthToken, User
from hyperadmin.auth.oauth.refresh import SESSION_EXPIRED_MESSAGE, OAuthRefreshMiddleware
from hyperadmin.auth.oauth.session import OAUTH_FLASH_KEY, OAUTH_SESSION_KEY
from tests.unit.oauth.conftest import FakeProvider, session_of, sign_in

pytestmark = pytest.mark.anyio

NOW = 1_000_000.0


class FakeBackend:
    """Stands in for ``OAuthBackend``: answers refresh calls from a script."""

    def __init__(self, *outcomes: Any) -> None:
        self.outcomes = list(outcomes)
        self.calls: list[tuple[str, int, float]] = []

    def provider(self, name: str) -> object | None:
        return object() if name == "google" else None

    async def refresh_token(self, provider: str, user_id: int, *, leeway: float) -> float | None:
        self.calls.append((provider, user_id, leeway))
        outcome = self.outcomes.pop(0)
        if isinstance(outcome, Exception):
            raise outcome
        return outcome


class Harness:
    def __init__(self, backend: FakeBackend) -> None:
        self.backend = backend
        self.passed: list[dict] = []
        self.slept: list[float] = []
        self.middleware = OAuthRefreshMiddleware(
            self._app, backend=backend, leeway_seconds=60, clock=lambda: NOW, sleep=self._sleep
        )

    async def _app(self, scope: dict, receive: Any, send: Any) -> None:
        self.passed.append(scope)

    async def _sleep(self, seconds: float) -> None:
        self.slept.append(seconds)

    async def request(self, session: Any, scope_type: str = "http") -> None:
        scope: dict[str, Any] = {"type": scope_type}
        if session is not None:
            scope["session"] = session
        await self.middleware(scope, None, None)  # type: ignore[arg-type]


def _session(expires_in: float | None = 30, **marker: Any) -> dict[str, Any]:
    expires_at = None if expires_in is None else NOW + expires_in
    return {
        "user_id": 7,
        OAUTH_SESSION_KEY: {"user_id": 7, "provider": "google", "expires_at": expires_at, **marker},
    }


def _hard() -> OAuthProviderError:
    return OAuthProviderError("google", "Token refresh failed", error_code="invalid_grant")


def _transient() -> OAuthProviderError:
    return OAuthProviderError("google", "provider unreachable", transient=True)


# ── Middleware logic ──────────────────────────────────────────────────────


async def test_near_expiry_token_is_refreshed_and_the_request_proceeds() -> None:
    """
    Scenario: token refresh middleware refreshes near-expiry tokens
      Given alice has an OAuthToken with expires_at in 30 seconds
      When  alice issues an authenticated request
      Then  the middleware exchanges the refresh_token for a new access token
      And   the session marker carries the new expires_at
      And   the original request proceeds normally
    """
    harness = Harness(FakeBackend(NOW + 3600))
    session = _session(30, retry_at=NOW - 1)

    await harness.request(session)

    assert harness.backend.calls == [("google", 7, 60)]
    assert session[OAUTH_SESSION_KEY] == {
        "user_id": 7,
        "provider": "google",
        "expires_at": NOW + 3600,
    }
    assert len(harness.passed) == 1
    assert harness.slept == []


async def test_refresh_hard_failure_clears_the_session() -> None:
    """
    Scenario: token refresh hard failure clears the session
      Given alice's refresh_token has been revoked at the IdP
      When  the middleware attempts a refresh and the IdP returns 400 invalid_grant
      Then  the user's session is cleared
      And   a "Session expired" message is left for the login page
    """
    harness = Harness(FakeBackend(_hard()))
    session = _session(-5)

    await harness.request(session)

    assert session == {OAUTH_FLASH_KEY: {"message": SESSION_EXPIRED_MESSAGE, "level": "info"}}
    assert len(harness.backend.calls) == 1
    assert len(harness.passed) == 1


@pytest.mark.parametrize(
    "session",
    [
        None,
        "not a dict",
        {},
        {"user_id": 7},
        {OAUTH_SESSION_KEY: {"user_id": 7, "provider": "google", "expires_at": NOW}},
        {"user_id": 8, OAUTH_SESSION_KEY: {"user_id": 7, "provider": "google", "expires_at": NOW}},
        _session(3600),
        _session(None),
    ],
)
async def test_sessions_with_nothing_to_refresh_are_left_alone(session: Any) -> None:
    """
    Scenario: non-OAuth session users are unaffected
      Given user bob logged in via username/password (no OAuth marker)
      When  bob makes an authenticated request
      Then  no token refresh logic executes
    """
    harness = Harness(FakeBackend())
    before = dict(session) if isinstance(session, dict) else session

    await harness.request(session)

    assert harness.backend.calls == []
    assert session == before
    assert len(harness.passed) == 1


async def test_non_http_scopes_pass_through() -> None:
    harness = Harness(FakeBackend())

    await harness.request(_session(-5), scope_type="websocket")

    assert harness.backend.calls == []
    assert len(harness.passed) == 1


async def test_network_failure_is_retried_once() -> None:
    harness = Harness(FakeBackend(_transient(), NOW + 3600))
    session = _session(30)

    await harness.request(session)

    assert len(harness.backend.calls) == 2
    assert harness.slept == [1.0]
    assert session[OAUTH_SESSION_KEY]["expires_at"] == NOW + 3600


async def test_second_network_failure_lets_the_request_proceed_and_backs_off() -> None:
    harness = Harness(FakeBackend(_transient(), _transient()))
    session = _session(30)

    await harness.request(session)
    await harness.request(session)

    assert len(harness.backend.calls) == 2
    assert session["user_id"] == 7
    assert session[OAUTH_SESSION_KEY]["expires_at"] == NOW + 30
    assert session[OAUTH_SESSION_KEY]["retry_at"] == NOW + 30.0
    assert len(harness.passed) == 2


async def test_hard_failure_on_the_retry_clears_the_session() -> None:
    harness = Harness(FakeBackend(_transient(), _hard()))
    session = _session(30)

    await harness.request(session)

    assert "user_id" not in session
    assert OAUTH_FLASH_KEY in session


async def test_token_without_refresh_token_stops_being_checked() -> None:
    harness = Harness(FakeBackend(None))
    session = _session(30)

    await harness.request(session)
    await harness.request(session)

    assert len(harness.backend.calls) == 1
    assert session[OAUTH_SESSION_KEY]["expires_at"] is None
    assert session["user_id"] == 7


async def test_marker_of_a_removed_provider_is_dropped() -> None:
    harness = Harness(FakeBackend())
    session = _session(30, provider="okta")

    await harness.request(session)

    assert session == {"user_id": 7}
    assert harness.backend.calls == []


# ── Mounted admin ─────────────────────────────────────────────────────────


async def _tokens(engine: AsyncEngine) -> list[OAuthToken]:
    async with AsyncSession(engine) as session:
        return list((await session.execute(select(OAuthToken))).scalars())


async def _make_superuser(engine: AsyncEngine) -> None:
    async with AsyncSession(engine) as session:
        user = (await session.execute(select(User))).scalar_one()
        user.is_superuser = True
        await session.commit()


async def test_expired_oauth_token_is_auto_refreshed(
    build_app, engine: AsyncEngine, idp: FakeProvider
) -> None:
    """
    Scenario: expired OAuth token is auto-refreshed
      Given user alice's Google token expires within the leeway
      And   a valid refresh_token exists
      When  alice makes any authenticated request
      Then  the token is refreshed transparently and the request proceeds
    """
    idp.token = (200, {"access_token": "access-1", "refresh_token": "refresh-1", "expires_in": 30})

    async with build_app().client() as client:
        await sign_in(client)
        await _make_superuser(engine)
        response = await client.get("/admin/", follow_redirects=False)
        refreshes = len(idp.calls("/token")) - 1
        expires_at = (await session_of(client))[OAUTH_SESSION_KEY]["expires_at"]
        await client.get("/admin/", follow_redirects=False)

    assert response.status_code == 200
    assert refreshes == 1
    assert idp.form(-1)["grant_type"] == "refresh_token"
    assert expires_at > time.time() + 3000
    (row,) = await _tokens(engine)
    assert row.access_token == "access-2"
    # The token is fresh now: the second request did not call the provider again.
    assert len(idp.calls("/token")) == 2


async def test_refresh_failure_logs_the_user_out(
    build_app, engine: AsyncEngine, idp: FakeProvider
) -> None:
    """
    Scenario: refresh failure logs user out
      Given user alice's refresh_token is revoked at Google
      When  alice makes an authenticated request with an expired token
      Then  alice is logged out and redirected to /admin/login
      And   the login page shows a "Session expired" message once
    """
    idp.token = (200, {"access_token": "access-1", "refresh_token": "refresh-1", "expires_in": 30})
    idp.refresh = (400, {"error": "invalid_grant"})

    async with build_app().client() as client:
        await sign_in(client)
        response = await client.get("/admin/", follow_redirects=False)
        login = await client.get("/admin/login")
        again = await client.get("/admin/login")
        session = await session_of(client)

    assert response.status_code == 302
    assert response.headers["location"] == "/admin/login"
    assert 'data-testid="login-notice"' in login.text
    assert "Session expired. Please sign in again." in login.text
    assert "Session expired" not in again.text
    assert "user_id" not in session


async def test_non_oauth_session_users_are_unaffected(
    build_app, engine: AsyncEngine, idp: FakeProvider
) -> None:
    """
    Scenario: non-OAuth session users are unaffected
      Given user bob logged in via username/password (no OAuthToken)
      When  bob makes an authenticated request
      Then  no token refresh logic executes
    """
    async with AsyncSession(engine) as session:
        session.add(
            User(
                username="bob",
                email="bob@acme.com",
                password_hash=hash_password("secret"),
                is_superuser=True,
            )
        )
        await session.commit()

    async with build_app().client() as client:
        await client.post(
            "/admin/login", data={"username": "bob", "password": "secret"}, follow_redirects=False
        )
        response = await client.get("/admin/", follow_redirects=False)
        session_data = await session_of(client)

    assert response.status_code == 200
    assert OAUTH_SESSION_KEY not in session_data
    assert idp.requests == []


async def test_unreachable_provider_does_not_log_the_user_out(
    build_app, engine: AsyncEngine, idp: FakeProvider, monkeypatch: pytest.MonkeyPatch
) -> None:
    from hyperadmin.auth.oauth import refresh as refresh_module

    async def no_sleep(seconds: float) -> None:
        return None

    monkeypatch.setattr(refresh_module.asyncio, "sleep", no_sleep)
    idp.token = (200, {"access_token": "access-1", "refresh_token": "refresh-1", "expires_in": 30})
    app = build_app()

    async with app.client() as client:
        await sign_in(client)
        await _make_superuser(engine)
        idp.network_error = httpx.ConnectError("down")
        response = await client.get("/admin/", follow_redirects=False)
        marker = (await session_of(client))[OAUTH_SESSION_KEY]

    assert response.status_code == 200
    assert "retry_at" in marker
    assert SimpleNamespace(**marker).provider == "google"
