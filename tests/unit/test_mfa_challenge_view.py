"""Unit tests for MFA challenge / verify / resend views (C2-D, #486).

Maps the 4 BDD scenarios from
.meta/epics/epicauth-object-level-permissions-mvp-otpmfa/stories/featauth-create-mfa-challenge-view-and-template.md
to tests, plus edge cases enumerated in
docs/specs/object-permissions-mfa.md (Edge Cases & Error Handling).

C2-D adds three NEW endpoints; the C3-A wiring of `login_view` and the
partial-auth middleware gate is intentionally out of scope here. These
tests therefore prime ``request.session[PARTIAL_AUTH_SESSION_KEY]`` by
hand to simulate the post-password / pre-MFA state.
"""

from __future__ import annotations

from typing import Any

import pytest
from fastapi import FastAPI, Request
from fastapi.templating import Jinja2Templates
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlmodel import SQLModel
from starlette.middleware.sessions import SessionMiddleware
from starlette.responses import Response

from hyperadmin.auth.backend import hash_password
from hyperadmin.auth.models import User
from hyperadmin.auth.otp import (
    OTP_SESSION_KEY,
    PARTIAL_AUTH_SESSION_KEY,
    EmailOTPService,
    RateLimitError,
)


@pytest.fixture
async def async_engine(tmp_path):
    db_file = tmp_path / "test_mfa_challenge.db"
    engine = create_async_engine(f"sqlite+aiosqlite:///{db_file}")
    async with engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.create_all)
    yield engine
    await engine.dispose()


@pytest.fixture
async def alice(async_engine) -> User:
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


class _CapturingSender:
    """Test double for the EmailOTPService email_sender callable."""

    def __init__(self) -> None:
        self.calls: list[tuple[str, str]] = []
        self.raise_on_send: BaseException | None = None

    async def __call__(self, email: str, code: str) -> None:
        if self.raise_on_send is not None:
            raise self.raise_on_send
        self.calls.append((email, code))


def _build_app(async_engine, otp_service: Any | None = None, sender: Any | None = None):
    """Build a minimal FastAPI app exposing the MFA endpoints.

    The app intentionally does NOT wire ``login_view`` to populate a
    partial-auth session — that is C3-A's job. Tests prime the session
    by hand via the ``/_test/seed-partial-auth`` helper route below.
    """
    from hyperadmin.auth.session import SessionAuthBackend
    from hyperadmin.auth.views import (
        mfa_challenge_view,
        mfa_resend_view,
        mfa_verify_view,
    )
    from hyperadmin.core.app import Admin
    from hyperadmin.core.registry import site
    from hyperadmin.core.settings import HyperAdminSettings

    site._registry.clear()

    app = FastAPI()
    backend = SessionAuthBackend(engine=async_engine)
    Admin(
        app,
        engine=async_engine,
        settings=HyperAdminSettings(create_tables=False, secret_key="test-secret"),
        auth_backend=backend,
    )

    if otp_service is None:
        otp_service = EmailOTPService(email_sender=sender or _CapturingSender())

    # C3-A will wire these into core/app.py::_register_auth_routes; for
    # C2-D unit tests we wire them directly so we can exercise the views
    # in isolation. The session middleware is added BELOW the routes so
    # cookies are actually written.
    import os as _os

    template_dir = _os.path.join(
        _os.path.dirname(_os.path.dirname(_os.path.dirname(_os.path.abspath(__file__)))),
        "src",
        "hyperadmin",
        "templates",
    )
    templates = Jinja2Templates(directory=template_dir)
    from hyperadmin.i18n import install_jinja_i18n

    install_jinja_i18n(templates.env)
    templates.env.globals["admin_prefix"] = "/admin"
    templates.env.globals["auth_enabled"] = True
    templates.env.globals["theme"] = "default"
    templates.env.globals["site_title"] = "HyperAdmin"
    templates.env.globals["site_header"] = "HyperAdmin"
    templates.env.globals["supported_locales"] = ["en"]
    templates.env.globals["rtl_locales"] = []

    async def _challenge_get(request: Request):
        return await mfa_challenge_view(request, templates, "/admin")

    async def _verify_post(request: Request):
        return await mfa_verify_view(request, templates, backend, otp_service, "/admin")

    async def _resend_post(request: Request):
        return await mfa_resend_view(request, templates, backend, otp_service, "/admin")

    async def _seed(request: Request):
        # Test-only helper: simulates what C3-A's modified login_view will
        # do after a correct password for an MFA-enabled user.
        form = await request.form()
        request.session[PARTIAL_AUTH_SESSION_KEY] = {
            "stage": "mfa_pending",
            "user_id": int(form["user_id"]),
        }
        return Response(status_code=204)

    async def _seed_otp_route(request: Request):
        # Test-only helper: writes an OTP entry directly to the session
        # so we can drive verify() with known codes / known issued_at.
        form = await request.form()
        request.session[OTP_SESSION_KEY] = {
            "code_hash": hash_password(str(form["code"])),
            "issued_at": str(form["issued_at"]),
            "attempts": 0,
            "user_id": int(form["user_id"]),
        }
        return Response(status_code=204)

    app.add_api_route("/admin/mfa/challenge", _challenge_get, methods=["GET"])
    app.add_api_route("/admin/mfa/verify", _verify_post, methods=["POST"])
    app.add_api_route("/admin/mfa/resend", _resend_post, methods=["POST"])
    app.add_api_route("/_test/seed-partial-auth", _seed, methods=["POST"])
    app.add_api_route("/_test/seed-otp", _seed_otp_route, methods=["POST"])

    app.add_middleware(SessionMiddleware, secret_key="test-secret")
    return app


