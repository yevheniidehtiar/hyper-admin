"""Shared fixtures of the OAuth unit tests: a fake identity provider and a database."""

from __future__ import annotations

from collections.abc import AsyncIterator, Iterator
from typing import Any
from urllib.parse import parse_qs

import httpx
import pytest
from cryptography.fernet import Fernet
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine
from sqlmodel import SQLModel

from hyperadmin.auth.oauth.backend import OAuthBackend
from hyperadmin.auth.oauth.providers import github_provider, google_provider
from hyperadmin.auth.oauth.tokens import configure_token_cipher


class FakeProvider:
    """An ``httpx`` transport handler that plays Google and GitHub.

    Every answer is a ``(status, json)`` pair a test may replace; ``requests``
    records what the backend sent.
    """

    def __init__(self) -> None:
        self.requests: list[httpx.Request] = []
        self.token: tuple[int, Any] = (
            200,
            {
                "access_token": "access-1",
                "refresh_token": "refresh-1",
                "expires_in": 3600,
                "scope": "openid email",
            },
        )
        self.refresh: tuple[int, Any] = (200, {"access_token": "access-2", "expires_in": 3600})
        self.userinfo: tuple[int, Any] = (
            200,
            {
                "sub": "abc123",
                "email": "alice@acme.com",
                "email_verified": True,
                "given_name": "Alice",
                "family_name": "Liddell",
            },
        )
        self.emails: tuple[int, Any] = (200, [])
        #: Raised instead of answering, to simulate an unreachable provider.
        self.network_error: Exception | None = None
        #: Number of refresh calls that fail with ``network_error`` before one succeeds.
        self.failures_left: int | None = None

    def form(self, index: int = -1) -> dict[str, str]:
        """Return the form body of a recorded request as a flat dict."""
        body = parse_qs(self.requests[index].content.decode())
        return {key: values[0] for key, values in body.items()}

    def calls(self, fragment: str) -> list[httpx.Request]:
        return [request for request in self.requests if fragment in str(request.url)]

    def _fail(self) -> bool:
        if self.network_error is None:
            return False
        if self.failures_left is None:
            return True
        if self.failures_left > 0:
            self.failures_left -= 1
            return True
        return False

    def __call__(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        if self._fail():
            assert self.network_error is not None
            raise self.network_error
        path = request.url.path
        if path.endswith("/emails"):
            status, payload = self.emails
        elif request.method == "GET":
            status, payload = self.userinfo
        elif b"grant_type=refresh_token" in request.content:
            status, payload = self.refresh
        else:
            status, payload = self.token
        if isinstance(payload, (dict, list)):
            return httpx.Response(status, json=payload)
        return httpx.Response(status, text=str(payload))


@pytest.fixture(autouse=True)
def _token_cipher() -> Iterator[None]:
    configure_token_cipher(Fernet.generate_key().decode())
    yield
    configure_token_cipher(None)


@pytest.fixture
async def engine(tmp_path) -> AsyncIterator[AsyncEngine]:
    import hyperadmin.auth.models  # noqa: F401 - registers the hyperadmin_* tables

    db = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'oauth.db'}")
    async with db.begin() as conn:
        await conn.run_sync(SQLModel.metadata.create_all)
    yield db
    await db.dispose()


@pytest.fixture
def idp() -> FakeProvider:
    return FakeProvider()


@pytest.fixture
def backend(engine: AsyncEngine, idp: FakeProvider) -> OAuthBackend:
    return OAuthBackend(
        providers={
            "google": google_provider("google-id", "google-secret"),
            "github": github_provider("github-id", "github-secret"),
        },
        engine=engine,
        transport=httpx.MockTransport(idp),
    )
