"""Unit tests for ``hyperadmin_reports.grid`` (headers, cell kinds, totals, bands)."""

from __future__ import annotations

from datetime import datetime
from typing import Any

import pytest
from sqlmodel import Field, SQLModel

from hyperadmin_reports import (
    Count,
    Group,
    Many2One,
    Max,
    Min,
    ReportResult,
    ReportView,
    StringAggComma,
    Sum,
    TimeBucket,
    build_grid,
    flatten_grid,
)
from hyperadmin_reports.grid import GridCell, HeaderCell, cell_kind


class GrSupplier(SQLModel, table=True):
    __tablename__ = "test_report_grid_supplier"

    id: int | None = Field(default=None, primary_key=True)
    name: str


class GrOrder(SQLModel, table=True):
    __tablename__ = "test_report_grid_order"

    id: int | None = Field(default=None, primary_key=True)
    sku: str
    region: str
    amount: int
    created_at: datetime
    supplier_id: int | None = Field(default=None, foreign_key="test_report_grid_supplier.id")


class ByQuarter(ReportView):
    slug = "by-quarter"
    model = GrOrder
    rows = [Group("sku")]
    cols = [TimeBucket("created_at", period="quarter")]
    values = [Sum("amount")]


class ByYearTwoValues(ReportView):
    slug = "by-year"
    model = GrOrder
    rows = [Group("sku")]
    cols = [TimeBucket("created_at", period="year")]
    values = [Sum("amount"), Count()]


class ByRegionAndMonth(ReportView):
    slug = "by-region-month"
    model = GrOrder
    rows = [Group("region"), Group("sku")]
    cols = [Group("region"), TimeBucket("created_at", period="month")]
    values = [Min("amount")]


class EveryAggregate(ReportView):
    slug = "every-aggregate"
    model = GrOrder
    rows = [Group("sku")]
    values = [Count(), Sum("amount"), Min("amount"), Max("amount"), StringAggComma("region")]


class Related(ReportView):
    slug = "related"
    model = GrOrder
    rows = [Group("sku")]
    values = [Many2One("supplier_id")]


def _result(
    report: type[ReportView],
    records: list[dict[str, Any]],
    *,
    periods: dict[str, Any] | None = None,
) -> ReportResult:
    return ReportResult(
        records=records,
        rows=[d.name for d in report.rows],
        cols=[d.name for d in report.cols],
        values=[a.name for a in report.values],
        periods=periods or {},
        fills={a.name: a.empty for a in report.values},
    )


def _values(cells: list[GridCell]) -> list[Any]:
    return [c.value for c in cells]


def test_quarter_headers_have_a_year_level_and_abbreviated_buckets() -> None:
    """
    Scenario: multi-level column headers (year → bucket) with abbreviated labels
      Given a quarter bucket spanning two years
      When  the grid is built
      Then  the first header row has one "year" cell per year spanning its quarters
      And   the leaf row abbreviates "2025-Q1" to "Q1" with the full key as title
      And   the first column of each year starts a group; exports keep the full labels
    """
    grid = build_grid(
        ByQuarter,
        _result(
            ByQuarter,
            [
                {"sku": "A", "created_at": "2025-Q1", "sum_amount": 10},
                {"sku": "A", "created_at": "2025-Q4", "sum_amount": 20},
                {"sku": "B", "created_at": "2026-Q1", "sum_amount": 5},
            ],
            periods={"created_at": "quarter"},
        ),
    )

    assert grid.levels == 2
    assert grid.header_rows[0] == [
        HeaderCell(label="2025", span=2, start=True),
        HeaderCell(label="2026", span=1, start=True),
    ]
    assert grid.header_rows[1] == [
        HeaderCell(label="Q1", title="2025-Q1", sr_suffix=" 2025", start=True, num=True),
        HeaderCell(label="Q4", title="2025-Q4", sr_suffix=" 2025", start=False, num=True),
        HeaderCell(label="Q1", title="2026-Q1", sr_suffix=" 2026", start=True, num=True),
    ]
    assert grid.column_flags == [(True, True), (False, True), (True, True)]
    assert grid.column_labels == ["2025-Q1", "2025-Q4", "2026-Q1"]
    assert grid.row_labels == ["Sku"]
    assert grid.key_items[0] == "— no rows in that quarter"


