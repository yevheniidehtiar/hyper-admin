"""Unit tests for the chart fragment route and the report-to-chart mapping (st-v054-charts-03).

The mapping tests build :class:`ReportResult` objects by hand (no database); the route tests
mount a real admin over a SQLite file, in bridge mode where permissions matter.
"""

from __future__ import annotations

from collections.abc import Iterator
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import anyio
import pytest
from fastapi import FastAPI, Header
from fastapi.testclient import TestClient
from sqlalchemy.exc import OperationalError
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine
from sqlmodel import Field, SQLModel
from sqlmodel.ext.asyncio.session import AsyncSession

from hyperadmin import Admin
from hyperadmin.auth.bridge import ExternalAuth
from hyperadmin.core.registry import site
from hyperadmin.core.settings import HyperAdminSettings
from hyperadmin_reports import (
    Count,
    Group,
    ReportResult,
    ReportView,
    StringAggComma,
    Sum,
    TimeBucket,
    register_report,
    registered_reports,
    unregister_report,
)
from hyperadmin_reports.chart_data import (
    MAX_BARS,
    MAX_POINTS,
    ChartUnavailableError,
    build_chart,
    chartable,
    placeholder,
)
from hyperadmin_reports.charts import BarChart, LineChart, StackedBarChart


class CrOrder(SQLModel, table=True):
    __tablename__ = "test_chart_route_order"

    id: int | None = Field(default=None, primary_key=True)
    sku: str
    region: str = "north"
    amount: int
    created_at: datetime


class Revenue(ReportView):
    slug = "cr-revenue"
    model = CrOrder
    rows = [Group("sku")]
    cols = [TimeBucket("created_at", period="month")]
    values = [Sum("amount")]


class BySku(ReportView):
    slug = "cr-by-sku"
    model = CrOrder
    rows = [Group("sku")]
    values = [Sum("amount")]


class ByRegion(ReportView):
    slug = "cr-by-region"
    model = CrOrder
    rows = [Group("sku")]
    cols = [Group("region")]
    values = [Sum("amount")]


class OnlyText(ReportView):
    slug = "cr-only-text"
    model = CrOrder
    rows = [Group("sku")]
    values = [StringAggComma("region")]


class Ungrouped(ReportView):
    slug = "cr-ungrouped"
    model = CrOrder
    values = [Count()]


REPORTS = (Revenue, BySku, ByRegion, OnlyText, Ungrouped)
_ALLOWED = {"Authorization": "Bearer allowed"}
_DENIED = {"Authorization": "Bearer denied"}


def _result(
    report: type[ReportView], records: list[dict[str, Any]], **periods: Any
) -> ReportResult:
    return ReportResult(
        records=records,
        rows=[d.name for d in report.rows],
        cols=[d.name for d in report.cols],
        values=[a.name for a in report.values],
        periods=periods,
        fills={a.name: a.empty for a in report.values},
    )


def _rec(**fields: Any) -> dict[str, Any]:
    return fields


# -- mapping ------------------------------------------------------------------------------
def test_time_bucket_columns_make_a_line_per_row_group() -> None:
    result = _result(
        Revenue,
        [
            _rec(sku="A", created_at="2025-01", sum_amount=10),
            _rec(sku="A", created_at="2025-02", sum_amount=20),
            _rec(sku="B", created_at="2025-01", sum_amount=5),
        ],
    )

    built = build_chart(Revenue, result)

    assert isinstance(built.chart, LineChart)
    assert built.chart.labels == ("2025-01", "2025-02")
    assert [(s.name, s.values) for s in built.chart.series] == [
        ("A", (10.0, 20.0)),
        ("B", (5.0, None)),
    ]
    assert built.chart.x_title == "Created At"
    assert built.caption == "Sum of Amount"
    assert "2025-02" in built.chart.desc


def test_single_group_makes_a_bar_chart() -> None:
    result = _result(BySku, [_rec(sku="A", sum_amount=30), _rec(sku="B", sum_amount=5)])

    built = build_chart(BySku, result)

    assert isinstance(built.chart, BarChart)
    assert built.chart.labels == ("A", "B")
    assert built.chart.series[0].values == (30.0, 5.0)


