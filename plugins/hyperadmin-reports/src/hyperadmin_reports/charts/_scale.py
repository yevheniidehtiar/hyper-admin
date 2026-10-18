"""Scale and label arithmetic shared by the SVG chart models."""

from __future__ import annotations

import math

_NICE_STEPS = (1.0, 2.0, 2.5, 5.0, 10.0)
ELLIPSIS = "…"


def nice_scale(low: float, high: float, count: int = 4) -> tuple[float, float, float]:
    """Return ``(start, stop, step)`` covering ``[low, high]`` in about ``count`` round steps.

    The domain always includes zero so bars and lines keep an honest baseline.
    """
    low, high = min(low, 0.0), max(high, 0.0)
    if high == low:
        high = low + 1.0
    raw = (high - low) / count
    magnitude = 10 ** math.floor(math.log10(raw))
    step = next(m * magnitude for m in _NICE_STEPS if m * magnitude >= raw)
    start = math.floor(low / step) * step
    stop = math.ceil(high / step) * step
    return start, stop, step


def tick_values(start: float, stop: float, step: float) -> list[float]:
    """Return the tick values from ``start`` to ``stop`` inclusive, free of float drift."""
    n = round((stop - start) / step)
    return [round(start + i * step, 10) for i in range(n + 1)]


def format_number(value: float) -> str:
    """Format a value with thousands separators; integers lose the decimal point."""
    if float(value).is_integer():
        return f"{int(value):,}"
    return f"{value:,.2f}".rstrip("0").rstrip(".")


def compact_number(value: float) -> str:
    """Format an axis tick compactly: ``1200000`` → ``1.2M``, ``45000`` → ``45k``."""
    for divisor, suffix in ((1e9, "B"), (1e6, "M"), (1e3, "k")):
        if abs(value) >= divisor:
            return format_number(round(value / divisor, 1)) + suffix
    return format_number(value)


def truncate(text: str, max_chars: int) -> str:
    """Cut ``text`` to ``max_chars`` characters, ending in an ellipsis when shortened."""
    if len(text) <= max_chars:
        return text
    return text[: max(max_chars - 1, 1)].rstrip() + ELLIPSIS
