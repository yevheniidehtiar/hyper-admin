"""Pure presentation helpers for the task pages."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from datetime import timedelta

_MINUTE = 60
_HOUR = 3600
_DAY = 86400


def format_age(age: timedelta | None) -> str | None:
    """Compact text for an age ("45s", "12m", "3h 5m", "2d 4h"); ``None`` stays ``None``."""
    if age is None:
        return None
    seconds = max(int(age.total_seconds()), 0)
    if seconds < _MINUTE:
        return f"{seconds}s"
    if seconds < _HOUR:
        return f"{seconds // _MINUTE}m"
    if seconds < _DAY:
        return f"{seconds // _HOUR}h {seconds % _HOUR // _MINUTE}m"
    return f"{seconds // _DAY}d {seconds % _DAY // _HOUR}h"
