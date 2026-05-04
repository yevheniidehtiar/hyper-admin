"""Minimal HyperAdmin app with MFA wired for E2E testing (C3-C, #488).

Started by the ``mfa_base_url`` fixture via uvicorn subprocess. Seeds two
users on startup:

* ``alice / secret`` — ``mfa_enabled=True`` (full two-factor flow)
* ``bob / secret``   — ``mfa_enabled=False`` (single-factor reference)

The OTP service uses an in-process ``_CapturingSender`` whose latest
issued code is exposed through test-only HTTP endpoints (``/_test/...``).
This is the only practical way for the Playwright client to read a code
that lives in the server process — there is no real email backend.

For the rate-limit scenario the service is configured with a tight
``rate_limit=(2, 3600)``: two OTP issuances per hour is enough budget
for the happy-path flows (one at login, one resend) while making the
boundary deterministic — every test that needs a fresh code starts by
resetting the captured history via ``/_test/reset_otp_state``.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone
from typing import Any

from fastapi import FastAPI
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlmodel import SQLModel, select
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from hyperadmin.auth.backend import hash_password
from hyperadmin.auth.models import User
from hyperadmin.auth.otp import OTP_SESSION_KEY, EmailOTPService
from hyperadmin.auth.permissions import (
    ModelPermissionChecker,
    PermissionSyncService,
)
from hyperadmin.auth.session import SessionAuthBackend
from hyperadmin.core.app import Admin
from hyperadmin.core.settings import HyperAdminSettings

engine = create_async_engine(
    "sqlite+aiosqlite:///:memory:",
    connect_args={"check_same_thread": False},
)


class _CapturingSender:
    """Test-only email sender: stores the most recent (email, code) pair."""

    def __init__(self) -> None:
        self.calls: list[tuple[str, str]] = []

    async def __call__(self, email: str, code: str) -> None:
        self.calls.append((email, code))

    def latest_for(self, email: str) -> str | None:
        for sent_email, sent_code in reversed(self.calls):
            if sent_email == email:
                return sent_code
        return None

    def reset(self) -> None:
        self.calls.clear()


_SENDER = _CapturingSender()


async def _seed_users() -> None:
    """Create alice (MFA on) and bob (MFA off) idempotently."""
    async with AsyncSession(engine) as session:
        for username, mfa in (("alice", True), ("bob", False)):
            existing = (
                await session.execute(select(User).where(User.username == username))
            ).scalar_one_or_none()
            if existing is None:
                session.add(
                    User(
                        username=username,
                        email=f"{username}@example.com",
                        password_hash=hash_password("secret"),
                        is_superuser=True,
                        mfa_enabled=mfa,
                        mfa_method="email" if mfa else None,
                    )
                )
        await session.commit()


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
    async with engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.create_all)
    await _seed_users()
    yield


app = FastAPI(lifespan=lifespan)

backend = SessionAuthBackend(engine=engine)
# rate_limit=(2, 3600): two issuances per hour is enough budget for the
# happy-path scenarios that issue exactly one code, and makes the
# rate-limit scenario hit on the third call within the same session.
otp_service = EmailOTPService(email_sender=_SENDER, rate_limit=(2, 3600))
settings = HyperAdminSettings(create_tables=False, secret_key="e2e-mfa-test-secret")

admin = Admin(
    app,
    engine=engine,
    settings=settings,
    auth_backend=backend,
    permission_checker=ModelPermissionChecker(engine=engine),
    permission_registry=PermissionSyncService(engine=engine),
    otp_service=otp_service,
)
admin.mount(path="/admin")


# ── Test-only helper endpoints ────────────────────────────────────────────
#
# All under ``/_test/`` so they are clearly out of scope for production-style
# E2E flows. They are mounted directly on the FastAPI app (NOT on the admin
# router) so they sit OUTSIDE the auth middleware's ``/admin`` prefix and
# stay reachable from anonymous and partial-auth Playwright contexts alike.


async def _reset_otp_state(request: Request) -> Response:
    """Wipe captured codes + clear any session OTP/partial-auth state."""
    _SENDER.reset()
    request.session.clear()
    return Response(status_code=204)


async def _latest_code(request: Request) -> JSONResponse:
    """Return the latest OTP code captured for ``?email=...``.

    Lets the Playwright test read the OTP that the server-side service
    just generated — the only way to drive the verify form deterministically
    when there is no real email backend.
    """
    email = request.query_params.get("email", "")
    code = _SENDER.latest_for(email)
    return JSONResponse({"email": email, "code": code})


async def _backdate_session_otp(request: Request) -> Response:
    """Backdate the current session's OTP entry past its TTL.

    Used by the "expired OTP" scenario. Returns 404 if the session has no
    pending OTP entry — the caller must complete the password step first.
    """
    entry = request.session.get(OTP_SESSION_KEY)
    if not isinstance(entry, dict):
        return Response(status_code=404)
    stale = (datetime.now(tz=timezone.utc) - timedelta(hours=1)).isoformat()
    entry["issued_at"] = stale
    request.session[OTP_SESSION_KEY] = entry
    return Response(status_code=204)


def _register_test_routes(_app: FastAPI) -> None:
    # Use the lower-level Starlette router to keep these out of FastAPI's
    # OpenAPI surface and avoid the response-model machinery; the helpers
    # take a single ``Request`` and return ``Response`` objects.
    _app.router.add_route("/_test/reset_otp_state", _reset_otp_state, methods=["POST"])
    _app.router.add_route("/_test/latest_code", _latest_code, methods=["GET"])
    _app.router.add_route("/_test/backdate_session_otp", _backdate_session_otp, methods=["POST"])


_register_test_routes(app)


# Re-export for completeness; the fixture imports ``app`` only.
_ = (Any,)