async def _seed_partial(client: AsyncClient, user_id: int) -> None:
    resp = await client.post("/_test/seed-partial-auth", data={"user_id": user_id})
    assert resp.status_code == 204


async def _seed_otp(client: AsyncClient, user_id: int, code: str, issued_at: str) -> None:
    resp = await client.post(
        "/_test/seed-otp",
        data={"user_id": user_id, "code": code, "issued_at": issued_at},
    )
    assert resp.status_code == 204


# --- Scenario 1: GET /admin/mfa/challenge renders the form ----------------


class TestChallengePage:
    @pytest.mark.anyio
    async def test_challenge_page_renders_with_code_input_and_verify_button(
        self, async_engine, alice
    ) -> None:
        """
        Scenario: MFA challenge page renders with code input
          Given user "alice" passed password authentication and has mfa_enabled=True
          When  GET /admin/mfa/challenge
          Then  page renders a form with a 6-digit code input and "Verify" button
        """
        app = _build_app(async_engine)
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            # Given alice has a partial-auth session
            await _seed_partial(client, alice.id)

            # When she GETs the challenge page
            resp = await client.get("/admin/mfa/challenge")

            # Then the page renders with the code input + verify button
            assert resp.status_code == 200
            body = resp.text
            assert 'data-testid="mfa-code-input"' in body
            assert 'data-testid="mfa-verify-btn"' in body
            assert 'data-testid="mfa-resend-link"' in body

    @pytest.mark.anyio
    async def test_challenge_page_without_partial_auth_redirects_to_login(
        self, async_engine
    ) -> None:
        """Edge case: GET /admin/mfa/challenge with NO partial-auth session
        must redirect to /admin/login — there is no user to challenge.
        """
        app = _build_app(async_engine)
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.get("/admin/mfa/challenge", follow_redirects=False)
            assert resp.status_code == 302
            assert resp.headers["location"].endswith("/admin/login")


# --- Scenario 2: correct OTP code completes login -------------------------


class TestVerifyHappyPath:
    @pytest.mark.anyio
    async def test_correct_code_upgrades_session_and_redirects(self, async_engine, alice) -> None:
        """
        Scenario: correct OTP code completes login
          Given user "alice" is on MFA challenge page and code "123456" was sent
          When  POST /admin/mfa/verify with code=123456
          Then  session is created and redirect to /admin/
        """
        from datetime import datetime, timezone

        app = _build_app(async_engine)
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            # Given alice has a partial-auth session and a pending OTP "123456"
            await _seed_partial(client, alice.id)
            await _seed_otp(
                client,
                alice.id,
                "123456",
                datetime.now(tz=timezone.utc).isoformat(),
            )

            # When she POSTs the correct code
            resp = await client.post(
                "/admin/mfa/verify",
                data={"code": "123456"},
                follow_redirects=False,
            )

            # Then the session is upgraded and she is redirected to /admin/
            assert resp.status_code == 302
            assert resp.headers["location"].endswith("/admin/")

            # And the partial-auth marker is gone (full session takes over)
            resp2 = await client.get("/admin/mfa/challenge", follow_redirects=False)
            assert resp2.status_code == 302
            assert resp2.headers["location"].endswith("/admin/login")


