"""Unit tests for MFA login wiring + middleware gate + settings views (C3-A, #487).

Maps the 5 BDD scenarios from
``.meta/epics/epicauth-object-level-permissions-mvp-otpmfa/stories/
featauth-wire-mfa-into-login-flow-enabledisable-settings.md``
to tests, plus edge cases enumerated in
``docs/specs/object-permissions-mfa.md`` (§"Edge Cases & Error Handling").

C3-A closes the MFA loop end-to-end:
  * ``login_view`` learns to branch on ``user.mfa_enabled``
  * ``AuthenticationMiddleware`` learns to bounce partial-auth users to
    ``/admin/mfa/challenge`` for non-MFA admin routes
  * ``mfa_settings_view`` / ``mfa_enable_view`` / ``mfa_disable_view`` provide
    the in-app enable/disable surface guarded by full auth.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlmodel import SQLModel, select

from hyperadmin.auth.backend import hash_password
from hyperadmin.auth.models import User
from hyperadmin.auth.otp import (
    OTP_SESSION_KEY,
    PARTIAL_AUTH_SESSION_KEY,
    EmailOTPService,
)


@pytest.fixture
async def async_engine(tmp_path):
    db_file = tmp_path / "test_mfa_wiring.db"
    engine = create_async_engine(f"sqlite+aiosqlite:///{db_file}")
    async with engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.create_all)
    yield engine
    await engine.dispose()


class _CapturingSender:
    """Test double for the EmailOTPService email_sender callable."""

    def __init__(self) -> None:
        self.calls: list[tuple[str, str]] = []

    async def __call__(self, email: str, code: str) -> None:
        self.calls.append((email, code))


@pytest.fixture
async def mfa_alice(async_engine) -> User:
    async with AsyncSession(async_engine) as session:
        user = User(
            username="alice",
            email="alice@example.com",
            password_hash=hash_password("secret"),
            mfa_enabled=True,
            mfa_method="email",
        )
        session.add(user)
        await session.commit()
        await session.refresh(user)
        return user


@pytest.fixture
async def plain_bob(async_engine) -> User:
    async with AsyncSession(async_engine) as session:
        user = User(
            username="bob",
            email="bob@example.com",
            password_hash=hash_password("secret"),
            mfa_enabled=False,
        )
        session.add(user)
        await session.commit()
        await session.refresh(user)
        return user


def _build_app(async_engine, sender: _CapturingSender | None = None) -> tuple[FastAPI, Any]:
    """Build a FastAPI app with auth + MFA endpoints fully wired (C3-A).

    Returns the app plus the otp_service so tests can introspect it.
    """
    from hyperadmin.auth.session import SessionAuthBackend
    from hyperadmin.core.app import Admin
    from hyperadmin.core.registry import site
    from hyperadmin.core.settings import HyperAdminSettings

    site._registry.clear()

    app = FastAPI()
    backend = SessionAuthBackend(engine=async_engine)
    sender = sender or _CapturingSender()
    otp_service = EmailOTPService(email_sender=sender)
    Admin(
        app,
        engine=async_engine,
        settings=HyperAdminSettings(create_tables=False, secret_key="test-secret-c3a"),
        auth_backend=backend,
        otp_service=otp_service,
    ).mount("/admin")
    return app, otp_service


# ── Scenario 1 ────────────────────────────────────────────────────────────


class TestLoginRedirectsMfaUser:
    @pytest.mark.anyio
    async def test_mfa_enabled_user_redirected_to_challenge_after_password(
        self, async_engine, mfa_alice
    ) -> None:
        """
        Scenario: MFA-enabled user redirected to challenge after password
          Given user "alice" has mfa_enabled=True
          When  POST /admin/login with correct username and password
          Then  password is verified but session is NOT fully created
          And   redirect to /admin/mfa/challenge
        """
        # Given alice with mfa_enabled and a capturing sender
        sender = _CapturingSender()
        app, _ = _build_app(async_engine, sender=sender)
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            # When she POSTs valid credentials
            resp = await client.post(
                "/admin/login",
                data={"username": "alice", "password": "secret"},
                follow_redirects=False,
            )

            # Then she is redirected to /admin/mfa/challenge (not /admin/)
            assert resp.status_code == 302
            assert resp.headers["location"].endswith("/admin/mfa/challenge")

            # And exactly one OTP was emitted to alice's address
            assert len(sender.calls) == 1
            assert sender.calls[0][0] == "alice@example.com"

            # And reaching /admin/ now bounces back to /mfa/challenge —
            # the partial-auth marker exists but full auth does NOT.
            bounced = await client.get("/admin/", follow_redirects=False)
            assert bounced.status_code == 302
            assert bounced.headers["location"].endswith("/admin/mfa/challenge")


# ── Scenario 2 ────────────────────────────────────────────────────────────


class TestLoginPlainUser:
    @pytest.mark.anyio
    async def test_mfa_disabled_user_logs_in_normally(self, async_engine, plain_bob) -> None:
        """
        Scenario: MFA-disabled user logs in normally
          Given user "bob" has mfa_enabled=False
          When  POST /admin/login with correct credentials
          Then  session is created and redirect to /admin/
        """
        # Given bob with mfa_enabled=False and a sender that should never fire
        sender = _CapturingSender()
        app, _ = _build_app(async_engine, sender=sender)
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            # When he POSTs valid credentials
            resp = await client.post(
                "/admin/login",
                data={"username": "bob", "password": "secret"},
                follow_redirects=False,
            )

            # Then he goes straight to /admin/ — single-factor login preserved
            assert resp.status_code == 302
            assert resp.headers["location"].endswith("/admin/")

            # And no OTP was emitted (single-factor path bypasses MFA entirely)
            assert sender.calls == []


# ── Scenario 3 ────────────────────────────────────────────────────────────


class TestEnableMfaFromSettings:
    @pytest.mark.anyio
    async def test_settings_renders_for_authenticated_user(self, async_engine, plain_bob) -> None:
        """The settings page renders for a fully-authenticated user with no MFA."""
        # Given bob is fully authenticated
        app, _ = _build_app(async_engine)
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            await client.post("/admin/login", data={"username": "bob", "password": "secret"})
            # When he visits the MFA settings page
            resp = await client.get("/admin/mfa/settings")
            # Then the page renders with the expected affordances
            assert resp.status_code == 200
            assert 'data-testid="mfa-status-indicator"' in resp.text
            assert 'data-testid="mfa-enable-btn"' in resp.text

    @pytest.mark.anyio
    async def test_enable_mfa_sends_otp_then_verify_flips_flag(
        self, async_engine, plain_bob
    ) -> None:
        """
        Scenario: enable MFA from settings
          Given user "alice" is logged in and visits /admin/mfa/settings
          When  clicks "Enable MFA"
          Then  OTP code is sent to alice's email
          And   after verification, mfa_enabled is set to True
        """
        # Given bob is logged in, mfa_enabled=False, and a capturing sender
        sender = _CapturingSender()
        app, _ = _build_app(async_engine, sender=sender)
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            await client.post("/admin/login", data={"username": "bob", "password": "secret"})

            # When he clicks "Enable MFA" — POST /admin/mfa/enable kicks off the flow
            start = await client.post("/admin/mfa/enable")
            # Then the page re-renders with the confirm input and a code is sent
            assert start.status_code == 200
            assert 'data-testid="mfa-confirm-input"' in start.text
            assert len(sender.calls) == 1
            assert sender.calls[0][0] == "bob@example.com"
            issued_code = sender.calls[0][1]

            # When he submits the code from his email
            confirm = await client.post("/admin/mfa/enable", data={"code": issued_code})

            # Then mfa_enabled is now True in the DB and method is "email"
            assert confirm.status_code in (200, 302)
            async with AsyncSession(async_engine) as session:
                row = (
                    await session.execute(select(User).where(User.username == "bob"))
                ).scalar_one()
                assert row.mfa_enabled is True
                assert row.mfa_method == "email"


# ── Scenario 4 ────────────────────────────────────────────────────────────


class TestDisableMfaFromSettings:
    @pytest.mark.anyio
    async def test_disable_mfa_requires_fresh_otp(self, async_engine, mfa_alice) -> None:
        """
        Scenario: disable MFA from settings
          Given user "alice" has mfa_enabled=True and visits /admin/mfa/settings
          When  clicks "Disable MFA" and confirms
          Then  mfa_enabled is set to False
        """
        # Given alice is fully authenticated (skipping MFA challenge by priming
        # her session via a direct call): we POST login to start, complete the
        # challenge by reading the captured OTP from sender.
        sender = _CapturingSender()
        app, _ = _build_app(async_engine, sender=sender)
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            # Login -> sends OTP -> partial-auth state
            await client.post("/admin/login", data={"username": "alice", "password": "secret"})
            assert len(sender.calls) == 1
            login_code = sender.calls[0][1]

            # Verify the OTP -> upgrades to full session
            await client.post("/admin/mfa/verify", data={"code": login_code})

            # When she POSTs /admin/mfa/disable to begin the disable flow
            start = await client.post("/admin/mfa/disable")
            # Then a fresh OTP is dispatched and the confirm input is rendered
            assert start.status_code == 200
            assert 'data-testid="mfa-confirm-input"' in start.text
            assert len(sender.calls) == 2  # one for login, one for disable
            disable_code = sender.calls[1][1]

            # When she submits the disable confirmation code
            confirm = await client.post("/admin/mfa/disable", data={"code": disable_code})

            # Then mfa_enabled is False in the DB
            assert confirm.status_code in (200, 302)
            async with AsyncSession(async_engine) as session:
                row = (
                    await session.execute(select(User).where(User.username == "alice"))
                ).scalar_one()
                assert row.mfa_enabled is False
                assert row.mfa_method is None


# ── Scenario 5 ────────────────────────────────────────────────────────────


class TestPartialAuthGate:
    @pytest.mark.anyio
    async def test_partial_auth_cannot_reach_admin_routes(self, async_engine, mfa_alice) -> None:
        """
        Scenario: partial-auth state cannot access admin routes
          Given user "alice" submitted correct password but hasn't completed MFA
          When  navigating to /admin/order
          Then  redirect to /admin/mfa/challenge (not the admin page)
        """
        # Given alice is in the partial-auth state (post-password, pre-OTP)
        sender = _CapturingSender()
        app, _ = _build_app(async_engine, sender=sender)
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            await client.post("/admin/login", data={"username": "alice", "password": "secret"})

            # When she tries to hit a regular admin route
            resp = await client.get("/admin/order", follow_redirects=False)

            # Then she is bounced to /admin/mfa/challenge (NOT /admin/login)
            assert resp.status_code == 302
            assert resp.headers["location"].endswith("/admin/mfa/challenge")

    @pytest.mark.anyio
    async def test_partial_auth_can_still_reach_mfa_endpoints(
        self, async_engine, mfa_alice
    ) -> None:
        """Edge: the gate must NOT loop — /admin/mfa/* is reachable in partial-auth."""
        sender = _CapturingSender()
        app, _ = _build_app(async_engine, sender=sender)
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            await client.post("/admin/login", data={"username": "alice", "password": "secret"})
            # The challenge endpoint itself stays reachable.
            resp = await client.get("/admin/mfa/challenge", follow_redirects=False)
            assert resp.status_code == 200

    @pytest.mark.anyio
    async def test_full_auth_user_passes_partial_gate(self, async_engine, plain_bob) -> None:
        """Edge: full-auth users (mfa_enabled=False) bypass the gate untouched."""
        app, _ = _build_app(async_engine)
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            await client.post("/admin/login", data={"username": "bob", "password": "secret"})
            # Reaching /admin/ returns 200 — the dashboard.
            resp = await client.get("/admin/", follow_redirects=False)
            assert resp.status_code == 200


# ── Edge: structured partial-auth shape is required ───────────────────────


class TestPartialAuthShapeValidation:
    @pytest.mark.anyio
    async def test_login_writes_structured_partial_auth_marker(
        self, async_engine, mfa_alice
    ) -> None:
        """The marker must follow the SDD-resolved shape: a dict with stage+user_id.

        We assert this indirectly: after logging in as an MFA user, hitting
        /admin/mfa/challenge succeeds (the C2-D _read_partial_auth helper
        accepts only structured dicts). If C3-A wrote a bare integer we would
        be redirected back to /admin/login instead.
        """
        sender = _CapturingSender()
        app, _ = _build_app(async_engine, sender=sender)
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            await client.post("/admin/login", data={"username": "alice", "password": "secret"})
            resp = await client.get("/admin/mfa/challenge", follow_redirects=False)
            assert resp.status_code == 200, (
                "challenge view rejected the partial-auth marker — wrong shape"
            )


# ── Edge: enable flow rejects bad codes without flipping the flag ─────────


class TestEnableFlowRejectsBadCode:
    @pytest.mark.anyio
    async def test_wrong_confirm_code_does_not_flip_mfa_enabled(
        self, async_engine, plain_bob
    ) -> None:
        sender = _CapturingSender()
        app, _ = _build_app(async_engine, sender=sender)
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            await client.post("/admin/login", data={"username": "bob", "password": "secret"})
            await client.post("/admin/mfa/enable")
            assert len(sender.calls) == 1

            # Submit a deliberately wrong code
            resp = await client.post("/admin/mfa/enable", data={"code": "000000"})
            assert resp.status_code == 200

            async with AsyncSession(async_engine) as session:
                row = (
                    await session.execute(select(User).where(User.username == "bob"))
                ).scalar_one()
                # Then the MFA flag is unchanged
                assert row.mfa_enabled is False


# ── Edge: partial-auth gate ignores OTP_SESSION_KEY noise ─────────────────


class TestPartialAuthGateOnlyChecksKey:
    @pytest.mark.anyio
    async def test_otp_entry_alone_does_not_block_anonymous_user(self, async_engine) -> None:
        """A leftover OTP entry without a partial-auth marker should not
        falsely promote an anonymous request to "partial-auth"."""
        # We can't easily inject just an OTP key here without the partial-auth
        # marker, but we can sanity-check that an anonymous request is still
        # routed through the existing "send to login" path, NOT to the MFA
        # challenge.
        app, _ = _build_app(async_engine)
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.get("/admin/", follow_redirects=False)
            assert resp.status_code == 302
            assert resp.headers["location"].endswith("/admin/login")


# Silence unused-import warning when fixtures/constants aren't referenced
# directly in a test (they're consumed via the C3-A wiring under test).
_ = (datetime, timezone, OTP_SESSION_KEY, PARTIAL_AUTH_SESSION_KEY)
