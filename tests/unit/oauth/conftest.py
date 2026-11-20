"""Shared fixtures of the OAuth unit tests: a fake identity provider, a database, an app."""

from __future__ import annotations

from collections.abc import AsyncIterator, Callable, Iterator
from dataclasses import dataclass
from typing import Any
from urllib.parse import parse_qs, urlsplit

import httpx
import pytest
from cryptography.fernet import Fernet
from fastapi import FastAPI
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine
from sqlmodel import SQLModel
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from hyperadmin.auth.oauth.backend import OAuthBackend
from hyperadmin.auth.oauth.providers import github_provider, google_provider
from hyperadmin.auth.oauth.session import OAUTH_FLOW_KEY, OAUTH_SESSION_KEY
from hyperadmin.auth.oauth.tokens import configure_token_cipher
from tests.conftest import with_csrf

SECRET_KEY = "test-secret-oauth"
TOKEN_SECRET = Fernet.generate_key().decode()


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
        #: Number of calls that fail with ``network_error`` before answers resume.
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


class CapturingSender:
    """Records the ``(email, code)`` of every OTP the MFA service sends."""

    def __init__(self) -> None:
        self.calls: list[tuple[str, str]] = []
        self.error: Exception | None = None

    async def __call__(self, email: str, code: str) -> None:
        if self.error is not None:
            raise self.error
        self.calls.append((email, code))


@dataclass
class OAuthApp:
    """A mounted admin with OAuth, plus what a test needs to drive it."""

    app: FastAPI
    admin: Any
    backend: OAuthBackend
    sender: CapturingSender

    def client(self) -> httpx.AsyncClient:
        transport = httpx.ASGITransport(app=self.app)
        return with_csrf(httpx.AsyncClient(transport=transport, base_url="http://test"), SECRET_KEY)


async def start(
    client: httpx.AsyncClient, provider: str = "google", path: str = "authorize"
) -> dict[str, str]:
    """Hit the authorize (or link) route and return the provider URL's query."""
    response = await client.get(f"/admin/oauth/{path}/{provider}", follow_redirects=False)
    assert response.status_code == 302, response.text
    query = parse_qs(urlsplit(response.headers["location"]).query)
    return {key: values[0] for key, values in query.items()}


async def sign_in(
    client: httpx.AsyncClient, provider: str = "google", path: str = "authorize"
) -> httpx.Response:
    """Run authorize (or link) and the provider callback with a valid state."""
    query = await start(client, provider, path)
    return await client.get(
        f"/admin/oauth/callback/{provider}",
        params={"code": "code-1", "state": query["state"]},
        follow_redirects=False,
    )


async def session_of(client: httpx.AsyncClient) -> dict[str, Any]:
    """Return the admin session of ``client`` (through a test-only public route)."""
    return (await client.get("/admin/login/_test/session")).json()


@pytest.fixture(autouse=True)
def _registry() -> Iterator[None]:
    """Restore the global model registry: a mounted admin registers the auth models."""
    from hyperadmin.core.registry import site

    saved = dict(site._registry)
    yield
    site._registry = saved


@pytest.fixture(autouse=True)
def _token_cipher() -> Iterator[None]:
    configure_token_cipher(TOKEN_SECRET)
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


@pytest.fixture
def build_app(engine: AsyncEngine, backend: OAuthBackend) -> Callable[..., OAuthApp]:
    """Build a mounted ``Admin`` with built-in auth and OAuth.

    Keyword arguments: ``mfa=True`` wires an OTP service, ``oauth=<backend>``
    replaces the default backend, everything else goes to ``HyperAdminSettings``.
    """

    def build(*, mfa: bool = False, oauth: OAuthBackend | None = None, **settings: Any) -> OAuthApp:
        from hyperadmin.auth.otp import EmailOTPService
        from hyperadmin.auth.session import SessionAuthBackend
        from hyperadmin.core.app import Admin
        from hyperadmin.core.registry import site
        from hyperadmin.core.settings import HyperAdminSettings

        site._registry.clear()
        app = FastAPI()
        sender = CapturingSender()
        oauth_backend = oauth or backend
        admin = Admin(
            app,
            engine=engine,
            settings=HyperAdminSettings(
                create_tables=False,
                secret_key=SECRET_KEY,
                oauth_token_secret=TOKEN_SECRET,
                **settings,
            ),
            auth_backend=SessionAuthBackend(engine=engine),
            otp_service=EmailOTPService(email_sender=sender) if mfa else None,
            oauth_backend=oauth_backend,
        )
        admin.mount("/admin")

        async def dump_session(request: Request) -> Response:
            return JSONResponse(dict(request.session))

        async def backdate_flow(request: Request) -> Response:
            flow = dict(request.session[OAUTH_FLOW_KEY])
            flow["issued_at"] -= float(request.query_params["seconds"])
            request.session[OAUTH_FLOW_KEY] = flow
            return Response(status_code=204)

        async def expire_token(request: Request) -> Response:
            marker = dict(request.session[OAUTH_SESSION_KEY])
            marker["expires_at"] = float(request.query_params["at"])
            request.session[OAUTH_SESSION_KEY] = marker
            return Response(status_code=204)

        # Under /login: public, and inside the admin sub-app, where the session lives.
        router = admin.asgi_app.router
        router.add_route("/login/_test/session", dump_session, methods=["GET"])
        router.add_route("/login/_test/backdate", backdate_flow, methods=["GET"])
        router.add_route("/login/_test/expire", expire_token, methods=["GET"])
        return OAuthApp(app, admin, oauth_backend, sender)

    return build
