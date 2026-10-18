"""Positioned marks (ticks, labels, paths, bars, tooltips) the chart macros print as-is."""

from __future__ import annotations

from dataclasses import dataclass

TIP_LINE_PX = 18.0  # tooltip line height


def round1(value: float) -> float:
    return round(value, 1)


@dataclass(frozen=True)
class Tick:
    y: float
    label: str

    @property
    def text_y(self) -> float:
        return round1(self.y + 4.0)


@dataclass(frozen=True)
class AxisLabel:
    x: float
    text: str
    full: str

    @property
    def truncated(self) -> bool:
        return self.text != self.full


@dataclass(frozen=True)
class LinePath:
    d: str
    cls: str
    dashed: bool


@dataclass(frozen=True)
class TextMark:
    x: float
    y: float
    text: str
    cls: str = ""


@dataclass(frozen=True)
class Marker:
    cx: float
    cy: float
    cls: str


@dataclass(frozen=True)
class Tooltip:
    x: float
    y: float
    width: float
    height: float
    lines: tuple[tuple[str, str], ...]

    @property
    def text_x(self) -> float:
        return round1(self.x + 10.0)

    @property
    def rows(self) -> list[tuple[float, str, str]]:
        """``(baseline y, key, value)`` per tooltip line."""
        return [
            (round1(self.y + 20.0 + TIP_LINE_PX * i), k, v) for i, (k, v) in enumerate(self.lines)
        ]


@dataclass(frozen=True)
class Hover:
    """A focusable hit area for one x position, with its point marker and tooltip."""

    x: float
    width: float
    label: str
    marker: Marker | None = None
    tip: Tooltip | None = None


@dataclass(frozen=True)
class Rect:
    x: float
    y: float
    width: float
    height: float
    cls: str

    @property
    def x2(self) -> float:
        return round1(self.x + self.width)


@dataclass(frozen=True)
class Bar:
    rect: Rect
    label: str
    value_label: TextMark | None


@dataclass(frozen=True)
class Stack:
    segments: tuple[Rect, ...]
    hit: Hover
