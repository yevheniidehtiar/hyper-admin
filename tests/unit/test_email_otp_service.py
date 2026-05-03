"""Unit tests for EmailOTPService (C1-D, #484).

Maps the 5 BDD scenarios from
.meta/epics/epicauth-object-level-permissions-mvp-otpmfa/stories/featauth-create-emailotpservice.md
to failing tests, plus a few edge cases enumerated in
docs/specs/object-permissions-mfa.md (Edge Cases & Error Handling).
"""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any

import pytest

from hyperadmin.auth.models import User
from hyperadmin.auth.otp import (
    OTP_SESSION_KEY,
    PARTIAL_AUTH_SESSION_KEY,
    EmailOTPService,
    RateLimitError,
)

pytestmark = pytest.mark.anyio


# --- Helpers ---------------------------------------------------------------


class _Sender:
    """Test double capturing every (email, code) pair the service sends."""

    def __init__(self) -> None:
        self.calls: list[tuple[str, str]] = []
        self.raise_on_send: BaseException | None = None

    async def __call__(self, email: str, code: str) -> None:
        if self.raise_on_send is not None:
            raise self.raise_on_send
        self.calls.append((email, code))


def _make_user(uid: int = 1) -> User:
    return User(
        id=uid,
        username="alice",
        email="alice@example.com",
        password_hash="x",
    )


# --- Module-level constants ------------------------------------------------


class TestSessionKeyConstants:
    """C3-A's middleware will import these — they are the canonical names."""

    def test_otp_session_key_value(self) -> None:
        assert OTP_SESSION_KEY == "mfa_otp"

    def test_partial_auth_session_key_value(self) -> None:
        assert PARTIAL_AUTH_SESSION_KEY == "auth_state"


# --- Scenario 1: generate and send OTP code -------------------------------


class TestGenerateAndSend:
    async def test_writes_hashed_entry_and_calls_email_sender(self) -> None:
        # Given user "alice" with email "alice@example.com"
        sender = _Sender()
        service = EmailOTPService(email_sender=sender)
        alice = _make_user()
        session: dict[str, Any] = {}

        # When generate_and_send(alice) is called
        await service.generate_and_send(alice, session)

        # Then a 6-digit code is generated and stored
        entry = session[OTP_SESSION_KEY]
        assert entry["user_id"] == alice.id
        assert "code_hash" in entry
        assert "issued_at" in entry
        assert entry["attempts"] == 0

        # And email_sender is called with alice's email and the code
        assert len(sender.calls) == 1
        sent_email, sent_code = sender.calls[0]
        assert sent_email == "alice@example.com"
        assert len(sent_code) == 6
        assert sent_code.isdigit()

    async def test_raw_code_is_not_persisted_in_session(self) -> None:
        # Edge: we must store hash, never the raw code
        sender = _Sender()
        service = EmailOTPService(email_sender=sender)
        session: dict[str, Any] = {}

        await service.generate_and_send(_make_user(), session)

        _, raw_code = sender.calls[0]
        entry = session[OTP_SESSION_KEY]
        # The raw 6-digit code must not appear anywhere in the stored value.
        assert raw_code not in str(entry)
        assert entry["code_hash"] != raw_code


# --- Scenario 2: verify valid OTP code -------------------------------------


class TestVerify:
    async def test_returns_true_on_correct_recent_code(self) -> None:
        # Given user "alice" has a pending OTP code generated 2 minutes ago
        sender = _Sender()
        service = EmailOTPService(email_sender=sender, ttl_seconds=300)
        alice = _make_user()
        session: dict[str, Any] = {}
        await service.generate_and_send(alice, session)
        _, raw_code = sender.calls[0]
        # Backdate issued_at by 2 minutes (well within TTL=300s).
        issued = datetime.fromisoformat(session[OTP_SESSION_KEY]["issued_at"])
        session[OTP_SESSION_KEY]["issued_at"] = (issued - timedelta(minutes=2)).isoformat()

        # When verify(alice, raw_code, session) is called
        result = await service.verify(alice, raw_code, session)

        # Then result is True
        assert result is True

    async def test_returns_false_on_expired_code(self) -> None:
        # Given a pending OTP older than the configured TTL
        sender = _Sender()
        service = EmailOTPService(email_sender=sender, ttl_seconds=300)
        alice = _make_user()
        session: dict[str, Any] = {}
        await service.generate_and_send(alice, session)
        _, raw_code = sender.calls[0]
        # Backdate issued_at by 6 minutes (TTL is 5).
        issued = datetime.fromisoformat(session[OTP_SESSION_KEY]["issued_at"])
        session[OTP_SESSION_KEY]["issued_at"] = (issued - timedelta(minutes=6)).isoformat()

        # When verify is called
        result = await service.verify(alice, raw_code, session)

        # Then result is False
        assert result is False

    async def test_returns_false_on_wrong_code(self) -> None:
        # Given a pending OTP code
        sender = _Sender()
        service = EmailOTPService(email_sender=sender)
        alice = _make_user()
        session: dict[str, Any] = {}
        await service.generate_and_send(alice, session)

        # When verify is called with a wrong code
        result = await service.verify(alice, "999999", session)

        # Then result is False
        assert result is False
        # And attempts counter is bumped
        assert session[OTP_SESSION_KEY]["attempts"] == 1

    async def test_returns_false_when_no_pending_code(self) -> None:
        # Given session has no pending OTP entry
        service = EmailOTPService(email_sender=_Sender())
        result = await service.verify(_make_user(), "123456", {})
        # Then verify returns False without raising
        assert result is False

    async def test_clears_session_entry_on_success(self) -> None:
        # Edge: SDD says single active code per user — successful verify clears it.
        sender = _Sender()
        service = EmailOTPService(email_sender=sender)
        alice = _make_user()
        session: dict[str, Any] = {}
        await service.generate_and_send(alice, session)
        _, raw_code = sender.calls[0]

        result = await service.verify(alice, raw_code, session)

        assert result is True
        assert OTP_SESSION_KEY not in session