def test_row_and_column_groups_make_a_stacked_bar_per_row() -> None:
    result = _result(
        ByRegion,
        [
            _rec(sku="A", region="north", sum_amount=3),
            _rec(sku="A", region="south", sum_amount=4),
            _rec(sku="B", region=None, sum_amount=1),
        ],
    )

    built = build_chart(ByRegion, result)

    assert isinstance(built.chart, StackedBarChart)
    assert built.chart.labels == ("A", "B")
    assert [s.name for s in built.chart.series] == ["north", "south", "—"]


def test_time_bucket_rows_make_a_line_split_by_column_groups() -> None:
    class Monthly(ReportView):
        slug = "cr-monthly"
        model = CrOrder
        rows = [TimeBucket("created_at", period="month")]
        cols = [Group("region")]
        values = [Sum("amount")]

    result = _result(
        Monthly,
        [
            _rec(created_at="2025-01", region="north", sum_amount=3),
            _rec(created_at="2025-02", region="south", sum_amount=4),
        ],
    )

    built = build_chart(Monthly, result)

    assert isinstance(built.chart, LineChart)
    assert built.chart.labels == ("2025-01", "2025-02")
    assert [s.name for s in built.chart.series] == ["north", "south"]


def test_columns_only_report_plots_the_columns() -> None:
    class ByMonth(ReportView):
        slug = "cr-by-month"
        model = CrOrder
        cols = [TimeBucket("created_at", period="month")]
        values = [Sum("amount")]

    result = _result(
        ByMonth,
        [_rec(created_at="2025-01", sum_amount=3), _rec(created_at="2025-02", sum_amount=4)],
    )

    built = build_chart(ByMonth, result)

    assert isinstance(built.chart, LineChart)
    assert built.chart.series[0].values == (3.0, 4.0)


def test_extra_series_are_dropped_keeping_the_largest() -> None:
    records = [_rec(sku=f"S{i}", created_at="2025-01", sum_amount=i + 1) for i in range(8)]

    built = build_chart(Revenue, _result(Revenue, records))

    assert [s.name for s in built.chart.series] == ["S2", "S3", "S4", "S5", "S6", "S7"]
    assert built.caption == "Sum of Amount · 6 of 8 series"


def test_long_lines_keep_the_latest_points() -> None:
    records = [_rec(sku="A", created_at=f"2025-{m:02d}", sum_amount=m) for m in range(1, 13)] + [
        _rec(sku="A", created_at=f"2026-{m:02d}", sum_amount=m) for m in range(1, 13)
    ]
    records += [_rec(sku="A", created_at=f"2027-{m:02d}", sum_amount=m) for m in range(1, 13)]
    records += [_rec(sku="A", created_at="2028-01", sum_amount=1)]

    built = build_chart(Revenue, _result(Revenue, records))

    assert len(built.chart.labels) == MAX_POINTS
    assert built.chart.labels[-1] == "2028-01"
    assert built.caption == f"Sum of Amount · latest {MAX_POINTS} of 37"


def test_many_groups_keep_the_largest_bars_in_order() -> None:
    records = [_rec(sku=f"S{i:02d}", sum_amount=i) for i in range(15)]

    built = build_chart(BySku, _result(BySku, records))

    assert len(built.chart.labels) == MAX_BARS
    assert built.chart.labels[0] == "S03"
    assert built.chart.labels[-1] == "S14"
    assert built.caption == f"Sum of Amount · top {MAX_BARS} of 15"


def test_negative_stacks_are_unavailable() -> None:
    result = _result(
        ByRegion,
        [
            _rec(sku="A", region="north", sum_amount=-3),
            _rec(sku="A", region="south", sum_amount=4),
        ],
    )

    with pytest.raises(ChartUnavailableError, match="negative values"):
        build_chart(ByRegion, result)


