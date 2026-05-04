"""End-to-end integration unit tests for the MFA login flow (C3-C, #488).

This file is the *full integration loop* for the email-OTP MFA feature:
``login`` → ``partial-auth`` → ``mfa/challenge`` → ``mfa/verify`` → full
session. The per-component tests live elsewhere and are deliberately NOT
duplicated here:

* ``tests/unit/test_email_otp_service.py``  — service-level (C1-D)
* ``tests/unit/test_mfa_challenge_view.py`` — view-level (C2-D)
* ``tests/unit/test_mfa_login_wiring.py``   — wiring + middleware (C3-A)

Each test composes the whole chain through the real ``Admin`` mount and the
real session middleware, so the assertions describe observable HTTP
behaviour (status codes, redirects, persisted DB state) rather than
implementation internals.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import TYPE_CHECKING, Any

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlmodel import SQLModel

if TYPE_CHECKING:
    from collections.abc import AsyncIterator
    from pathlib import Path

    from sqlalchemy.ext.asyncio import AsyncEngine
    from starlette.requests import Request

from hyperadmin.auth.backend import hash_password
from hyperadmin.auth.models import User
from hyperadmin.auth.otp import (
    OTP_SESSION_KEY,
    PARTIAL_AUTH_SESSION_KEY,
    EmailOTPService,
)


@pytest.fixture
async def async_engine(tmp_path: Path) -> AsyncIterator[AsyncEngine]:
    db_file = tmp_path / "test_mfa_login_flow.db"
    engine = create_async_engine(f"sqlite+aiosqlite:///{db_file}")
    async with engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.create_all)
    yield engine
    await engine.dispose()


class _CapturingSender:
    """Test double for ``EmailOTPService.email_sender``.

    Records the (email, code) pair of every successful issuance so tests can
    drive the verify step with the exact code that the service generated.
    """

    def __init__(self) -> None:
        self.calls: list[tuple[str, str]] = []

    async def __call__(self, email: str, code: str) -> None:
        self.calls.append((email, code))


def _make_alice_data() -> dict[str, Any]:
    # is_superuser=True mirrors the e2e test app fixture in tests/e2e/_mfa_app.py
    # so admin-route assertions stay consistent across unit and e2e suites.
    return {
        "username": "alice",
        "email": "alice@example.com",
        "password_hash": hash_password("secret"),
        "is_superuser": True,
        "mfa_enabled": True,
        "mfa_method": "email",
    }


@pytest.fixture
async def alice(async_engine: AsyncEngine) -> User:
    async with AsyncSession(async_engine) as session:
        user = User(**_make_alice_data())
        session.add(user)
        await session.commit()
        await session.refresh(user)
        return user


def _build_app(async_engine: AsyncEngine, sender: _CapturingSender) -> FastAPI:
    """Build a fully-wired Admin app with auth + MFA endpoints.

    Uses ``Admin.mount`` so login_view, mfa_challenge_view, mfa_verify_view,
    mfa_resend_view, and the partial-auth middleware gate are all in play —
    exactly what the production app sees.
    """
    from hyperadmin.auth.session import SessionAuthBackend
    from hyperadmin.core.app import Admin
    from hyperadmin.core.registry import site
    from hyperadmin.core.settings import HyperAdminSettings

    # Direct access to the private registry — no public reset() exists on
    # the site singleton today. If site grows one, swap this for it.
    site._registry.clear()

    app = FastAPI()
    backend = SessionAuthBackend(engine=async_engine)
    otp_service = EmailOTPService(email_sender=sender)
    Admin(
        app,
        engine=async_engine,
        settings=HyperAdminSettings(create_tables=False, secret_key="test-secret-c3c"),
        auth_backend=backend,
        otp_service=otp_service,
    ).mount("/admin")
    return app


# ─── Scenario: full login chain succeeds ──────────────────────────────────


class TestEndToEndLoginSucceeds:
    @pytest.mark.anyio
    async def test_login_then_verify_yields_full_session(self, async_engine, alice) -> None:
        """
        Scenario: full login chain succeeds for an MFA-enabled user
          Given alice has mfa_enabled=True
          When  she POSTs correct credentials and then the issued OTP
          Then  the response is a redirect to /admin/
          And   subsequent admin requests succeed (full auth granted)
        """
        # Given alice with MFA on, and a capturing sender wired into the app
        sender = _CapturingSender()
        app = _build_app(async_engine, sender)
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            # When she submits the correct password
            login_resp = await client.post(
                "/admin/login",
                data={"username": "alice", "password": "secret"},
                follow_redirects=False,
            )
            # Then she is redirected to the MFA challenge (partial auth)
            assert login_resp.status_code == 302
            assert login_resp.headers["location"].endswith("/admin/mfa/challenge")
            assert len(sender.calls) == 1
            sent_email, sent_code = sender.calls[0]
            assert sent_email == "alice@example.com"

            # When she POSTs the correct OTP
            verify_resp = await client.post(
                "/admin/mfa/verify",
                data={"code": sent_code},
                follow_redirects=False,
            )
            # Then she lands on /admin/ with a full session
            assert verify_resp.status_code == 302
            assert verify_resp.headers["location"].endswith("/admin/")

            # And follow-up admin requests are accepted (no MFA bounce)
            admin_resp = await client.get("/admin/", follow_redirects=False)
            assert admin_resp.status_code == 200


# ─── Scenario: wrong code keeps session in partial-auth ──────────────────


class TestWrongCodeKeepsPartialAuth:
    @pytest.mark.anyio
    async def test_wrong_otp_does_not_grant_full_session(self, async_engine, alice) -> None:
        """
        Scenario: wrong OTP keeps the user in partial-auth
          Given alice has just submitted her password
          When  she POSTs an incorrect OTP code
          Then  the verify view re-renders 200 with an error
          And   admin routes still bounce her to /mfa/challenge
        """
        # Given alice in the partial-auth state after a correct password
        sender = _CapturingSender()
        app = _build_app(async_engine, sender)
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            await client.post(
                "/admin/login",
                data={"username": "alice", "password": "secret"},
                follow_redirects=False,
            )
            assert len(sender.calls) == 1

            # When she submits a wrong code
            verify_resp = await client.post(
                "/admin/mfa/verify",
                data={"code": "000000"},
                follow_redirects=False,
            )
            # Then the challenge re-renders 200 with the "Invalid code" error
            assert verify_resp.status_code == 200
            assert "Invalid code" in verify_resp.text

            # And the partial-auth gate still redirects /admin/ to /mfa/challenge
            admin_resp = await client.get("/admin/", follow_redirects=False)
            assert admin_resp.status_code == 302
            assert admin_resp.headers["location"].endswith("/admin/mfa/challenge")


# ─── Scenario: middleware blocks partial-auth from regular admin routes ──


class TestPartialAuthBlocksAdminRoute:
    @pytest.mark.anyio
    async def test_partial_auth_user_redirected_from_user_list(self, async_engine, alice) -> None:
        """
        Scenario: middleware blocks a partial-auth session from /admin/user
          Given alice has only completed the password step
          When  she GETs /admin/user
          Then  the response redirects to /admin/mfa/challenge
        """
        # Given alice mid-MFA (has a partial-auth marker, no full session)
        sender = _CapturingSender()
        app = _build_app(async_engine, sender)
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            await client.post(
                "/admin/login",
                data={"username": "alice", "password": "secret"},
                follow_redirects=False,
            )

            # When she tries to reach a regular admin route
            resp = await client.get("/admin/user", follow_redirects=False)

            # Then she is bounced to the MFA challenge (NOT to /admin/login)
            assert resp.status_code == 302
            assert resp.headers["location"].endswith("/admin/mfa/challenge")


# ─── Scenario: resend invalidates the prior code ─────────────────────────


class TestResendInvalidatesPriorCode:
    @pytest.mark.anyio
    async def test_resend_overwrites_previous_otp(self, async_engine, alice) -> None:
        """
        Scenario: resend invalidates the previous OTP
          Given alice has a pending OTP from the login step
          When  she POSTs /admin/mfa/resend
          Then  a fresh code is issued to her email
          And   the prior code can no longer be used to verify
        """
        # Given alice mid-MFA with a pending OTP (the one issued at login)
        sender = _CapturingSender()
        app = _build_app(async_engine, sender)
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            await client.post(
                "/admin/login",
                data={"username": "alice", "password": "secret"},
                follow_redirects=False,
            )
            assert len(sender.calls) == 1
            old_code = sender.calls[0][1]

            # When she POSTs the resend endpoint
            resend_resp = await client.post("/admin/mfa/resend")
            # Then a NEW code is issued to her email (different from the first)
            assert resend_resp.status_code == 200
            assert len(sender.calls) == 2
            new_code = sender.calls[1][1]
            # And the two codes are distinct (overwhelmingly likely with 6
            # digits of entropy; if they happen to collide, force one retry).
            if old_code == new_code:
                resend_resp = await client.post("/admin/mfa/resend")
                assert resend_resp.status_code == 200
                assert len(sender.calls) == 3
                new_code = sender.calls[-1][1]
            assert new_code != old_code

            # And the OLD code now fails to verify (single active OTP per user)
            old_verify = await client.post(
                "/admin/mfa/verify",
                data={"code": old_code},
                follow_redirects=False,
            )
            assert old_verify.status_code == 200
            assert "Invalid code" in old_verify.text

            # And the NEW code completes login
            new_verify = await client.post(
                "/admin/mfa/verify",
                data={"code": new_code},
                follow_redirects=False,
            )
            assert new_verify.status_code == 302
            assert new_verify.headers["location"].endswith("/admin/")


# ─── Scenario: expired OTP surfaces the "expired" copy ───────────────────


class TestExpiredCodeIsRejectedDistinctly:
    @pytest.mark.anyio
    async def test_backdated_otp_renders_expired_message(self, async_engine, alice) -> None:
        """
        Scenario: an OTP older than its TTL is rejected with a distinct message
          Given alice has a pending OTP whose ``issued_at`` is older than the TTL
          When  she submits that code
          Then  the page re-renders 200 with an "expired" message and resend link
        """
        # Given alice in partial auth with a pending OTP, then we backdate it
        # by clearing the code from session and re-injecting via the verify
        # path: easier — we use the existing OTP entry directly via the
        # session-poking approach used by C2-D's view tests.
        from starlette.responses import Response  # runtime — Response() is constructed here

        from hyperadmin.auth.session import SessionAuthBackend
        from hyperadmin.core.app import Admin
        from hyperadmin.core.registry import site
        from hyperadmin.core.settings import HyperAdminSettings

        # Direct access to the private registry — no public reset() exists on
        # the site singleton today. If site grows one, swap this for it.
        site._registry.clear()

        app = FastAPI()
        backend = SessionAuthBackend(engine=async_engine)
        sender = _CapturingSender()
        otp_service = EmailOTPService(email_sender=sender)
        Admin(
            app,
            engine=async_engine,
            settings=HyperAdminSettings(create_tables=False, secret_key="test-secret-c3c-exp"),
            auth_backend=backend,
            otp_service=otp_service,
        ).mount("/admin")

        async def _backdate(request: Request) -> Response:
            entry = request.session.get(OTP_SESSION_KEY)
            if entry is None:
                return Response(status_code=404)
            stale = (datetime.now(tz=timezone.utc) - timedelta(hours=1)).isoformat()
            entry["issued_at"] = stale
            request.session[OTP_SESSION_KEY] = entry
            return Response(status_code=204)

        app.router.add_route("/_test/backdate-otp", _backdate, methods=["POST"])

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            # Given alice completes the password step
            await client.post(
                "/admin/login",
                data={"username": "alice", "password": "secret"},
                follow_redirects=False,
            )
            assert len(sender.calls) == 1
            issued_code = sender.calls[0][1]

            # And we artificially backdate the OTP entry past its TTL
            backdate_resp = await client.post("/_test/backdate-otp")
            assert backdate_resp.status_code == 204

            # When she submits the (now expired) code
            verify_resp = await client.post(
                "/admin/mfa/verify",
                data={"code": issued_code},
                follow_redirects=False,
            )
            # Then the response is 200 with a distinct "expired" message
            assert verify_resp.status_code == 200
            assert "expired" in verify_resp.text.lower()
            # And the resend affordance is still surfaced
            assert 'data-testid="mfa-resend-link"' in verify_resp.text


# Silence unused-import warnings: PARTIAL_AUTH_SESSION_KEY is documented in
# the module docstring but consumed only indirectly via the wired views.
_ = PARTIAL_AUTH_SESSION_KEY