# --- Scenario 3: wrong OTP code shows error -------------------------------


class TestVerifyWrongCode:
    @pytest.mark.anyio
    async def test_wrong_code_shows_invalid_error_and_keeps_partial_session(
        self, async_engine, alice
    ) -> None:
        """
        Scenario: wrong OTP code shows error
          Given user "alice" is on MFA challenge page
          When  POST /admin/mfa/verify with code=999999
          Then  error "Invalid code" is shown and user stays on challenge page
        """
        from datetime import datetime, timezone

        app = _build_app(async_engine)
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            await _seed_partial(client, alice.id)
            await _seed_otp(
                client,
                alice.id,
                "123456",
                datetime.now(tz=timezone.utc).isoformat(),
            )

            resp = await client.post(
                "/admin/mfa/verify",
                data={"code": "999999"},
                follow_redirects=False,
            )

            assert resp.status_code == 200
            assert "Invalid code" in resp.text
            assert 'data-testid="mfa-code-input"' in resp.text

            # Partial session still active
            challenge = await client.get("/admin/mfa/challenge", follow_redirects=False)
            assert challenge.status_code == 200


# --- Scenario 4: expired OTP code shows error with resend ----------------


class TestVerifyExpiredCode:
    @pytest.mark.anyio
    async def test_expired_code_shows_error_with_resend_link(self, async_engine, alice) -> None:
        """
        Scenario: expired OTP code shows error with resend option
          Given user "alice" has an OTP code that expired
          When  POST /admin/mfa/verify with the expired code
          Then  error "Code expired, please request a new one" is shown
          And   a "Resend code" link is available
        """
        from datetime import datetime, timedelta, timezone

        app = _build_app(async_engine)
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            await _seed_partial(client, alice.id)
            stale = (datetime.now(tz=timezone.utc) - timedelta(seconds=3600)).isoformat()
            await _seed_otp(client, alice.id, "123456", stale)

            resp = await client.post(
                "/admin/mfa/verify",
                data={"code": "123456"},
                follow_redirects=False,
            )

            assert resp.status_code == 200
            # Either "Code expired" or "Invalid or expired code" — the
            # template surfaces an explicit expired message when the
            # service returned False AND no fresh entry remains.
            assert "expired" in resp.text.lower()
            assert 'data-testid="mfa-resend-link"' in resp.text


# --- Edge: resend triggers EmailOTPService.generate_and_send -------------


class TestResend:
    @pytest.mark.anyio
    async def test_resend_calls_generate_and_send(self, async_engine, alice) -> None:
        """Edge: POST /admin/mfa/resend triggers EmailOTPService.generate_and_send."""
        sender = _CapturingSender()
        service = EmailOTPService(email_sender=sender)
        app = _build_app(async_engine, otp_service=service)
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            await _seed_partial(client, alice.id)

            resp = await client.post("/admin/mfa/resend")

            # The view re-renders the challenge page (200) with a flash
            # confirming the new code was sent.
            assert resp.status_code == 200
            assert len(sender.calls) == 1
            assert sender.calls[0][0] == "alice@example.com"

    @pytest.mark.anyio
    async def test_resend_when_rate_limited_renders_flash(self, async_engine, alice) -> None:
        """Edge: rate-limit hit surfaces flash, does not crash."""

        class _AlwaysRateLimited:
            async def generate_and_send(self, user: User, session: dict) -> None:
                raise RateLimitError("too many")

            async def verify(
                self, user: User, code: str, session: dict
            ) -> bool:  # pragma: no cover - not used in this test
                return False

        app = _build_app(async_engine, otp_service=_AlwaysRateLimited())
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            await _seed_partial(client, alice.id)
            resp = await client.post("/admin/mfa/resend")
            assert resp.status_code == 200
            assert "too many attempts" in resp.text.lower()

    @pytest.mark.anyio
    async def test_resend_without_partial_auth_redirects_to_login(self, async_engine) -> None:
        """Edge: anonymous resend → redirect to login (no session to refresh)."""
        app = _build_app(async_engine)
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.post("/admin/mfa/resend", follow_redirects=False)
            assert resp.status_code == 302
            assert resp.headers["location"].endswith("/admin/login")
