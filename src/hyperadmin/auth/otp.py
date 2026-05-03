"""Email-OTP service for MVP MFA (v0.5.1, C1-D, #484).

This module owns the canonical session-state keys used across the MFA flow.
The middleware (C3-A) and views (C2-D) MUST import the constants from here
rather than redefining them — they are the single source of truth for all
MFA-related session state in HyperAdmin.

Two keys are exported:

* ``OTP_SESSION_KEY`` — namespace under which a single pending OTP record
  lives in ``request.session``. The shape is::

      {
          "code_hash": "<argon2 hash of the 6-digit code>",
          "issued_at": "<ISO-8601 timestamp>",
          "attempts": <int>,
          "user_id": <int>,
      }

* ``PARTIAL_AUTH_SESSION_KEY`` — namespace for the partial-auth marker that
  signals "password verified, awaiting MFA". Its value is a structured dict
  ``{"stage": "mfa_pending", "user_id": ...}`` (per the SDD's resolved Open
  Question #2 — structured form is more extensible than a bare user id).

Rate-limit accounting lives in-session under ``OTP_SESSION_KEY + "_history"``
as ``{<user_id_str>: [<iso ts>, ...]}``. This is per-session, single-process
state; it does not span workers — the SDD acknowledges this MVP limitation
and plans a pluggable counter for v0.6+.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from secrets import choice
from typing import TYPE_CHECKING, Any, Final

from hyperadmin.auth.backend import hash_password, verify_password

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable

    from hyperadmin.auth.models import User

OTP_SESSION_KEY: Final[str] = "mfa_otp"
PARTIAL_AUTH_SESSION_KEY: Final[str] = "auth_state"

_DIGITS: Final[str] = "0123456789"
_OTP_LENGTH: Final[int] = 6


class RateLimitError(Exception):
    """Raised by ``EmailOTPService.generate_and_send`` when the per-user
    OTP issuance rate limit has been exceeded for the current window."""


class EmailOTPService:
    """Generate, store, and verify 6-digit numeric OTP codes via email.

    Codes are stored hashed (Argon2) under ``session[OTP_SESSION_KEY]`` —
    raw codes are never persisted. The ``email_sender`` callable is injected
    by the application; this service does not know about SMTP backends.
    """

    def __init__(
        self,
        email_sender: Callable[[str, str], Awaitable[None]],
        ttl_seconds: int = 300,
        rate_limit: tuple[int, int] = (3, 600),
    ) -> None:
        self._email_sender = email_sender
        self._ttl_seconds = ttl_seconds
        self._max_codes, self._window_seconds = rate_limit

    async def generate_and_send(self, user: User, session: dict[str, Any]) -> None:
        """Generate a fresh 6-digit OTP, store its hash in ``session``, and
        deliver the raw code via ``email_sender``.

        Raises:
            RateLimitError: when the user has already requested
                ``rate_limit[0]`` codes within ``rate_limit[1]`` seconds.
            Exception: any error raised by ``email_sender`` is re-raised
                after rolling back the just-written session entry so the
                user is not left with a code that was never delivered.
        """

        if user.id is None:
            raise ValueError("Cannot issue OTP for an unsaved user (user.id is None)")

        # All timestamps are timezone-aware UTC so TTL/window arithmetic is
        # invariant under server timezone settings (containers, kubelets, etc).
        now = datetime.now(tz=timezone.utc)
        self._enforce_rate_limit(user, session, now)

        code = "".join(choice(_DIGITS) for _ in range(_OTP_LENGTH))
        previous_entry = session.get(OTP_SESSION_KEY)
        session[OTP_SESSION_KEY] = {
            "code_hash": hash_password(code),
            "issued_at": now.isoformat(),
            "attempts": 0,
            "user_id": user.id,
        }

        try:
            await self._email_sender(user.email, code)
        except BaseException:
            # Rollback BOTH the OTP entry AND the rate-limit history. A code
            # that was never delivered must not linger in the session, and a
            # failed send must not consume the user's rate-limit budget.
            if previous_entry is None:
                session.pop(OTP_SESSION_KEY, None)
            else:
                session[OTP_SESSION_KEY] = previous_entry
            raise

        # Only count this as a real issuance once delivery has succeeded.
        # Placing this AFTER ``await`` rather than before is what protects
        # users from flaky SMTP servers eating their rate-limit budget.
        self._record_issuance(user, session, now)

    async def verify(self, user: User, code: str, session: dict[str, Any]) -> bool:
        """Verify ``code`` against the pending OTP for ``user``.

        On success, clears the session entry — a single active code per
        user (per the SDD: "Latest generate_and_send overwrites prior OTP
        in session; older code becomes invalid").

        Returns ``False`` (without raising) on:
          * no pending entry,
          * expired entry,
          * mismatched code (and bumps ``attempts`` counter),
          * mismatched user id.
        """

        entry = session.get(OTP_SESSION_KEY)
        if entry is None:
            return False
        if entry.get("user_id") != user.id:
            return False

        try:
            issued_at = datetime.fromisoformat(entry["issued_at"])
        except (KeyError, ValueError):
            return False
        # Compare in UTC so TTL evaluation is consistent across servers
        # regardless of local TZ. Naive `issued_at` values (from older
        # entries written before this fix) are treated as UTC.
        if issued_at.tzinfo is None:
            issued_at = issued_at.replace(tzinfo=timezone.utc)
        if datetime.now(tz=timezone.utc) - issued_at > timedelta(seconds=self._ttl_seconds):
            return False

        if not verify_password(code, entry["code_hash"]):
            entry["attempts"] = int(entry.get("attempts", 0)) + 1
            return False

        # Successful verify — burn the code so it cannot be replayed.
        session.pop(OTP_SESSION_KEY, None)
        return True

    # -- internals ----------------------------------------------------------

    def _history_key(self) -> str:
        return OTP_SESSION_KEY + "_history"

    def _user_history(self, user: User, session: dict[str, Any]) -> list[str]:
        history = session.setdefault(self._history_key(), {})
        return history.setdefault(str(user.id), [])

    def _enforce_rate_limit(self, user: User, session: dict[str, Any], now: datetime) -> None:
        history = self._user_history(user, session)
        cutoff = now - timedelta(seconds=self._window_seconds)
        # Naive timestamps from pre-UTC entries are treated as UTC.
        fresh: list[str] = []
        for ts in history:
            parsed = datetime.fromisoformat(ts)
            if parsed.tzinfo is None:
                parsed = parsed.replace(tzinfo=timezone.utc)
            if parsed >= cutoff:
                fresh.append(ts)
        # Persist the trimmed list so the session does not grow unbounded.
        session[self._history_key()][str(user.id)] = fresh
        if len(fresh) >= self._max_codes:
            raise RateLimitError(
                f"OTP rate limit exceeded: {self._max_codes} codes per "
                f"{self._window_seconds}s for user_id={user.id}"
            )

    def _record_issuance(self, user: User, session: dict[str, Any], now: datetime) -> None:
        self._user_history(user, session).append(now.isoformat())