def test_report_without_a_foldable_value_is_unavailable() -> None:
    assert not chartable(OnlyText)
    assert not chartable(Ungrouped)
    assert chartable(Revenue)
    with pytest.raises(ChartUnavailableError, match="no numeric value"):
        build_chart(OnlyText, _result(OnlyText, []))
    with pytest.raises(ChartUnavailableError, match="no numeric value"):
        build_chart(Ungrouped, _result(Ungrouped, []))


def test_empty_result_makes_an_empty_chart() -> None:
    built = build_chart(BySku, _result(BySku, []))

    assert built.chart.is_empty
    assert built.chart.desc.endswith("no data.")


def test_non_numeric_cells_are_gaps() -> None:
    result = _result(BySku, [_rec(sku="A", sum_amount="n/a"), _rec(sku="B", sum_amount=True)])

    assert build_chart(BySku, result).chart.is_empty


def test_placeholder_is_an_empty_chart_of_the_default_size() -> None:
    chart = placeholder(BySku)

    assert chart.is_empty
    assert chart.title == "Cr by sku"


# -- route --------------------------------------------------------------------------------
def _get_user(authorization: str | None = Header(default=None)) -> Any:
    names = {"Bearer allowed": "allowed", "Bearer denied": "denied"}
    return (
        SimpleNamespace(id=names[authorization], name=names[authorization], is_staff=True)
        if authorization in names
        else None
    )


def _has_permission(user: Any, codename: str) -> bool:
    return user.name == "allowed" and codename == "view_report_cr_revenue"


@pytest.fixture(autouse=True)
def _registered() -> Iterator[None]:
    saved_models = dict(site._registry)
    site._registry = {}
    saved_reports = registered_reports()
    for report in saved_reports:
        unregister_report(report)
    for report in REPORTS:
        register_report(report)
    yield
    for report in registered_reports():
        unregister_report(report)
    for report in saved_reports:
        register_report(report)
    site._registry = saved_models


@pytest.fixture
def engine(tmp_path: Path) -> AsyncEngine:
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'charts.db'}")

    async def _seed() -> None:
        async with engine.begin() as conn:
            await conn.run_sync(SQLModel.metadata.create_all, tables=[CrOrder.__table__])  # type: ignore[attr-defined]
        async with AsyncSession(engine) as session:
            for sku, amount, month in (("A", 10, 1), ("A", 20, 2), ("B", 5, 1)):
                session.add(
                    CrOrder(
                        sku=sku,
                        amount=amount,
                        created_at=datetime(2025, month, 3, tzinfo=timezone.utc),
                    )
                )
            await session.commit()

    anyio.run(_seed)
    return engine


def _client(engine: AsyncEngine, *, bridge: bool = False) -> TestClient:
    app = FastAPI()
    kwargs: dict[str, Any] = {}
    if bridge:
        kwargs["auth"] = ExternalAuth(get_user=_get_user, has_permission=_has_permission)
    Admin(
        app,
        engine=engine,
        settings=HyperAdminSettings(secret_key="chart-test-secret"),
        **kwargs,
    ).mount("/admin")
    return TestClient(app, follow_redirects=False)


def test_fragment_renders_the_frame_with_period_switch_and_table(engine: AsyncEngine) -> None:
    response = _client(engine).get("/admin/reports/cr-revenue/chart")

    assert response.status_code == 200
    html = response.text
    assert 'data-testid="chart-frame"' in html
    assert 'data-testid="chart-cr-revenue"' in html
    assert 'data-testid="chart-data-table-cr-revenue"' in html
    assert 'hx-get="/admin/reports/cr-revenue/chart?period=week"' in html
    assert 'aria-pressed="true" hx-get="/admin/reports/cr-revenue/chart?period=month"' in html


def test_fragment_forwards_the_query_string_and_period(engine: AsyncEngine) -> None:
    response = _client(engine).get("/admin/reports/cr-revenue/chart?period=year&region=north")

    assert response.status_code == 200
    assert '<th class="ha-table-th" scope="col">Created At</th>' in response.text
    assert ">2025<" in response.text
    # The switch keeps every other query key unchanged.
    assert "chart?period=month&amp;region=north" in response.text or (
        "chart?period=month&region=north" in response.text
    )


