"""What an OAuth sign-in keeps in the admin session (``docs/specs/oauth-sso.md``).

Three keys, all inside the signed admin session cookie:

- ``OAUTH_FLOW_KEY``: the sign-in in flight (state nonce, PKCE verifier, issue
  time), written by the authorize step and removed by the callback.
- ``OAUTH_SESSION_KEY``: marks a session that was started by an OAuth sign-in and
  says when its access token expires, so the refresh middleware never touches the
  database for password sessions.
- ``OAUTH_FLASH_KEY``: a one-shot message for the next page.

This module imports nothing heavy; ``auth/views.py`` and templates use it without
loading the OAuth backend.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Final, Literal

if TYPE_CHECKING:
    from collections.abc import MutableMapping

    from starlette.requests import Request

OAUTH_FLOW_KEY: Final[str] = "oauth_flow"
OAUTH_SESSION_KEY: Final[str] = "oauth_session"
OAUTH_FLASH_KEY: Final[str] = "oauth_flash"

FlashLevel = Literal["info", "error"]


def mark_oauth_session(
    session: MutableMapping[str, Any], *, user_id: int, provider: str, expires_at: float | None
) -> None:
    """Record that ``user_id`` signed in through ``provider``.

    Args:
        session: The admin session.
        user_id: The signed-in user.
        provider: Name of the provider.
        expires_at: Expiry of the access token as epoch seconds, or ``None`` when
            the token does not expire.
    """
    session[OAUTH_SESSION_KEY] = {
        "user_id": user_id,
        "provider": provider,
        "expires_at": expires_at,
    }


def read_oauth_session(session: Any, *, user_id: Any) -> dict[str, Any] | None:
    """Return the OAuth marker of ``session`` when it belongs to ``user_id``.

    Anything else (no session, no marker, a malformed one, another user's) is
    ``None``: the marker only ever describes the user the session is signed in as.
    """
    try:
        marker = session.get(OAUTH_SESSION_KEY)
    except AttributeError:
        return None
    if not isinstance(marker, dict) or not isinstance(marker.get("provider"), str):
        return None
    if user_id is None or marker.get("user_id") != user_id:
        return None
    return marker


def set_flash(session: MutableMapping[str, Any], message: str, level: FlashLevel = "info") -> None:
    """Leave ``message`` for the next page that calls :func:`pop_flash`."""
    session[OAUTH_FLASH_KEY] = {"message": message, "level": level}


def pop_flash(request: Request) -> dict[str, str] | None:
    """Return and remove the pending message, as ``{"message", "level"}``.

    Safe on a request without a session (returns ``None``), so templates can call it
    unconditionally.
    """
    session = request.scope.get("session")
    if not isinstance(session, dict):
        return None
    flash = session.pop(OAUTH_FLASH_KEY, None)
    if not isinstance(flash, dict) or not isinstance(flash.get("message"), str):
        return None
    return {"message": flash["message"], "level": str(flash.get("level") or "info")}


__all__ = [
    "OAUTH_FLASH_KEY",
    "OAUTH_FLOW_KEY",
    "OAUTH_SESSION_KEY",
    "mark_oauth_session",
    "pop_flash",
    "read_oauth_session",
    "set_flash",
]