def test_totals_fold_sums_per_row_column_and_grand() -> None:
    """
    Scenario: row, column and grand totals for a Sum
      Given a sku x quarter grid with a missing cell and a zero cell
      When  the grid is built and flattened
      Then  each row ends with its total, the footer holds the column totals
      And   the grand total closes the footer; an empty cell is null, a zero is zero
    """
    grid = build_grid(
        ByQuarter,
        _result(
            ByQuarter,
            [
                {"sku": "A", "created_at": "2025-Q1", "sum_amount": 10},
                {"sku": "A", "created_at": "2025-Q2", "sum_amount": 0},
                {"sku": "B", "created_at": "2025-Q2", "sum_amount": 5},
            ],
            periods={"created_at": "quarter"},
        ),
    )

    assert grid.has_row_totals and grid.has_col_totals
    assert grid.total_labels == ["Total"]
    assert [(c.value, c.kind) for c in grid.rows[0].cells] == [(10, "num"), (0, "zero")]
    assert [(c.value, c.kind) for c in grid.rows[1].cells] == [(None, "null"), (5, "num")]
    assert _values(grid.rows[0].totals) == [10]
    assert _values(grid.rows[1].totals) == [5]
    assert _values(grid.col_totals) == [10, 5]
    assert _values(grid.grand_totals) == [15]
    assert grid.width == 4
    table = flatten_grid(grid)
    assert table.header == ["Sku", "2025-Q1", "2025-Q2", "Total"]
    assert table.rows == [["A", 10, 0, 10], ["B", None, 5, 5], ["Total", 10, 5, 15]]


def test_year_bucket_with_two_values_has_leaf_and_aggregate_levels() -> None:
    """
    Scenario: several aggregates under a year bucket
      Given Sum and Count over a year bucket
      When  the grid is built
      Then  there is no year group level, the bucket row spans both aggregates
      And   a third row names each aggregate; the totals column is labelled per aggregate
    """
    grid = build_grid(
        ByYearTwoValues,
        _result(
            ByYearTwoValues,
            [{"sku": "A", "created_at": "2025", "sum_amount": 10, "count_all": 2}],
            periods={"created_at": "year"},
        ),
    )

    assert grid.header_rows == [
        [HeaderCell(label="2025", span=2, start=True)],
        [
            HeaderCell(label="Sum of Amount", start=True, num=True),
            HeaderCell(label="Count of Rows", start=False, num=True),
        ],
    ]
    assert grid.column_labels == ["2025 / Sum of Amount", "2025 / Count of Rows"]
    assert grid.total_labels == ["Total / Sum of Amount", "Total / Count of Rows"]
    assert _values(grid.rows[0].totals) == [10, 2]
    assert _values(grid.grand_totals) == [10, 2]


def test_group_and_month_columns_nest_under_the_year_and_rows_band_by_first_key() -> None:
    """
    Scenario: a plain column dimension next to a month bucket, two row dimensions
      Given cols=[region, month] and rows=[region, sku] with a Min aggregate
      When  the grid is built
      Then  the year is the group level and the leaf joins region and month
      And   rows are banded by region, each row labelled by its sku
      And   the Min totals are the smallest values
    """
    grid = build_grid(
        ByRegionAndMonth,
        _result(
            ByRegionAndMonth,
            [
                {"region": "EU", "sku": "A", "created_at": "2025-01", "min_amount": 3},
                {"region": "EU", "sku": "B", "created_at": "2025-02", "min_amount": 1},
                {"region": "US", "sku": "A", "created_at": "2025-01", "min_amount": 7},
            ],
            periods={"created_at": "month"},
        ),
    )

    assert [c.label for c in grid.header_rows[0]] == ["2025"]
    assert [c.label for c in grid.header_rows[1]] == [
        "EU / 2025-01",
        "EU / 2025-02",
        "US / 2025-01",
    ]
    assert grid.header_rows[1][0].title is None
    assert grid.grouped_rows
    assert [(band, [r.label for r in rows]) for band, rows in grid.bands()] == [
        ("EU", ["A", "B"]),
        ("US", ["A"]),
    ]
    assert grid.row_labels == ["Region", "Sku"]
    assert _values(grid.rows[0].totals) == [3]
    assert _values(grid.col_totals) == [3, 1, 7]
    assert _values(grid.grand_totals) == [1]
    assert flatten_grid(grid).rows[-1] == ["Total", None, 3, 1, 7, 1]