# --- Scenario 5: rate limit exceeded ---------------------------------------


class TestRateLimit:
    async def test_raises_after_three_codes_in_window(self) -> None:
        # Given user "alice" has requested 3 OTP codes in the last 10 minutes
        sender = _Sender()
        service = EmailOTPService(email_sender=sender, rate_limit=(3, 600))
        alice = _make_user()
        session: dict[str, Any] = {}
        for _ in range(3):
            await service.generate_and_send(alice, session)

        # When generate_and_send is called again
        # Then RateLimitError is raised
        with pytest.raises(RateLimitError):
            await service.generate_and_send(alice, session)

    async def test_window_slides(self) -> None:
        # Edge: history outside the window must not block new sends.
        sender = _Sender()
        service = EmailOTPService(email_sender=sender, rate_limit=(3, 600))
        alice = _make_user()
        session: dict[str, Any] = {}
        for _ in range(3):
            await service.generate_and_send(alice, session)
        # Backdate every history timestamp past the window.
        history_key = OTP_SESSION_KEY + "_history"
        per_user = session[history_key][str(alice.id)]
        session[history_key][str(alice.id)] = [
            (datetime.fromisoformat(ts) - timedelta(seconds=601)).isoformat() for ts in per_user
        ]

        # Should not raise: the three prior issues are now outside the window.
        await service.generate_and_send(alice, session)


# --- Edge: email send failure rolls back session entry ---------------------


class TestEmailFailure:
    async def test_session_entry_rolled_back_on_email_failure(self) -> None:
        sender = _Sender()
        sender.raise_on_send = RuntimeError("smtp down")
        service = EmailOTPService(email_sender=sender)
        alice = _make_user()
        session: dict[str, Any] = {}

        with pytest.raises(RuntimeError, match="smtp down"):
            await service.generate_and_send(alice, session)

        # The OTP entry must not be left behind for a code that was never sent.
        assert OTP_SESSION_KEY not in session

    async def test_email_failure_restores_previous_entry(self) -> None:
        # Edge: if a previous code already lived in the session, a failed
        # second send must restore it rather than wipe it out.
        sender = _Sender()
        service = EmailOTPService(email_sender=sender)
        alice = _make_user()
        session: dict[str, Any] = {}
        await service.generate_and_send(alice, session)
        original_entry = dict(session[OTP_SESSION_KEY])

        sender.raise_on_send = RuntimeError("smtp down")
        with pytest.raises(RuntimeError):
            await service.generate_and_send(alice, session)

        assert session[OTP_SESSION_KEY] == original_entry

    async def test_email_failure_does_not_consume_rate_limit_budget(self) -> None:
        # Edge: a flaky SMTP backend must not eat the user's rate-limit
        # budget. Three failed sends followed by a successful send must
        # all be allowed under rate_limit=(3, 600); only delivered codes
        # count toward the window.
        sender = _Sender()
        sender.raise_on_send = RuntimeError("smtp down")
        service = EmailOTPService(email_sender=sender, rate_limit=(3, 600))
        alice = _make_user()
        session: dict[str, Any] = {}

        for _ in range(5):
            with pytest.raises(RuntimeError):
                await service.generate_and_send(alice, session)

        # Rate-limit history must remain empty: zero successful issuances.
        history = session.get(OTP_SESSION_KEY + "_history", {}).get(str(alice.id), [])
        assert history == []

        # And a subsequent successful send must go through cleanly.
        sender.raise_on_send = None
        await service.generate_and_send(alice, session)
        assert OTP_SESSION_KEY in session


class TestGuardrails:
    async def test_unsaved_user_raises_value_error(self) -> None:
        # Edge: user.id is None — service has no key to scope state under.
        service = EmailOTPService(email_sender=_Sender())
        unsaved = User(id=None, username="x", email="x@example.com", password_hash="x")
        with pytest.raises(ValueError, match=r"user\.id is None"):
            await service.generate_and_send(unsaved, {})

    async def test_verify_rejects_entry_for_other_user(self) -> None:
        # Edge: a session entry belonging to a different user must not
        # be redeemable by the current user.
        sender = _Sender()
        service = EmailOTPService(email_sender=sender)
        alice = _make_user(uid=1)
        bob = _make_user(uid=2)
        session: dict[str, Any] = {}
        await service.generate_and_send(alice, session)
        _, raw_code = sender.calls[0]

        result = await service.verify(bob, raw_code, session)

        assert result is False

    async def test_verify_rejects_malformed_issued_at(self) -> None:
        # Edge: corrupt session payload — verify must return False, not
        # propagate a parse error to the caller.
        service = EmailOTPService(email_sender=_Sender())
        session: dict[str, Any] = {
            OTP_SESSION_KEY: {
                "code_hash": "irrelevant",
                "issued_at": "not-a-timestamp",
                "attempts": 0,
                "user_id": 1,
            }
        }
        result = await service.verify(_make_user(), "123456", session)
        assert result is False
