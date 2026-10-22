"""Map a :class:`~hyperadmin_reports.view.ReportResult` onto one of the SVG chart classes.

The report's first foldable aggregate (a sum, count, minimum, maximum or average; never a
comma-joined list or a related record) is what gets drawn. The shape of the report picks
the chart:

* a time bucket on the x axis (the column dimension, else the row dimension): a **line**,
  one line per row group (or per column key);
* a single series over plain groups: a **bar**;
* rows x columns of plain groups: a **stacked bar**, one stack per row, one segment per
  column key.

The design caps a chart at six series and keeps the plot readable, so extra series are
dropped (largest totals kept), bar charts keep the top 12 groups and line charts the latest
36 points; the caption says so.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import TYPE_CHECKING, Any

from hyperadmin_reports.bucketing import TimeBucket
from hyperadmin_reports.charts import BarChart, Chart, LineChart, Series, StackedBarChart
from hyperadmin_reports.charts.geometry import MAX_SERIES, MISSING
from hyperadmin_reports.grid import KEY_SEPARATOR

if TYPE_CHECKING:
    from collections.abc import Callable, Sequence

    from hyperadmin_reports.aggregates import Aggregate
    from hyperadmin_reports.crosstab import Key
    from hyperadmin_reports.view import ReportResult, ReportView

#: Most groups a bar or stacked bar shows (the rest are left out; the caption says so).
MAX_BARS = 12
#: Most points a line shows (the latest ones).
MAX_POINTS = 36


class ChartUnavailableError(Exception):
    """The report cannot be drawn as a chart; the message says why, in a sentence."""


@dataclass(frozen=True)
class ReportChart:
    """A chart and the muted caption the frame prints under its title."""

    chart: Chart
    caption: str


def chart_value(report: type[ReportView]) -> Aggregate | None:
    """The aggregate the chart draws: the first one that can be folded into totals."""
    return next((a for a in report.values if a.totals), None)


def chartable(report: type[ReportView]) -> bool:
    """Whether ``report`` has a dimension to put on the x axis and a value to draw."""
    return bool((report.rows or report.cols) and chart_value(report) is not None)


def placeholder(report: type[ReportView]) -> BarChart:
    """An empty chart the frame uses for its loading state (only its size and title show)."""
    return BarChart(report.slug, title=report.get_label(), labels=(), series=[Series("", ())])


def _number(value: Any) -> float | None:
    if isinstance(value, bool) or not isinstance(value, (int, float, Decimal)):
        return None
    return float(value)


def _label(key: Sequence[Any]) -> str:
    return KEY_SEPARATOR.join(MISSING if part is None else str(part) for part in key)


def _is_time(dims: Sequence[Any]) -> bool:
    return any(isinstance(d, TimeBucket) for d in dims)


def build_chart(report: type[ReportView], result: ReportResult) -> ReportChart:
    """The chart for ``result``; raises :class:`ChartUnavailableError` when it cannot be drawn."""
    agg = chart_value(report)
    if agg is None or not (report.rows or report.cols):
        raise ChartUnavailableError("This report has no numeric value to chart.")
    pivot = result.pivot(agg.name)
    by_name = {d.name: d for d in (*report.rows, *report.cols)}
    row_dims = [by_name[n] for n in pivot.rows]
    col_dims = [by_name[n] for n in pivot.cols]

    # Which dimension runs along the x axis, and which one (if any) splits it into series.
    x_on_cols = not row_dims or (bool(col_dims) and _is_time(col_dims) and not _is_time(row_dims))
    split = bool(row_dims and col_dims)
    x_dims = col_dims if x_on_cols else row_dims
    x_keys = pivot.col_keys if x_on_cols else pivot.row_keys
    s_keys: list[Key | None] = list(pivot.row_keys if x_on_cols else pivot.col_keys)
    if not split:
        s_keys = [None]

    def value(x: Key, s: Key | None) -> float | None:
        other = s or ()
        return _number(pivot.cell(other, x) if x_on_cols else pivot.cell(x, other))

    names = [_label(k or ()) for k in s_keys] if split else [agg.label]
    columns = [[value(x, s) for x in x_keys] for s in s_keys]
    labels = [_label(k) for k in x_keys]
    notes: list[str] = []

    line = _is_time(x_dims)
    if len(columns) > MAX_SERIES:
        by_size = sorted(range(len(columns)), key=lambda i: -sum(abs(v or 0.0) for v in columns[i]))
        keep = sorted(by_size[:MAX_SERIES])
        notes.append(f"{MAX_SERIES} of {len(columns)} series")
        names, columns = [names[i] for i in keep], [columns[i] for i in keep]
    if line and len(labels) > MAX_POINTS:
        notes.append(f"latest {MAX_POINTS} of {len(labels)}")
        labels, columns = labels[-MAX_POINTS:], [c[-MAX_POINTS:] for c in columns]
    elif not line and len(labels) > MAX_BARS:
        totals = [sum(c[i] or 0.0 for c in columns) for i in range(len(labels))]
        top = sorted(sorted(range(len(labels)), key=lambda i: -totals[i])[:MAX_BARS])
        notes.append(f"top {MAX_BARS} of {len(labels)}")
        labels, columns = [labels[i] for i in top], [[c[i] for i in top] for c in columns]

    series = [Series(n, c) for n, c in zip(names, columns, strict=True)]
    x_title = KEY_SEPARATOR.join(d.label for d in x_dims)
    kind: Callable[..., Chart] = (
        LineChart if line else BarChart if len(series) == 1 else StackedBarChart
    )
    try:
        chart = kind(
            report.slug,
            title=report.get_label(),
            labels=labels,
            series=series,
            x_title=x_title,
            desc=_describe(agg, x_title, labels, columns),
        )
    except ValueError as exc:  # a stacked bar cannot draw negative segments
        raise ChartUnavailableError("Stacked bars cannot show negative values.") from exc
    return ReportChart(chart, " · ".join([agg.label, *notes]))


def _describe(
    agg: Aggregate, x_title: str, labels: list[str], columns: list[list[float | None]]
) -> str:
    """One sentence for ``<desc>``: what is drawn and where its largest value sits."""
    peaks = [(v, labels[i]) for c in columns for i, v in enumerate(c) if v is not None]
    sentence = f"{agg.label} by {x_title.lower()}"
    if not peaks:
        return f"{sentence}; no data."
    top, at = max(peaks)
    return f"{sentence}; the largest value, {top:g}, is at {at}."
