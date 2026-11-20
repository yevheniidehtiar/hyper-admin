"""OAuth sign-in fixture app for E2E testing (#446, docs/specs/oauth-sso.md).

Started by the ``oauth_base_url`` fixture in ``tests/e2e/test_oauth_flow.py``. The admin
has built-in auth, MFA and one OAuth provider named ``google``, whose endpoints point at
a fake identity provider served by this same application under ``/_idp``:

* ``GET /_idp/authorize`` - the consent page: one "Continue as ..." button per known
  account. Choosing one redirects back to the admin callback with a code.
* ``POST /_idp/token`` - exchanges the code, checking the client credentials and the PKCE
  verifier against the challenge sent to ``/_idp/authorize``.
* ``GET /_idp/userinfo`` - the profile of the access token.

Accounts at the provider:

* ``newcomer@example.com`` - no admin user yet; signing in creates one.
* ``alice@example.com`` - linked to the seeded admin user ``alice``, who has MFA on.

The provider URLs need this server's own address, which the fixture passes as
``E2E_OAUTH_IDP_URL``.
"""

from __future__ import annotations

import os
import secrets
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from html import escape
from urllib.parse import urlencode

from cryptography.fernet import Fernet
from fastapi import FastAPI
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlmodel import SQLModel
from starlette.requests import Request
from starlette.responses import HTMLResponse, JSONResponse, RedirectResponse, Response

from hyperadmin.auth.backend import hash_password
from hyperadmin.auth.models import OAuthToken, User
from hyperadmin.auth.oauth.backend import OAuthBackend, pkce_challenge
from hyperadmin.auth.oauth.providers import OAuthProviderConfig
from hyperadmin.auth.otp import EmailOTPService
from hyperadmin.auth.session import SessionAuthBackend
from hyperadmin.core.app import Admin
from hyperadmin.core.settings import HyperAdminSettings

IDP_URL = os.environ.get("E2E_OAUTH_IDP_URL", "http://localhost:8000")
CLIENT_ID = "e2e-client-id"
CLIENT_SECRET = "e2e-client-secret"

#: Accounts the fake provider knows, by ``sub``.
ACCOUNTS: dict[str, dict[str, str]] = {
    "sub-newcomer": {"email": "newcomer@example.com", "name": "New Comer"},
    "sub-alice": {"email": "alice@example.com", "name": "Alice Liddell"},
}

engine = create_async_engine(
    "sqlite+aiosqlite:///:memory:", connect_args={"check_same_thread": False}
)

#: Authorization codes and access tokens the fake provider issued.
_codes: dict[str, dict[str, str]] = {}
_access_tokens: dict[str, str] = {}


async def _seed() -> None:
    """Create ``alice`` (MFA on) with her Google identity already linked."""
    async with AsyncSession(engine) as session:
        alice = User(
            username="alice",
            email="alice@example.com",
            password_hash=hash_password("secret"),
            is_superuser=True,
            mfa_enabled=True,
            mfa_method="email",
        )
        session.add(alice)
        await session.commit()
        await session.refresh(alice)
        session.add(
            OAuthToken(user_id=alice.id, provider="google", sub="sub-alice", access_token="seeded")
        )
        await session.commit()


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
    async with engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.create_all)
    await _seed()
    yield


async def _discard_code(email: str, code: str) -> None:
    """The MFA sender of this app: nobody reads the codes."""


app = FastAPI(lifespan=lifespan)

admin = Admin(
    app,
    engine=engine,
    settings=HyperAdminSettings(
        create_tables=False,
        secret_key="e2e-oauth-test-secret",
        oauth_token_secret=Fernet.generate_key().decode(),
    ),
    auth_backend=SessionAuthBackend(engine=engine),
    otp_service=EmailOTPService(email_sender=_discard_code),
    oauth_backend=OAuthBackend(
        providers={
            "google": OAuthProviderConfig(
                name="google",
                client_id=CLIENT_ID,
                client_secret=CLIENT_SECRET,
                scopes=("openid", "email", "profile"),
                authorize_url=f"{IDP_URL}/_idp/authorize",
                token_url=f"{IDP_URL}/_idp/token",
                userinfo_url=f"{IDP_URL}/_idp/userinfo",
                button_label="Google",
            )
        }
    ),
)
admin.mount(path="/admin")


# ── Fake identity provider ────────────────────────────────────────────────


async def _authorize(request: Request) -> Response:
    """Consent page: pick the account to continue with."""
    params = request.query_params
    account = params.get("account")
    if account is None:
        buttons = "".join(
            f'<p><a href="?{escape(urlencode({**params, "account": sub}))}">'
            f"Continue as {escape(profile['email'])}</a></p>"
            for sub, profile in ACCOUNTS.items()
        )
        page = f"<!doctype html><title>Fake IdP</title><h1>Choose an account</h1>{buttons}"
        return HTMLResponse(page)
    code = secrets.token_urlsafe(16)
    _codes[code] = {"sub": account, "challenge": params.get("code_challenge", "")}
    query = urlencode({"code": code, "state": params.get("state", "")})
    return RedirectResponse(f"{params['redirect_uri']}?{query}", status_code=302)


async def _token(request: Request) -> Response:
    form = await request.form()
    issued = _codes.pop(str(form.get("code")), None)
    valid = (
        issued is not None
        and form.get("client_id") == CLIENT_ID
        and form.get("client_secret") == CLIENT_SECRET
        and pkce_challenge(str(form.get("code_verifier", ""))) == issued["challenge"]
    )
    if not valid or issued is None:
        return JSONResponse({"error": "invalid_grant"}, status_code=400)
    access_token = secrets.token_urlsafe(16)
    _access_tokens[access_token] = issued["sub"]
    return JSONResponse(
        {"access_token": access_token, "refresh_token": "e2e-refresh", "expires_in": 3600}
    )


async def _userinfo(request: Request) -> Response:
    token = request.headers.get("authorization", "").removeprefix("Bearer ")
    sub = _access_tokens.get(token)
    if sub is None:
        return JSONResponse({"error": "invalid_token"}, status_code=401)
    return JSONResponse({"sub": sub, "email_verified": True, **ACCOUNTS[sub]})


app.router.add_route("/_idp/authorize", _authorize, methods=["GET"])
app.router.add_route("/_idp/token", _token, methods=["POST"])
app.router.add_route("/_idp/userinfo", _userinfo, methods=["GET"])
