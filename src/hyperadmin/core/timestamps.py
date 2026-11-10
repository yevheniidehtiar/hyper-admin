from __future__ import annotations

from datetime import datetime, timezone


def utcnow() -> datetime:
    """Return the current time as a timezone-aware UTC datetime.

    Use as ``Field(default_factory=utcnow)``; the admin forms treat such fields as
    auto-populated and hide them from user input.
    """
    return datetime.now(timezone.utc)