def test_report_without_columns_has_column_totals_only_where_the_aggregate_allows() -> None:
    """
    Scenario: every aggregate type without a column dimension
      Given Count, Sum, Min, Max and a comma-joined list
      When  the grid is built
      Then  the single header row names the aggregates, lists are not numeric
      And   there is no totals column; the footer totals all but the list
    """
    grid = build_grid(
        EveryAggregate,
        _result(
            EveryAggregate,
            [
                {
                    "sku": "A",
                    "count_all": 2,
                    "sum_amount": 0,
                    "min_amount": 1,
                    "max_amount": 9,
                    "string_agg_region": "EU, US",
                },
                {
                    "sku": "B",
                    "count_all": 0,
                    "sum_amount": None,
                    "min_amount": None,
                    "max_amount": None,
                    "string_agg_region": None,
                },
            ],
        ),
    )

    assert grid.levels == 1
    assert [c.num for c in grid.header_rows[0]] == [True, True, True, True, False]
    assert not grid.has_row_totals
    assert grid.rows[0].totals == []
    assert [c.kind for c in grid.rows[0].cells] == ["num", "zero", "num", "num", "list"]
    assert [c.kind for c in grid.rows[1].cells] == ["zero", "null", "null", "null", "null"]
    assert [(c.value, c.kind) for c in grid.col_totals] == [
        (2, "num"),
        (0, "zero"),
        (1, "num"),
        (9, "num"),
        (None, "null"),
    ]
    assert grid.grand_totals == []
    assert grid.key_items == [
        "— no rows in that group",
        "0 rows that add up to zero",
        "Gr order · count of rows, sum of amount, min of amount, max of amount, list of region",
    ]
    assert flatten_grid(grid).rows[-1] == ["Total", 2, 0, 1, 9, None]
    assert not grid.bands()[0][0]


def test_related_record_cells_are_not_totalled_and_an_empty_grid_has_no_total_row() -> None:
    """
    Scenario: Many2One values and an empty result
      Given a Many2One-only report
      When  the grid is built with and without records
      Then  cells are "rel", column totals are null and the footer is omitted
      And   an empty result flattens to the header alone
    """
    grid = build_grid(Related, _result(Related, [{"sku": "A", "supplier_id": "Acme"}]))

    assert [c.kind for c in grid.rows[0].cells] == ["rel"]
    assert [c.is_null for c in grid.col_totals] == [True]
    assert not grid.has_col_totals
    assert flatten_grid(grid).rows == [["A", "Acme"]]
    assert flatten_grid(build_grid(Related, _result(Related, []))).rows == []


@pytest.mark.parametrize(
    ("agg", "value", "expected"),
    [
        (Sum("amount"), None, "null"),
        (StringAggComma("region"), "a, b", "list"),
        (Many2One("supplier_id"), 4, "rel"),
        (Sum("amount"), True, "text"),
        (Min("created_at"), "2025-01-01", "text"),
        (Count(), 0, "zero"),
        (Max("amount"), 2.5, "num"),
    ],
)
def test_cell_kind(agg: Any, value: Any, expected: str) -> None:
    assert cell_kind(agg, value) == expected


def test_aggregate_totals_fold_or_decline() -> None:
    """
    Scenario: which aggregates can be totalled
      Then  Sum and Count add, Min and Max pick the extreme, skipping empty cells
      And   a comma-joined list or a related record never totals
      And   an all-empty line totals to None
    """
    assert Sum("amount").total([1, None, 2]) == 3
    assert Count().total([0, 4]) == 4
    assert Min("amount").total([3, None, 1]) == 1
    assert Max("amount").total([3, None, 1]) == 3
    assert Sum("amount").total([None, None]) is None
    assert StringAggComma("region").total(["a"]) is None
    assert Many2One("supplier_id").total([1]) is None
    assert not StringAggComma("region").totals
