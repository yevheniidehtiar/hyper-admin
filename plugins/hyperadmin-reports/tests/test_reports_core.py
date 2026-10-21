"""Unit tests for the ``hyperadmin_reports`` core (aggregates, crosstab, bucketing, run).

Scenarios map 1:1 to
``.meta/epics/epic-v054-olap-reporting/stories/featreports-aggregates-and-crosstab-core.md``;
the remaining tests cover per-aggregate / per-dialect SQL and edge cases from
``docs/specs/olap-reporting.md``.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from datetime import date, datetime, timezone
from typing import Any

import pytest
import sqlalchemy as sa
from sqlalchemy import DateTime, column
from sqlalchemy.dialects import mssql, mysql, postgresql, sqlite
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlmodel import Field, SQLModel

from hyperadmin_reports import (
    AUTO_THRESHOLDS,
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
    pivot,
    resolve_period,
)
from hyperadmin_reports.bucketing import describe_span, period_for_days, range_days

pytestmark = pytest.mark.anyio

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

_plain_table = sa.Table(
    "test_reports_plain_ref",
    SQLModel.metadata,
    sa.Column("id", sa.Integer, primary_key=True),
)


class ReportSupplier(SQLModel, table=True):
    __tablename__ = "test_reports_supplier"

    id: int | None = Field(default=None, primary_key=True)
    name: str


class ReportOrder(SQLModel, table=True):
    __tablename__ = "test_reports_order"

    id: int | None = Field(default=None, primary_key=True)
    sku: str
    amount: int
    created_at: datetime
    supplier_id: int | None = Field(default=None, foreign_key="test_reports_supplier.id")
    plain_id: int | None = Field(default=None, foreign_key="test_reports_plain_ref.id")


class SkuByMonth(ReportView):
    slug = "orders-revenue"
    model = ReportOrder
    rows = [Group("sku")]
    cols = [TimeBucket("created_at", period="month")]
    values = [Sum("amount"), Count()]


class SkuAuto(ReportView):
    slug = "orders-auto"
    model = ReportOrder
    rows = [Group("sku")]
    cols = [TimeBucket("created_at", period="auto")]
    values = [Sum("amount")]


ORDERS: list[tuple[str, int, datetime, int | None]] = [
    ("A", 10, datetime(2025, 1, 5, tzinfo=timezone.utc), 1),
    ("A", 20, datetime(2025, 2, 10, tzinfo=timezone.utc), 1),
    ("B", 5, datetime(2025, 1, 20, tzinfo=timezone.utc), 2),
    ("A", 7, datetime(2025, 11, 30, tzinfo=timezone.utc), 1),
]


@pytest.fixture
async def engine() -> AsyncIterator[AsyncEngine]:
    eng = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with eng.begin() as conn:
        await conn.run_sync(SQLModel.metadata.create_all)
    yield eng
    await eng.dispose()


@pytest.fixture
async def session(engine: AsyncEngine) -> AsyncIterator[AsyncSession]:
    async with AsyncSession(engine) as s:
        yield s


@pytest.fixture
async def seeded(session: AsyncSession) -> AsyncSession:
    session.add_all([ReportSupplier(id=1, name="Acme"), ReportSupplier(id=2, name="Globex")])
    session.add_all(
        ReportOrder(sku=sku, amount=amount, created_at=at, supplier_id=sup)
        for sku, amount, at, sup in ORDERS
    )
    await session.commit()
    return session


# ---------------------------------------------------------------------------
# Scenario: Sum aggregate compiles to SUM(field)
# ---------------------------------------------------------------------------


def test_sum_aggregate_compiles_to_sum_field() -> None:
    # Given
    agg = Sum(field="amount")
    # When
    sql = agg.sql(dialect="postgresql")
    # Then
    assert sql == 'SUM("amount")'


@pytest.mark.parametrize(
    ("agg", "dialect", "expected"),
    [
        (Sum("amount"), "sqlite", 'SUM("amount")'),
        (Sum("amount"), "mysql", "SUM(`amount`)"),
        (Count(), "postgresql", "COUNT(*)"),
        (Count("id"), "postgresql", 'COUNT("id")'),
        (Min("amount"), "postgresql", 'MIN("amount")'),
        (Max("amount"), "sqlite", 'MAX("amount")'),
        (Many2One("supplier_id"), "postgresql", 'MAX("supplier_id")'),
        (StringAggComma("sku"), "postgresql", "STRING_AGG(CAST(\"sku\" AS TEXT), ', ')"),
        (StringAggComma("sku"), "sqlite", "GROUP_CONCAT(\"sku\", ', ')"),
        (StringAggComma("sku"), "mysql", "GROUP_CONCAT(`sku` SEPARATOR ', ')"),
        (StringAggComma("sku"), "mariadb", "GROUP_CONCAT(`sku` SEPARATOR ', ')"),
    ],
)
def test_aggregate_sql_per_dialect(agg: Any, dialect: str, expected: str) -> None:
    assert agg.sql(dialect) == expected


def test_aggregate_names_labels_and_empty_cells() -> None:
    assert [a.name for a in (Sum("amount"), Count(), StringAggComma("sku"))] == [
        "sum_amount",
        "count_all",
        "string_agg_sku",
    ]
    assert Sum("amount").label == "Sum of Amount"
    assert Count().label == "Count of Rows"
    assert StringAggComma("sku").label == "List of Sku"
    assert Max("amount", label="Peak").label == "Peak"
    assert Many2One("supplier_id").name == "supplier_id"
    assert Many2One("supplier_id").label == "Supplier"
    assert Many2One("supplier_id", label="Vendor").label == "Vendor"
    assert Count.empty == 0
    assert Sum.empty is None
    assert repr(Sum("amount")) == "Sum('amount')"


def test_unknown_dialect_raises() -> None:
    with pytest.raises(ValueError, match="Unknown SQL dialect"):
        Sum("amount").sql("nosuchdb")


def test_string_agg_unsupported_dialect_raises() -> None:
    with pytest.raises(ValueError, match="no SQL for dialect 'mssql'"):
        StringAggComma("sku").sql("mssql")


# ---------------------------------------------------------------------------
# Scenario: pivot builder pivots (sku, month) → row × col grid
# ---------------------------------------------------------------------------


def test_pivot_builder_pivots_sku_month_grid() -> None:
    # Given
    records = [
        {"sku": "A", "month": "2026-01", "total": 10},
        {"sku": "A", "month": "2026-02", "total": 20},
        {"sku": "B", "month": "2026-01", "total": 5},
    ]
    # When
    grid = pivot(records, rows=["sku"], cols=["month"], value="total")
    # Then
    assert grid.grid == {("A", "2026-01"): 10, ("A", "2026-02"): 20, ("B", "2026-01"): 5}
    assert grid.row_keys == [("A",), ("B",)]
    assert grid.col_keys == [("2026-01",), ("2026-02",)]
    assert grid.cell(("B",), ("2026-02",)) is None
    assert grid.table() == [[10, 20], [5, None]]


def test_pivot_fills_missing_cells_and_handles_no_columns() -> None:
    p = pivot([{"sku": "A", "n": 3}], rows=["sku"], cols=[], value="n", fill=0)
    assert p.col_keys == [()]
    assert p.cell(("A",)) == 3
    assert p.cell(("Z",)) == 0


def test_pivot_sorts_none_last_and_keeps_order_for_unorderable_keys() -> None:
    p = pivot(
        [{"k": None, "v": 1}, {"k": "b", "v": 2}, {"k": "a", "v": 3}],
        rows=["k"],
        cols=[],
        value="v",
    )
    assert p.row_keys == [("a",), ("b",), (None,)]
    mixed = pivot([{"k": "x", "v": 1}, {"k": 1, "v": 2}], rows=["k"], cols=[], value="v")
    assert mixed.row_keys == [("x",), (1,)]


def test_pivot_rejects_ungrouped_records() -> None:
    with pytest.raises(ValueError, match="Duplicate pivot cell"):
        pivot([{"k": "a", "v": 1}, {"k": "a", "v": 2}], rows=["k"], cols=[], value="v")


# ---------------------------------------------------------------------------
# Scenario: auto bucketing picks quarter for 365-day range
# ---------------------------------------------------------------------------


def test_auto_bucketing_picks_quarter_for_365_day_range() -> None:
    # Given
    bucket = TimeBucket("created_at", period="auto")
    # When
    period = bucket.resolve_period((date(2025, 1, 1), date(2025, 12, 31)))
    # Then
    assert period == "quarter"


@pytest.mark.parametrize(
    ("start", "end", "expected"),
    [
        (date(2026, 1, 1), date(2026, 1, 31), "day"),
        (date(2026, 1, 1), date(2026, 2, 1), "week"),
        (date(2026, 1, 1), date(2026, 3, 31), "week"),
        (date(2026, 1, 1), date(2026, 6, 30), "month"),
        (date(2026, 1, 1), date(2026, 7, 31), "quarter"),
        (date(2024, 1, 1), date(2026, 12, 31), "quarter"),
        (date(2020, 1, 1), date(2026, 12, 31), "year"),
        (datetime(2026, 1, 1, 9), "2026-01-10T00:00:00", "day"),
        (date(2026, 1, 31), date(2026, 1, 1), "day"),
    ],
)
def test_resolve_period_thresholds(start: Any, end: Any, expected: str) -> None:
    assert resolve_period((start, end)) == expected


def test_auto_thresholds_are_ascending() -> None:
    limits = [limit for limit, _ in AUTO_THRESHOLDS]
    assert limits == sorted(limits)


def test_time_bucket_fixed_period_and_auto_without_range() -> None:
    assert TimeBucket("created_at", period="week").resolve_period(None) == "week"
    assert TimeBucket("created_at", period="auto").resolve_period(None) == "year"
    assert TimeBucket("created_at").period == "month"
    assert TimeBucket("created_at").label == "Created At"
    assert TimeBucket("created_at", label="Month").label == "Month"
    assert repr(TimeBucket("created_at")) == "TimeBucket('created_at', period='month')"
    with pytest.raises(ValueError, match="Unknown TimeBucket period"):
        TimeBucket("created_at", period="decade")  # type: ignore[arg-type]


def test_time_bucket_format_key() -> None:
    assert TimeBucket.format_key("2026-01-12", "week") == "2026-W03"
    assert TimeBucket.format_key(None, "week") is None
    assert TimeBucket.format_key("2026-Q1", "quarter") == "2026-Q1"


_CREATED = column("created_at", DateTime)


@pytest.mark.parametrize(
    ("period", "expected"),
    [
        ("day", "to_char(created_at, 'YYYY-MM-DD')"),
        ("week", "to_char(date_trunc('week', created_at), 'YYYY-MM-DD')"),
        ("month", "to_char(created_at, 'YYYY-MM')"),
        ("quarter", "to_char(created_at, 'YYYY-\"Q\"Q')"),
        ("year", "to_char(created_at, 'YYYY')"),
    ],
)
def test_time_bucket_postgresql_sql(period: Any, expected: str) -> None:
    expr = TimeBucket("created_at").expression(_CREATED, period)
    assert str(expr.compile(dialect=postgresql.dialect())) == expected


@pytest.mark.parametrize(
    ("period", "expected"),
    [
        ("day", "date_format(created_at, '%%Y-%%m-%%d')"),
        ("week", "date_format(date_sub(created_at, INTERVAL WEEKDAY(created_at) DAY), "),
        ("month", "date_format(created_at, '%%Y-%%m')"),
        ("quarter", "concat(year(created_at), '-Q', quarter(created_at))"),
        ("year", "date_format(created_at, '%%Y')"),
    ],
)
def test_time_bucket_mysql_sql(period: Any, expected: str) -> None:
    expr = TimeBucket("created_at").expression(_CREATED, period)
    assert str(expr.compile(dialect=mysql.dialect())).startswith(expected)


def test_time_bucket_sqlite_sql_has_no_bound_parameters() -> None:
    for period in ("day", "week", "month", "quarter", "year"):
        compiled = (
            TimeBucket("created_at").expression(_CREATED, period).compile(dialect=sqlite.dialect())
        )
        assert compiled.params == {}


def test_time_bucket_unsupported_dialect_raises() -> None:
    expr = TimeBucket("created_at").expression(_CREATED, "month")
    with pytest.raises(NotImplementedError, match="no SQL for dialect 'mssql'"):
        expr.compile(dialect=mssql.dialect())


@pytest.mark.parametrize(
    ("period", "expected"),
    [
        ("day", ["2025-01-05", "2025-01-20", "2025-02-10", "2025-11-30"]),
        ("week", ["2025-W01", "2025-W04", "2025-W07", "2025-W48"]),
        ("month", ["2025-01", "2025-02", "2025-11"]),
        ("quarter", ["2025-Q1", "2025-Q4"]),
        ("year", ["2025"]),
    ],
)
async def test_time_bucket_keys_on_sqlite(
    seeded: AsyncSession, period: Any, expected: list[str]
) -> None:
    class ByPeriod(ReportView):
        slug = "by-period"
        model = ReportOrder
        cols = [TimeBucket("created_at", period=period)]
        values = [Count()]

    result = await ByPeriod.run(seeded)
    assert [r["created_at"] for r in result.records] == expected


# ---------------------------------------------------------------------------
# ReportView
# ---------------------------------------------------------------------------


def test_group_name_label_repr() -> None:
    assert Group("supplier_id").name == "supplier_id"
    assert Group("supplier_id").label == "Supplier"
    assert Group("sku", label="SKU").label == "SKU"
    assert repr(Group("sku")) == "Group('sku')"


def test_report_label_and_permission_defaults() -> None:
    assert SkuByMonth.get_label() == "Orders revenue"
    assert SkuByMonth.get_permission() == "view_report_orders_revenue"

    class Custom(SkuByMonth):
        label = "Revenue"
        permission = "finance.view"

    assert Custom.get_label() == "Revenue"
    assert Custom.get_permission() == "finance.view"


def test_report_build_query_compiles_for_postgresql() -> None:
    query = SkuByMonth.build_query("postgresql", {"created_at": "month"})
    sql = str(query.compile(dialect=postgresql.dialect()))
    assert 'SUM("amount") AS sum_amount' in sql
    assert "COUNT(*) AS count_all" in sql
    assert "FROM test_reports_order" in sql
    assert (
        "GROUP BY test_reports_order.sku, to_char(test_reports_order.created_at, 'YYYY-MM')" in sql
    )


async def test_report_run_returns_flat_result_set(seeded: AsyncSession) -> None:
    result = await SkuByMonth.run(seeded)

    assert isinstance(result, ReportResult)
    assert result.columns == ["sku", "created_at", "sum_amount", "count_all"]
    assert result.periods == {"created_at": "month"}
    assert result.records == [
        {"sku": "A", "created_at": "2025-01", "sum_amount": 10, "count_all": 1},
        {"sku": "A", "created_at": "2025-02", "sum_amount": 20, "count_all": 1},
        {"sku": "A", "created_at": "2025-11", "sum_amount": 7, "count_all": 1},
        {"sku": "B", "created_at": "2025-01", "sum_amount": 5, "count_all": 1},
    ]
    totals = result.pivot()
    assert totals.cell(("B",), ("2025-02",)) is None
    counts = result.pivot("count_all")
    assert counts.cell(("B",), ("2025-02",)) == 0


async def test_report_run_accepts_a_session_factory(
    engine: AsyncEngine, seeded: AsyncSession
) -> None:
    factory = async_sessionmaker(engine, expire_on_commit=False)
    result = await SkuByMonth.run(factory)
    assert len(result.records) == 4


async def test_auto_bucket_uses_requested_range(seeded: AsyncSession) -> None:
    result = await SkuAuto.run(seeded, date_range=(date(2025, 1, 1), date(2025, 12, 31)))
    assert result.periods == {"created_at": "quarter"}
    assert result.pivot().col_keys == [("2025-Q1",), ("2025-Q4",)]


async def test_auto_bucket_falls_back_to_data_range(seeded: AsyncSession) -> None:
    # Data spans 2025-01-05 .. 2025-11-30 (330 days) → quarter.
    result = await SkuAuto.run(seeded)
    assert result.periods == {"created_at": "quarter"}


async def test_auto_bucket_on_empty_table_is_single_bucket(session: AsyncSession) -> None:
    result = await SkuAuto.run(session)
    assert result.periods == {"created_at": "year"}
    assert result.records == []


async def test_string_agg_runs_on_sqlite(seeded: AsyncSession) -> None:
    class Skus(ReportView):
        slug = "skus"
        model = ReportOrder
        rows = [TimeBucket("created_at", period="year")]
        values = [StringAggComma("sku"), Min("amount"), Max("amount")]

    (record,) = (await Skus.run(seeded)).records
    assert sorted(record["string_agg_sku"].split(", ")) == ["A", "A", "A", "B"]
    assert (record["min_amount"], record["max_amount"]) == (5, 20)


async def test_many2one_renders_display_inferred_from_foreign_key(seeded: AsyncSession) -> None:
    class BySku(ReportView):
        slug = "by-sku"
        model = ReportOrder
        rows = [Group("sku")]
        values = [Many2One("supplier_id"), Sum("amount")]

    result = await BySku.run(seeded)
    assert [(r["sku"], r["supplier_id"]) for r in result.records] == [
        ("A", "Acme"),
        ("B", "Globex"),
    ]


async def test_many2one_falls_back_to_pk(seeded: AsyncSession) -> None:
    seeded.add(
        ReportOrder(
            sku="C", amount=1, created_at=datetime(2025, 3, 1, tzinfo=timezone.utc), supplier_id=99
        )
    )
    await seeded.commit()

    class Explicit(ReportView):
        slug = "explicit"
        model = ReportOrder
        rows = [Group("sku")]
        values = [Many2One("supplier_id", target=ReportSupplier)]

    class NoForeignKey(ReportView):
        slug = "no-fk"
        model = ReportOrder
        rows = [Group("sku")]
        values = [Many2One("amount")]

    class UnmappedTarget(ReportView):
        slug = "unmapped"
        model = ReportOrder
        rows = [Group("sku")]
        values = [Many2One("plain_id")]

    explicit = await Explicit.run(seeded)
    assert [r["supplier_id"] for r in explicit.records] == ["Acme", "Globex", 99]
    no_fk = await NoForeignKey.run(seeded)
    assert [r["amount"] for r in no_fk.records] == [20, 5, 1]
    unmapped = await UnmappedTarget.run(seeded)
    assert [r["plain_id"] for r in unmapped.records] == [None, None, None]


# ---------------------------------------------------------------------------
# Period override (the report page's bucket switch) and the "Auto chose..." note
# ---------------------------------------------------------------------------


async def test_period_override_replaces_the_declared_bucket(seeded: AsyncSession) -> None:
    """
    Scenario: ?period= overrides the declared period
      Given SkuByMonth declares a month bucket
      When  it runs with period="quarter"
      Then  the buckets are quarters and no auto span is recorded
    """
    result = await SkuByMonth.run(seeded, period="quarter")

    assert result.periods == {"created_at": "quarter"}
    assert result.auto_spans == {}
    assert result.pivot().col_keys == [("2025-Q1",), ("2025-Q4",)]


async def test_period_override_auto_records_the_span_it_decided_on(
    seeded: AsyncSession,
) -> None:
    """
    Scenario: Auto explains itself
      Given SkuByMonth declares a month bucket
      When  it runs with period="auto" (data range, then an explicit range, then no rows)
      Then  auto_spans holds the day count that picked the bucket, or nothing without data
    """
    from_data = await SkuByMonth.run(seeded, period="auto")
    explicit = await SkuAuto.run(seeded, date_range=(date(2025, 1, 1), date(2025, 1, 31)))

    assert from_data.periods == {"created_at": "quarter"}
    assert from_data.auto_spans == {"created_at": 330}
    assert explicit.periods == {"created_at": "day"}
    assert explicit.auto_spans == {"created_at": 31}

    await seeded.execute(sa.delete(ReportOrder))
    await seeded.commit()
    no_rows = await SkuAuto.run(seeded)
    assert no_rows.periods == {"created_at": "year"}
    assert no_rows.auto_spans == {}


def test_time_bucket_resolve_period_with_override() -> None:
    bucket = TimeBucket("created_at", period="month")
    assert bucket.resolve_period(None, "week") == "week"
    assert bucket.resolve_period(None, "auto") == "year"
    assert bucket.resolve_period((date(2025, 1, 1), date(2025, 1, 10)), "auto") == "day"
    assert bucket.resolve_period((date(2025, 1, 1), date(2025, 1, 10))) == "month"


@pytest.mark.parametrize(
    ("days", "expected"),
    [(1, "1-day"), (92, "92-day"), (93, "3-month"), (365, "12-month"), (1100, "36-month")],
)
def test_describe_span(days: int, expected: str) -> None:
    assert describe_span(days) == expected


def test_period_for_days_and_range_days() -> None:
    assert [period_for_days(d) for d in (31, 32, 92, 93, 186, 187, 1100, 1101)] == [
        "day",
        "week",
        "week",
        "month",
        "month",
        "quarter",
        "quarter",
        "year",
    ]
    assert range_days(("2025-01-31", date(2025, 1, 1))) == 31


@pytest.mark.parametrize(
    ("key", "period", "expected"),
    [
        ("2025-Q3", "quarter", ("2025", "Q3")),
        ("2026-W03", "week", ("2026", "W03")),
        ("2026-01-15", "day", ("2026", "01-15")),
        ("2026-01", "month", ("2026", "2026-01")),
        ("2026", "year", (None, "2026")),
        ("2026", "month", (None, "2026")),
        (None, "month", (None, "")),
    ],
)
def test_time_bucket_split_key(key: Any, period: Any, expected: tuple[str | None, str]) -> None:
    assert TimeBucket.split_key(key, period) == expected


def test_report_description_and_summary() -> None:
    class Described(SkuByMonth):
        slug = "described"
        description = "Revenue per SKU and month."

    assert SkuByMonth.get_description() == ""
    assert Described.get_description() == "Revenue per SKU and month."
    assert SkuByMonth.get_summary() == "Report order · sum of amount, count of rows"


def test_filters_are_declared_but_unused() -> None:
    class Filtered(SkuByMonth):
        filters = ["sku"]

    assert Filtered.filters == ["sku"]
    assert Filtered.build_query("sqlite", {"created_at": "month"}).whereclause is None


@pytest.mark.parametrize(
    ("attrs", "message"),
    [
        ({"slug": ""}, "slug is required"),
        ({"model": None}, "model is required"),
        ({"values": []}, "at least one aggregate"),
        ({"rows": [Group("nope")]}, "unknown field\\(s\\) of ReportOrder: nope"),
        ({"values": [Sum("missing")]}, "unknown field\\(s\\) of ReportOrder: missing"),
        ({"values": [Sum("amount"), Sum("amount")]}, "duplicate column name\\(s\\): sum_amount"),
    ],
)
def test_validate_rejects_inconsistent_declarations(attrs: dict[str, Any], message: str) -> None:
    broken = type("Broken", (SkuByMonth,), attrs)
    with pytest.raises(ValueError, match=message):
        broken.validate()


def test_validate_accepts_count_star() -> None:
    SkuByMonth.validate()
