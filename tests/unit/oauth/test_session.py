"""OAuth keys in the admin session and the public paths of the auth middleware (#443)."""

from __future__ import annotations

from types import SimpleNamespace

import pytest
from starlette.requests import Request

from hyperadmin.auth.middleware import AuthenticationMiddleware
from hyperadmin.auth.oauth.session import (
    OAUTH_FLASH_KEY,
    OAUTH_SESSION_KEY,
    mark_oauth_session,
    pop_flash,
    read_oauth_session,
    set_flash,
)
from hyperadmin.auth.oauth.wiring import PUBLIC_PATHS


def test_marker_round_trips_for_its_own_user() -> None:
    session: dict = {}

    mark_oauth_session(session, user_id=7, provider="google", expires_at=1234.5)

    assert session[OAUTH_SESSION_KEY] == {
        "user_id": 7,
        "provider": "google",
        "expires_at": 1234.5,
    }
    assert read_oauth_session(session, user_id=7) == session[OAUTH_SESSION_KEY]


@pytest.mark.parametrize(
    ("session", "user_id"),
    [
        ({}, 7),
        ({OAUTH_SESSION_KEY: "google"}, 7),
        ({OAUTH_SESSION_KEY: {"user_id": 7}}, 7),
        ({OAUTH_SESSION_KEY: {"user_id": 7, "provider": 1}}, 7),
        ({OAUTH_SESSION_KEY: {"user_id": 7, "provider": "google"}}, 8),
        ({OAUTH_SESSION_KEY: {"user_id": None, "provider": "google"}}, None),
        (None, 7),
    ],
)
def test_marker_of_another_user_or_a_malformed_one_is_ignored(session, user_id) -> None:
    assert read_oauth_session(session, user_id=user_id) is None


def test_flash_is_shown_once() -> None:
    session: dict = {}
    request = SimpleNamespace(scope={"session": session})

    set_flash(session, "Session expired")
    first = pop_flash(request)  # type: ignore[arg-type]
    second = pop_flash(request)  # type: ignore[arg-type]

    assert first == {"message": "Session expired", "level": "info"}
    assert second is None
    assert OAUTH_FLASH_KEY not in session


def test_error_flash_keeps_its_level() -> None:
    session: dict = {}

    set_flash(session, "Nope", "error")

    assert pop_flash(SimpleNamespace(scope={"session": session})) == {  # type: ignore[arg-type]
        "message": "Nope",
        "level": "error",
    }


@pytest.mark.parametrize(
    "scope",
    [
        {},
        {"session": None},
        {"session": {OAUTH_FLASH_KEY: "plain string"}},
        {"session": {OAUTH_FLASH_KEY: {"message": 5}}},
    ],
)
def test_flash_is_absent_without_a_session_or_with_garbage(scope: dict) -> None:
    assert pop_flash(SimpleNamespace(scope=scope)) is None  # type: ignore[arg-type]


class _Backend:
    async def get_current_user(self, request: Request) -> None:
        return None


def _request(path: str) -> Request:
    return Request({"type": "http", "method": "GET", "path": path, "headers": [], "state": {}})


@pytest.mark.anyio
@pytest.mark.parametrize("path", ["/oauth/authorize/google", "/oauth/callback/github"])
async def test_oauth_sign_in_paths_are_public_only_when_configured(path: str) -> None:
    """
    Scenario: OAuth sign-in paths are public only with OAuth configured
      Given an admin with OAuth passes its public paths to the auth middleware
      When  a signed-out visitor requests an OAuth sign-in path
      Then  the request passes; without OAuth it is redirected to the login page
    """
    with_oauth = AuthenticationMiddleware(
        None, _Backend(), isolated=True, public_paths=PUBLIC_PATHS
    )
    without = AuthenticationMiddleware(None, _Backend(), isolated=True)

    passed = await with_oauth._authenticate(_request(path))
    redirected = await without._authenticate(_request(path))

    assert passed is None
    assert redirected is not None
    assert redirected.status_code == 302


@pytest.mark.anyio
@pytest.mark.parametrize("path", ["/oauth/settings", "/oauth/link/google", "/oauth/unlink/google"])
async def test_oauth_account_paths_stay_protected(path: str) -> None:
    middleware = AuthenticationMiddleware(
        None, _Backend(), isolated=True, public_paths=PUBLIC_PATHS
    )

    response = await middleware._authenticate(_request(path))

    assert response is not None
    assert response.status_code == 302
