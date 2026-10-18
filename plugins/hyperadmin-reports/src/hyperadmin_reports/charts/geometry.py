"""Server-rendered SVG chart models (design system: ``docs/design/system/components/Chart``).

Each chart takes already-aggregated, already-thinned series and computes the geometry the
Jinja macros in ``templates/hyperadmin_reports/charts/`` draw: the y scale and ticks, x bands and
positions, line paths, bar rectangles, tooltip boxes and truncated labels. Rendering needs no
JavaScript; the macros only print the numbers computed here.
"""

from __future__ import annotations

import math
import re
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from functools import cached_property
from typing import ClassVar

from hyperadmin_reports.charts._marks import (
    TIP_LINE_PX,
    AxisLabel,
    Bar,
    Hover,
    LinePath,
    Marker,
    Rect,
    Stack,
    TextMark,
    Tick,
    Tooltip,
    round1,
)
from hyperadmin_reports.charts._scale import compact_number, format_number, nice_scale, tick_values
from hyperadmin_reports.charts._scale import truncate as _truncate

Formatter = Callable[[float], str]

MAX_SERIES = 6  # the design system defines six categorical slots, ha-chart-1 … ha-chart-6
MISSING = "—"
_KEY = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]*$")
_CHAR_PX = 7.0  # average advance of a 12px tabular glyph
_LABEL_GAP_PX = 96.0  # minimum distance between two x-axis labels on a line chart
_HIT_PX = 28.0
_TIP_MIN_PX = 140.0
_LABEL_LINE_PX = 14.0  # vertical room one 12px end label needs
_DASHED_SERIES = 2  # series 2 is dashed so the two lines differ beyond colour
_END_LABEL_MAX_SERIES = 2  # with more lines, end labels collide; the legend carries them


@dataclass(frozen=True)
class Series:
    """One named series; ``values`` align with the chart's x labels (``None`` = no data)."""

    name: str
    values: Sequence[float | None]

    def __post_init__(self) -> None:
        object.__setattr__(self, "values", tuple(self.values))


@dataclass(frozen=True)
class PeriodOption:
    """One option of the frame's period switch; ``url`` re-requests the chart fragment."""

    label: str
    url: str
    active: bool = False


def _thin(count: int, gap: float, min_gap: float) -> tuple[list[int], float]:
    """Indices of the x labels to print (anchored at the last one) and the room each gets."""
    step = max(1, math.ceil(min_gap / gap)) if gap else 1
    keep = [i for i in range(count) if (count - 1 - i) % step == 0]
    return keep, step * gap


class _XYChart:
    """Shared frame, scale and table logic for charts with an x axis and a y axis."""

    kind: ClassVar[str]
    margin_left: ClassVar[float] = 44.0
    margin_right: ClassVar[float] = 16.0
    margin_top: ClassVar[float] = 12.0
    margin_bottom: ClassVar[float] = 28.0
    label_gap: ClassVar[float] = _LABEL_GAP_PX

    def __init__(  # noqa: PLR0913 - presentation knobs, all keyword-only
        self,
        key: str,
        *,
        title: str,
        labels: Sequence[str],
        series: Sequence[Series],
        desc: str = "",
        x_title: str = "",
        width: int = 800,
        height: int = 240,
        format_value: Formatter = format_number,
        format_tick: Formatter = compact_number,
        max_label_chars: int = 18,
    ) -> None:
        if not _KEY.match(key):
            raise ValueError(f"chart key must match {_KEY.pattern!r}, got {key!r}")
        if not 1 <= len(series) <= MAX_SERIES:
            raise ValueError(f"a chart takes 1 to {MAX_SERIES} series, got {len(series)}")
        for s in series:
            if len(s.values) != len(labels):
                raise ValueError(
                    f"series {s.name!r} has {len(s.values)} values for {len(labels)} labels"
                )
        self.key = key
        self.title = title
        self.labels = tuple(labels)
        self.series = tuple(series)
        self.desc = desc
        self.x_title = x_title
        self.width = width
        self.height = height
        self.format_value = format_value
        self.format_tick = format_tick
        self.max_label_chars = max_label_chars
        self._validate()

    def _validate(self) -> None:
        """Hook for subclasses to reject series their geometry cannot draw."""

    # -- frame ----------------------------------------------------------------------------
    @property
    def left(self) -> float:
        return self.margin_left

    @property
    def right(self) -> float:
        return self.width - self.margin_right

    @property
    def top(self) -> float:
        return self.margin_top

    @property
    def bottom(self) -> float:
        return self.height - self.margin_bottom

    @property
    def plot_width(self) -> float:
        return self.right - self.left

    @property
    def plot_height(self) -> float:
        return self.bottom - self.top

    @property
    def tick_x(self) -> float:
        return self.left - 8.0

    @property
    def label_y(self) -> float:
        return self.height - 8.0

    @property
    def title_id(self) -> str:
        return f"chart-{self.key}-title"

    @property
    def desc_id(self) -> str:
        return f"chart-{self.key}-desc"

    @property
    def is_empty(self) -> bool:
        return all(v is None for s in self.series for v in s.values)

    # -- scale ----------------------------------------------------------------------------
    def _domain(self) -> tuple[float, float]:
        present = [v for s in self.series for v in s.values if v is not None]
        return (min(present), max(present)) if present else (0.0, 0.0)

    @cached_property
    def _scale(self) -> tuple[float, float, float]:
        return nice_scale(*self._domain())

    def y(self, value: float) -> float:
        start, stop, _ = self._scale
        return round1(self.bottom - (value - start) / (stop - start) * self.plot_height)

    @property
    def zero_y(self) -> float:
        return self.y(0.0)

    @property
    def y_ticks(self) -> list[Tick]:
        return [Tick(self.y(v), self.format_tick(v)) for v in tick_values(*self._scale)]

    # -- text -----------------------------------------------------------------------------
    def fmt(self, value: float | None) -> str:
        return MISSING if value is None else self.format_value(value)

    def _point_label(self, i: int) -> str:
        values = ", ".join(f"{s.name} {self.fmt(s.values[i])}" for s in self.series)
        return f"{self.labels[i]}: {values}"

    def _axis_labels(self, centres: Sequence[float], gap: float) -> list[AxisLabel]:
        keep, room = _thin(len(centres), gap, self.label_gap)
        chars = min(self.max_label_chars, max(1, int(room / _CHAR_PX)))
        return [
            AxisLabel(centres[i], _truncate(self.labels[i], chars), self.labels[i]) for i in keep
        ]

    @property
    def table_rows(self) -> list[tuple[str, list[str]]]:
        return [
            (label, [self.fmt(s.values[i]) for s in self.series])
            for i, label in enumerate(self.labels)
        ]