def test_embedded_fragment_has_no_period_switch(engine: AsyncEngine) -> None:
    response = _client(engine).get("/admin/reports/cr-revenue/chart?embed=1")

    assert response.status_code == 200
    assert "ha-seg" not in response.text
    assert 'data-testid="chart-frame"' in response.text


def test_fragment_without_a_time_bucket_has_no_switch(engine: AsyncEngine) -> None:
    response = _client(engine).get("/admin/reports/cr-by-sku/chart")

    assert response.status_code == 200
    assert "ha-seg" not in response.text
    assert 'data-testid="chart-cr-by-sku"' in response.text


def test_fragment_with_no_rows_renders_the_empty_state(engine: AsyncEngine) -> None:
    async def _clear() -> None:
        async with engine.begin() as conn:
            await conn.exec_driver_sql("DELETE FROM test_chart_route_order")

    anyio.run(_clear)

    response = _client(engine).get("/admin/reports/cr-by-sku/chart")

    assert response.status_code == 200
    assert 'data-testid="chart-empty"' in response.text


def test_unchartable_report_renders_the_error_state(engine: AsyncEngine) -> None:
    response = _client(engine).get("/admin/reports/cr-only-text/chart")

    assert response.status_code == 200
    assert 'role="alert"' in response.text
    assert "no numeric value" in response.text
    assert "Retry" not in response.text


def test_failing_query_renders_the_error_state_with_retry(
    engine: AsyncEngine, monkeypatch: pytest.MonkeyPatch
) -> None:
    async def boom(*_a: Any, **_k: Any) -> Any:
        raise OperationalError("select", {}, Exception("timeout"))

    monkeypatch.setattr(Revenue, "run", boom)

    response = _client(engine).get("/admin/reports/cr-revenue/chart?period=year")

    assert response.status_code == 200
    assert "The report query failed." in response.text
    assert 'hx-get="/admin/reports/cr-revenue/chart?period=year"' in response.text


def test_failing_query_retry_without_a_query_string(
    engine: AsyncEngine, monkeypatch: pytest.MonkeyPatch
) -> None:
    async def boom(*_a: Any, **_k: Any) -> Any:
        raise OperationalError("select", {}, Exception("timeout"))

    monkeypatch.setattr(Revenue, "run", boom)

    response = _client(engine).get("/admin/reports/cr-revenue/chart")

    assert 'hx-get="/admin/reports/cr-revenue/chart"' in response.text


def test_unknown_report_is_a_404(engine: AsyncEngine) -> None:
    assert _client(engine).get("/admin/reports/nope/chart").status_code == 404


def test_fragment_needs_the_report_permission(engine: AsyncEngine) -> None:
    client = _client(engine, bridge=True)

    assert client.get("/admin/reports/cr-revenue/chart", headers=_ALLOWED).status_code == 200
    assert client.get("/admin/reports/cr-revenue/chart", headers=_DENIED).status_code == 403


def test_detail_page_lazy_loads_the_chart_with_its_query(engine: AsyncEngine) -> None:
    response = _client(engine).get("/admin/reports/cr-revenue/?period=year&region=north")

    html = response.text
    assert 'data-testid="report-chart"' in html
    assert 'hx-trigger="load"' in html
    assert "/admin/reports/cr-revenue/chart?period=year&amp;region=north&amp;embed=1" in html
    assert 'aria-busy="true"' in html
    assert "plugins/reports/charts.css" in html


def test_detail_page_without_rows_has_no_chart_slot(engine: AsyncEngine) -> None:
    async def _clear() -> None:
        async with engine.begin() as conn:
            await conn.exec_driver_sql("DELETE FROM test_chart_route_order")

    anyio.run(_clear)

    html = _client(engine).get("/admin/reports/cr-revenue/").text

    assert 'data-testid="report-chart"' not in html
    assert 'data-testid="report-no-data"' in html


def test_detail_page_of_an_unchartable_report_has_no_chart_slot(engine: AsyncEngine) -> None:
    html = _client(engine).get("/admin/reports/cr-only-text/").text

    assert 'data-testid="report-chart"' not in html
