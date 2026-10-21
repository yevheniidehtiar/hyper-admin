"""The report page's view model: a crosstab grid with headers, cell kinds and totals.

:func:`build_grid` turns a :class:`~hyperadmin_reports.view.ReportResult` into
one :class:`ReportGrid` the ``reports/detail.html`` template renders and the
exports flatten (:func:`hyperadmin_reports.export.build_table`), so the page,
the CSV and the XLSX never disagree on a header, a cell or a total.

Cells carry a *kind* so the template can tell a missing bucket (``null``,
printed as "—" with "no data" for screen readers) from rows that add up to
zero (``zero``, printed in normal text), and can truncate comma-joined lists.
Totals exist only for aggregates whose
:attr:`~hyperadmin_reports.aggregates.Aggregate.totals` is true; they are folded
from the pivoted cells, never re-queried.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal
from typing import TYPE_CHECKING, Any, Literal

from hyperadmin_reports.aggregates import Many2One, StringAggComma
from hyperadmin_reports.bucketing import TimeBucket

if TYPE_CHECKING:
    from collections.abc import Iterable, Sequence

    from hyperadmin_reports.aggregates import Aggregate
    from hyperadmin_reports.crosstab import Key, Pivot
    from hyperadmin_reports.view import ReportResult, ReportView

CellKind = Literal["null", "zero", "num", "list", "rel", "text"]

#: Joins the parts of a multi-dimension column key in headers and exports.
KEY_SEPARATOR = " / "
TOTAL_LABEL = "Total"


@dataclass(frozen=True)
class GridCell:
    """One rendered value and how to show it."""

    value: Any
    kind: CellKind

    @property
    def is_null(self) -> bool:
        return self.kind == "null"


@dataclass(frozen=True)
class HeaderCell:
    """A ``<th>`` of the column header: ``span`` columns wide, ``title`` when abbreviated."""

    label: str
    span: int = 1
    title: str | None = None
    sr_suffix: str | None = None
    start: bool = False
    num: bool = False


@dataclass(frozen=True)
class GridRow:
    """One data row: its dimension keys, cells (one per data column) and row totals."""

    keys: tuple[Any, ...]
    cells: list[GridCell]
    totals: list[GridCell]

    @property
    def group(self) -> Any:
        """The first row dimension's value: the band rows are grouped under."""
        return self.keys[0]

    @property
    def label(self) -> str:
        """The row header: every key after the group, or the single key."""
        keys = self.keys[1:] if len(self.keys) > 1 else self.keys
        return KEY_SEPARATOR.join(_text(k) for k in keys)


@dataclass(frozen=True)
class ReportGrid:
    """A pivoted report ready to render.

    ``header_rows`` holds one to three rows: the year (or outer key) level, the
    bucket level, then the aggregate level when the report has several
    aggregates under column keys. The last row has one cell per data column.
    ``column_labels`` are the flat per-column labels the exports use.
    """

    row_labels: list[str]
    header_rows: list[list[HeaderCell]]
    column_labels: list[str]
    rows: list[GridRow]
    col_totals: list[GridCell]
    grand_totals: list[GridCell]
    total_labels: list[str]
    grouped_rows: bool = False
    key_items: list[str] = field(default_factory=list)

    @property
    def levels(self) -> int:
        return len(self.header_rows)

    @property
    def width(self) -> int:
        """Number of cells in one body row, for ``colspan``."""
        return 1 + len(self.column_labels) + len(self.total_labels)

    @property
    def column_flags(self) -> list[tuple[bool, bool]]:
        """``(starts a group, numeric)`` per data column, read off the leaf header row."""
        return [
            (cell.start and i == 0, cell.num)
            for cell in self.header_rows[-1]
            for i in range(cell.span)
        ]

    @property
    def has_row_totals(self) -> bool:
        return bool(self.total_labels)

    @property
    def has_col_totals(self) -> bool:
        return bool(self.rows) and any(not c.is_null for c in self.col_totals)

    def bands(self) -> list[tuple[Any, list[GridRow]]]:
        """Rows grouped by their first key, in order (one band when not grouped)."""
        if not self.grouped_rows:
            return [(None, list(self.rows))]
        bands: list[tuple[Any, list[GridRow]]] = []
        for row in self.rows:
            if not bands or bands[-1][0] != row.group:
                bands.append((row.group, []))
            bands[-1][1].append(row)
        return bands


def _text(value: Any) -> str:
    return "" if value is None else str(value)


def cell_kind(agg: Aggregate, value: Any) -> CellKind:
    """How ``value`` of ``agg`` renders; ``None`` is always ``null``."""
    if value is None:
        return "null"
    if isinstance(agg, StringAggComma):
        return "list"
    if isinstance(agg, Many2One):
        return "rel"
    if isinstance(value, bool) or not isinstance(value, (int, float, Decimal)):
        return "text"
    return "zero" if value == 0 else "num"


def _is_numeric(agg: Aggregate) -> bool:
    return not isinstance(agg, (StringAggComma, Many2One))