class LineChart(_XYChart):
    """One 2px line per series; series 2 is also dashed so it never relies on colour alone."""

    kind = "line"

    @cached_property
    def xs(self) -> list[float]:
        n = len(self.labels)
        if n == 1:
            return [round1(self.left + self.plot_width / 2)]
        gap = self.plot_width / (n - 1)
        return [round1(self.left + i * gap) for i in range(n)]

    @property
    def _gap(self) -> float:
        n = len(self.labels)
        return self.plot_width / (n - 1) if n > 1 else self.plot_width

    @property
    def x_labels(self) -> list[AxisLabel]:
        return self._axis_labels(self.xs, self._gap)

    @property
    def paths(self) -> list[LinePath]:
        out = []
        for idx, s in enumerate(self.series, start=1):
            parts: list[str] = []
            pen_down = False
            for x, v in zip(self.xs, s.values, strict=True):
                if v is None:
                    pen_down = False
                    continue
                parts.append(f"{'L' if pen_down else 'M'}{x} {self.y(v)}")
                pen_down = True
            if parts:
                out.append(LinePath(" ".join(parts), f"s{idx}", dashed=idx == _DASHED_SERIES))
        return out

    @property
    def end_labels(self) -> list[TextMark]:
        """Series names at the line ends, when they fit; with 3+ series the legend carries them."""
        if len(self.series) > _END_LABEL_MAX_SERIES:
            return []
        placed: list[TextMark] = []
        for idx, s in enumerate(self.series, start=1):
            last = s.values[-1]
            if last is None:
                continue
            end_y = self.y(last)
            above = end_y - 10.0
            # With at most two labels, "below" never collides when "above" does.
            fits = all(abs(above - p.y) >= _LABEL_LINE_PX for p in placed)
            y = above if fits else end_y + 18.0
            placed.append(TextMark(self.right - 4.0, round1(y), s.name, f"s{idx}"))
        return placed

    def _tooltip(self, i: int, px: float, py: float) -> Tooltip:
        lines = [(f"{s.name} ", self.fmt(s.values[i])) for s in self.series]
        lines[0] = (f"{self.labels[i]} · {lines[0][0]}", lines[0][1])
        width = max(_TIP_MIN_PX, 20.0 + _CHAR_PX * max(len(k) + len(v) for k, v in lines))
        height = 12.0 + TIP_LINE_PX * len(lines)
        x = px + 10.0 if px + 10.0 + width <= self.right else max(0.0, px - 10.0 - width)
        return Tooltip(round1(x), round1(max(0.0, py - height - 4.0)), width, height, tuple(lines))

    @property
    def hovers(self) -> list[Hover]:
        hit_w = min(_HIT_PX, self._gap)
        out = []
        for i, px in enumerate(self.xs):
            present = [
                (idx, v) for idx, s in enumerate(self.series, 1) if (v := s.values[i]) is not None
            ]
            if not present:
                continue
            idx, value = present[0]
            py = self.y(value)
            out.append(
                Hover(
                    round1(px - hit_w / 2),
                    round1(hit_w),
                    self._point_label(i),
                    Marker(px, py, f"s{idx}"),
                    self._tooltip(i, px, py),
                )
            )
        return out


