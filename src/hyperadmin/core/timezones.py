"""Timezone-aware datetime helpers for forms, filters and display.

Pure helpers built on the stdlib ``zoneinfo`` and ``datetime`` only. Columns are
either *aware* (values are stored as UTC instants) or *naive* (values are stored
as wall-clock time). User input is entered in a display timezone and converted
accordingly; aware values are shown back in that timezone.
"""

from __future__ import annotations

import functools
from datetime import date, datetime, timezone, tzinfo
from typing import Any, Literal

DateTimeKind = Literal["aware", "naive"]

AUTO_NOW_MARKER = "__hyperadmin_auto_now__"
_NOW_NAMES = frozenset({"now", "utcnow"})


def utc_now() -> datetime:
    """Return the current time as an aware UTC datetime."""
    return datetime.now(timezone.utc)


setattr(utc_now, AUTO_NOW_MARKER, True)

_KNOWN_NOW_FACTORIES: tuple[Any, ...] = (datetime.now, datetime.utcnow, utc_now)


def is_auto_now_factory(fn: Any) -> bool:
    """Return ``True`` when ``fn`` is a default factory that stamps "now".

    Recognised: ``datetime.now``, ``datetime.utcnow``, :func:`utc_now`, partials of
    those, callables marked with ``__hyperadmin_auto_now__ = True``, and lambdas
    that reference ``now`` or ``utcnow``. A named function is deliberately not
    inspected, so it is the escape hatch for an editable datetime default.
    """
    if fn is None or not callable(fn):
        return False
    if isinstance(fn, functools.partial):
        return is_auto_now_factory(fn.func)
    if getattr(fn, AUTO_NOW_MARKER, False) is True:
        return True
    if any(fn == known for known in _KNOWN_NOW_FACTORIES):
        return True
    code = getattr(fn, "__code__", None)
    if code is None or getattr(fn, "__name__", "") != "<lambda>":
        return False
    return bool(_NOW_NAMES.intersection(code.co_names))


def _fromisoformat(raw: str) -> datetime:
    text = raw.strip()
    if text.endswith(("Z", "z")):
        text = f"{text[:-1]}+00:00"
    return datetime.fromisoformat(text)


def parse_datetime_input(raw: str, *, kind: DateTimeKind, tz: tzinfo) -> datetime:
    """Parse an ISO-8601 form value for a column of the given ``kind``.

    - ``aware``: naive input is interpreted in ``tz`` (``fold=0`` in DST gaps and
      overlaps) and returned as aware UTC; explicit offsets are respected.
    - ``naive``: naive input is kept as entered; input with an offset is converted
      to ``tz`` wall-clock time and returned naive.

    Raises:
        ValueError: When ``raw`` is not a valid ISO-8601 datetime.
    """
    value = _fromisoformat(raw)
    if kind == "aware":
        if value.tzinfo is None:
            value = value.replace(tzinfo=tz, fold=0)
        return value.astimezone(timezone.utc)
    if value.tzinfo is not None:
        return value.astimezone(tz).replace(tzinfo=None)
    return value


def format_datetime_input(value: Any, tz: tzinfo) -> str:
    """Format a value for an ``<input type="datetime-local">`` field.

    Aware datetimes are converted to ``tz``; the result has second precision and
    no offset. ``None`` becomes ``""``; strings pass through unchanged.
    """
    if value is None:
        return ""
    if isinstance(value, datetime):
        if value.tzinfo is not None:
            value = value.astimezone(tz).replace(tzinfo=None)
        return value.isoformat(timespec="seconds")
    if isinstance(value, date):
        return value.isoformat()
    return str(value)


def to_display(value: datetime, tz: tzinfo, fmt: str) -> str:
    """Format ``value`` with ``fmt``, converting only aware values to ``tz``."""
    if value.tzinfo is not None:
        value = value.astimezone(tz)
    return value.strftime(fmt)