def _column_levels(
    report: type[ReportView], result: ReportResult, col_keys: Sequence[Key]
) -> tuple[list[str | None], list[HeaderCell]]:
    """Per column key: its outer group label (or ``None``) and its leaf header cell."""
    groups: list[str | None] = []
    leaves: list[HeaderCell] = []
    for key in col_keys:
        outer: list[str] = []
        leaf: list[str] = []
        title: str | None = None
        for dim, value in zip(report.cols, key):
            if isinstance(dim, TimeBucket):
                year, short = TimeBucket.split_key(value, result.periods[dim.name])
                if year is not None:
                    outer.append(year)
                if short != _text(value):
                    title = _text(value)
                leaf.append(short)
            else:
                leaf.append(_text(value))
        group = KEY_SEPARATOR.join(outer) if outer else None
        groups.append(group)
        sr_suffix = f" {group}" if title is not None and group else None
        leaves.append(HeaderCell(label=KEY_SEPARATOR.join(leaf), title=title, sr_suffix=sr_suffix))
    return groups, leaves


def _runs(labels: Iterable[str | None]) -> list[tuple[str | None, int]]:
    runs: list[tuple[str | None, int]] = []
    for label in labels:
        if runs and runs[-1][0] == label:
            runs[-1] = (label, runs[-1][1] + 1)
        else:
            runs.append((label, 1))
    return runs


def _header_rows(
    report: type[ReportView], result: ReportResult, col_keys: Sequence[Key]
) -> list[list[HeaderCell]]:
    aggs = list(report.values)
    multi = len(aggs) > 1
    if not result.cols:
        return [[HeaderCell(label=a.label, num=_is_numeric(a)) for a in aggs]]
    groups, leaves = _column_levels(report, result, col_keys)
    width = len(aggs)
    starts = [i == 0 or groups[i] != groups[i - 1] for i in range(len(col_keys))]
    rows: list[list[HeaderCell]] = []
    if any(g is not None for g in groups):
        rows.append(
            [HeaderCell(label=g or "", span=n * width, start=True) for g, n in _runs(groups)]
        )
    rows.append(
        [
            HeaderCell(
                label=leaf.label,
                span=width,
                title=leaf.title,
                sr_suffix=leaf.sr_suffix,
                start=start,
                num=not multi and _is_numeric(aggs[0]),
            )
            for leaf, start in zip(leaves, starts)
        ]
    )
    if multi:
        rows.append(
            [
                HeaderCell(label=a.label, start=start and i == 0, num=_is_numeric(a))
                for start in starts
                for i, a in enumerate(aggs)
            ]
        )
    return rows


def _column_labels(report: type[ReportView], col_keys: Sequence[Key]) -> list[str]:
    """Flat header per data column: the key joined by ``" / "``, then the aggregate when needed."""
    labels = []
    for key in col_keys:
        for agg in report.values:
            parts = [_text(value) for value in key]
            if len(report.values) > 1 or not key:
                parts.append(agg.label)
            labels.append(KEY_SEPARATOR.join(parts))
    return labels


def _key_items(report: type[ReportView], result: ReportResult) -> list[str]:
    """The lines of the key under the grid: what "—" and "0" mean, and the unit."""
    bucket = next((result.periods[d.name] for d in report.cols if d.name in result.periods), None)
    unit = bucket if bucket is not None else "group"
    return [f"— no rows in that {unit}", "0 rows that add up to zero", report.get_summary()]


def build_grid(report: type[ReportView], result: ReportResult) -> ReportGrid:
    """Pivot every aggregate of ``result`` into one grid with headers and totals.

    Row totals (and the grand total) need column keys to fold; a report with
    no column dimension gets column totals only.
    """
    aggs = list(report.values)
    pivots: list[Pivot] = [result.pivot(a.name) for a in aggs]
    col_keys = pivots[0].col_keys
    row_keys = pivots[0].row_keys
    totalled = [a for a in aggs if a.totals] if result.cols else []

    rows: list[GridRow] = []
    for row_key in row_keys:
        cells = [
            GridCell(value, cell_kind(a, value))
            for col_key in col_keys
            for a, p in zip(aggs, pivots)
            for value in (p.cell(row_key, col_key),)
        ]
        totals = [
            GridCell(total, cell_kind(a, total))
            for a, p in zip(aggs, pivots)
            if a in totalled
            for total in (a.total(p.cell(row_key, c) for c in col_keys),)
        ]
        rows.append(GridRow(keys=row_key, cells=cells, totals=totals))

    col_totals = [
        GridCell(total, cell_kind(a, total))
        for col_key in col_keys
        for a, p in zip(aggs, pivots)
        for total in (a.total(p.cell(r, col_key) for r in row_keys),)
    ]
    grand_totals = [
        GridCell(total, cell_kind(a, total))
        for i, a in enumerate(totalled)
        for total in (a.total(row.totals[i].value for row in rows),)
    ]
    labels = {dim.name: dim.label for dim in report.rows}
    return ReportGrid(
        row_labels=[labels[name] for name in result.rows],
        header_rows=_header_rows(report, result, col_keys),
        column_labels=_column_labels(report, col_keys),
        rows=rows,
        col_totals=col_totals,
        grand_totals=grand_totals,
        total_labels=[
            TOTAL_LABEL if len(totalled) == 1 else f"{TOTAL_LABEL}{KEY_SEPARATOR}{a.label}"
            for a in totalled
        ],
        grouped_rows=len(result.rows) > 1,
        key_items=_key_items(report, result),
    )