class _BandChart(_XYChart):
    """Charts drawn as one band per x label, the bar taking 60 % of the band."""

    label_gap = 48.0

    @property
    def band(self) -> float:
        return self.plot_width / max(len(self.labels), 1)

    @property
    def bar_width(self) -> float:
        return round1(self.band * 0.6)

    def bar_x(self, i: int) -> float:
        return round1(self.left + i * self.band + self.band * 0.2)

    def centre(self, i: int) -> float:
        return round1(self.left + (i + 0.5) * self.band)

    @property
    def x_labels(self) -> list[AxisLabel]:
        return self._axis_labels([self.centre(i) for i in range(len(self.labels))], self.band)


class BarChart(_BandChart):
    """Simple bars for a single series, each focusable and labelled with its value."""

    kind = "bar"

    def _validate(self) -> None:
        if len(self.series) != 1:
            raise ValueError("BarChart takes exactly one series; use StackedBarChart for more")

    @property
    def bars(self) -> list[Bar]:
        out = []
        for i, value in enumerate(self.series[0].values):
            if value is None:
                continue
            vy, zero = self.y(value), self.zero_y
            rect = Rect(self.bar_x(i), min(vy, zero), self.bar_width, round1(abs(zero - vy)), "f1")
            text = self.fmt(value)
            mark = None
            if len(text) * _CHAR_PX <= self.band:
                ty = vy - 6.0 if value >= 0 else vy + 16.0
                mark = TextMark(self.centre(i), round1(ty), text)
            out.append(Bar(rect, f"{self.labels[i]}: {text}", mark))
        return out


class StackedBarChart(_BandChart):
    """One stack per x label, one segment per series, separated by a 1px surface line."""

    kind = "stacked_bar"

    def _validate(self) -> None:
        if any(v is not None and v < 0 for s in self.series for v in s.values):
            raise ValueError("StackedBarChart values must be zero or positive")

    def _domain(self) -> tuple[float, float]:
        totals = [sum(s.values[i] or 0.0 for s in self.series) for i in range(len(self.labels))]
        return 0.0, max(totals, default=0.0)

    @property
    def stacks(self) -> list[Stack]:
        out = []
        for i in range(len(self.labels)):
            x, total, segments = self.bar_x(i), 0.0, []
            for idx, s in enumerate(self.series, start=1):
                value = s.values[i]
                if not value:
                    continue
                y0, y1 = self.y(total), self.y(total + value)
                segments.append(Rect(x, y1, self.bar_width, round1(y0 - y1), f"f{idx}"))
                total += value
            if segments:
                out.append(Stack(tuple(segments), Hover(x, self.bar_width, self._point_label(i))))
        return out


class Sparkline:
    """A bare trend line for stat cards: no axes, min-to-max scaled, last point marked."""

    kind = "sparkline"
    pad_x: ClassVar[float] = 2.0
    pad_y: ClassVar[float] = 4.0

    def __init__(
        self,
        values: Sequence[float | None],
        *,
        key: str | None = None,
        title: str = "",
        width: int = 200,
        height: int = 40,
    ) -> None:
        if key is not None and not _KEY.match(key):
            raise ValueError(f"chart key must match {_KEY.pattern!r}, got {key!r}")
        self.values = tuple(values)
        self.key = key
        self.title = title
        self.width = width
        self.height = height

    @property
    def is_empty(self) -> bool:
        return all(v is None for v in self.values)

    @cached_property
    def points(self) -> list[tuple[float, float] | None]:
        present = [v for v in self.values if v is not None]
        if not present:
            return []
        low, high = min(present), max(present)
        n = len(self.values)
        span_x = self.width - 2 * self.pad_x
        span_y = self.height - 2 * self.pad_y
        out: list[tuple[float, float] | None] = []
        for i, v in enumerate(self.values):
            if v is None:
                out.append(None)
                continue
            x = self.pad_x + (i * span_x / (n - 1) if n > 1 else span_x / 2)
            frac = (v - low) / (high - low) if high > low else 0.5
            out.append((round1(x), round1(self.height - self.pad_y - frac * span_y)))
        return out

    @property
    def d(self) -> str:
        parts, pen_down = [], False
        for point in self.points:
            if point is None:
                pen_down = False
                continue
            parts.append(f"{'L' if pen_down else 'M'}{point[0]} {point[1]}")
            pen_down = True
        return " ".join(parts)

    @property
    def end(self) -> tuple[float, float] | None:
        return next((p for p in reversed(self.points) if p is not None), None)


Chart = LineChart | BarChart | StackedBarChart

__all__ = [
    "MAX_SERIES",
    "Bar",
    "BarChart",
    "Chart",
    "LineChart",
    "PeriodOption",
    "Series",
    "Sparkline",
    "StackedBarChart",
]
