"""Unit tests for report filters (st-v054-olap-05).

The first test maps 1:1 to the scenario of
``.meta/epics/epic-v054-olap-reporting/stories/featreports-filter-integration.md``;
the rest cover the pipeline (cache target, validation, ``auto`` span, the owner
switch), the page's filter sidebar and its choices, and that the grid, the
chart and both exports are narrowed alike, behind the report's permission.
"""

from __future__ import annotations

import enum
import io
from collections.abc import AsyncIterator, Iterator
from datetime import date, datetime, timezone
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import anyio
import pytest
from fastapi import FastAPI, Header
from fastapi.testclient import TestClient
from openpyxl import load_workbook
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine
from sqlmodel import Field, SQLModel
from sqlmodel.ext.asyncio.session import AsyncSession

from hyperadmin import Admin
from hyperadmin.adapters.introspection import datetime_kind
from hyperadmin.auth.bridge import ExternalAuth
from hyperadmin.core.registry import site
from hyperadmin.core.settings import HyperAdminSettings
from hyperadmin.filters import (
    BooleanFilter,
    CurrentPeriodDefault,
    DateRangeFilter,
    FilterBinding,
    IsOwnerFilter,
    MultiChoiceFilter,
    MultiFKFilter,
)
from hyperadmin_reports import (
    FactTableSource,
    Group,
    ReportView,
    Sum,
    TimeBucket,
    register_report,
    registered_reports,
    unregister_report,
)
from hyperadmin_reports.filter_panel import _annotation, build_filter_panel, filter_choices
from hyperadmin_reports.filtering import (
    bind,
    compile_filters,
    describe_filters,
    filter_clauses,
    filter_errors,
    filter_fields,
    filter_query_keys,
    filtered_span,
)

# ---------------------------------------------------------------------------
# Models and reports
# ---------------------------------------------------------------------------


class RfStatus(enum.Enum):
    NEW = "new"
    DONE = "done"


class RfSupplier(SQLModel, table=True):
    __tablename__ = "test_report_filters_supplier"

    id: int | None = Field(default=None, primary_key=True)
    name: str


class RfOrder(SQLModel, table=True):
    __tablename__ = "test_report_filters_order"

    id: int | None = Field(default=None, primary_key=True)
    sku: str
    amount: int
    created_at: datetime
    paid: bool = True
    status: RfStatus = RfStatus.NEW
    supplier_id: int | None = Field(default=None, foreign_key="test_report_filters_supplier.id")
    owner: str = "other"
    reviewer: str = "other"


class RfOrderFact(SQLModel, table=True):
    """Fact table at the order grain, holding different numbers than the live table."""

    __tablename__ = "test_report_filters_order_fact"

    id: int | None = Field(default=None, primary_key=True)
    sku: str
    amount: int
    created_at: datetime


class RfFactWithoutDate(SQLModel, table=True):
    __tablename__ = "test_report_filters_fact_without_date"

    id: int | None = Field(default=None, primary_key=True)
    sku: str
    amount: int


class Revenue(ReportView):
    """Scenario report: a DateRangeFilter and a Sum aggregate."""

    slug = "rf-revenue"
    label = "Revenue"
    model = RfOrder
    rows = [Group("sku")]
    values = [Sum("amount")]
    filters = [DateRangeFilter(field="created_at")]


class RevenueByMonth(ReportView):
    slug = "rf-revenue-by-month"
    label = "Revenue by month"
    model = RfOrder
    rows = [Group("sku")]
    cols = [TimeBucket("created_at", period="month")]
    values = [Sum("amount")]
    filters = [
        DateRangeFilter(field="created_at"),
        "sku",
        "paid",
        "status",
        MultiFKFilter(field="supplier_id"),
        MultiChoiceFilter(field="sku"),
        IsOwnerFilter(owner_fields="owner"),
    ]


class AutoRevenue(ReportView):
    slug = "rf-auto-revenue"
    model = RfOrder
    rows = [Group("sku")]
    cols = [TimeBucket("created_at", period="auto")]
    values = [Sum("amount")]
    filters = [DateRangeFilter(field="created_at")]


class CachedRevenue(Revenue):
    slug = "rf-cached-revenue"
    cache = FactTableSource(model=RfOrderFact)


class Unfiltered(ReportView):
    slug = "rf-unfiltered"
    model = RfOrder
    rows = [Group("sku")]
    values = [Sum("amount")]


REPORTS = (Revenue, RevenueByMonth, AutoRevenue, CachedRevenue, Unfiltered)


def _at(*parts: int) -> datetime:
    return datetime(*parts, tzinfo=timezone.utc)  # type: ignore[misc]


#: sku, amount, created_at, paid, status, supplier id, owner, reviewer
ORDERS: tuple[tuple[str, int, datetime, bool, RfStatus, int, str, str], ...] = (
    ("A", 10, _at(2026, 1, 5, 9), True, RfStatus.NEW, 1, "allowed", "other"),
    ("A", 20, _at(2026, 2, 10, 12), False, RfStatus.DONE, 1, "other", "allowed"),
    ("B", 5, _at(2026, 1, 20, 8), True, RfStatus.NEW, 2, "other", "other"),
    ("B", 7, _at(2026, 3, 15, 23), True, RfStatus.DONE, 2, "allowed", "other"),
)
FACTS = (("A", 100, _at(2026, 1, 5)), ("A", 200, _at(2026, 2, 10)))

FROM_FEB = {"created_at__gte": "2026-02-01"}
_ALLOWED = {"Authorization": "Bearer allowed"}
_DENIED = {"Authorization": "Bearer denied"}


async def _seed(engine: AsyncEngine) -> None:
    async with engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.create_all)
    async with AsyncSession(engine) as session:
        session.add_all([RfSupplier(id=1, name="Acme"), RfSupplier(id=2, name="Globex")])
        session.add_all(
            RfOrder(
                sku=sku,
                amount=amount,
                created_at=at,
                paid=paid,
                status=status,
                supplier_id=supplier,
                owner=owner,
                reviewer=reviewer,
            )
            for sku, amount, at, paid, status, supplier, owner, reviewer in ORDERS
        )
        session.add_all(RfOrderFact(sku=s, amount=a, created_at=at) for s, a, at in FACTS)
        await session.commit()


@pytest.fixture
async def session() -> AsyncIterator[AsyncSession]:
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    await _seed(engine)
    async with AsyncSession(engine) as db:
        yield db
    await engine.dispose()


def _totals(result: Any) -> dict[str, int]:
    totals: dict[str, int] = {}
    for record in result.records:
        totals[record["sku"]] = totals.get(record["sku"], 0) + record["sum_amount"]
    return totals


def _sql(report: type[ReportView], query: Any, binding: FilterBinding | None = None) -> str:
    clauses = filter_clauses(report, compile_filters(report, query, binding))
    statement = report.build_query("sqlite", {"created_at": "month"}, clauses)
    return str(statement.compile(compile_kwargs={"literal_binds": True}))


# ---------------------------------------------------------------------------
# Story scenario
# ---------------------------------------------------------------------------


@pytest.mark.anyio
async def test_filters_are_applied_before_the_aggregate(session: AsyncSession) -> None:
    """
    Scenario: filters are applied before the aggregate
      Given a DateRangeFilter and a Sum aggregate
      When  .run() executes with {"created_at__gte": "2026-02-01"}
      Then  the SQL WHERE clause includes "created_at >= '2026-02-01'"
      And   the result excludes pre-February rows
    """
    # Given a DateRangeFilter and a Sum aggregate
    assert isinstance(Revenue.filters[0], DateRangeFilter)
    assert isinstance(Revenue.values[0], Sum)

    # When .run() executes with {"created_at__gte": "2026-02-01"}
    result = await Revenue.run(session, filters=FROM_FEB)

    # Then the SQL WHERE clause includes "created_at >= '2026-02-01'", ahead of the grouping
    sql = _sql(Revenue, FROM_FEB)
    assert "created_at >= '2026-02-01" in sql
    assert sql.index("WHERE") < sql.index("GROUP BY")
    # And the result excludes pre-February rows
    assert _totals(result) == {"A": 20, "B": 7}
    assert _totals(await Revenue.run(session)) == {"A": 30, "B": 12}


# ---------------------------------------------------------------------------
# Pipeline
# ---------------------------------------------------------------------------


@pytest.mark.anyio
async def test_filters_target_the_fact_table_when_cache_is_set(session: AsyncSession) -> None:
    result = await CachedRevenue.run(session, filters=FROM_FEB)

    assert _totals(result) == {"A": 200}
    sql = _sql(CachedRevenue, FROM_FEB)
    assert "test_report_filters_order_fact.created_at >= '2026-02-01" in sql


def test_a_filter_column_missing_from_the_fact_table_fails_registration() -> None:
    class Broken(Revenue):
        slug = "rf-broken-cache"
        cache = FactTableSource(model=RfFactWithoutDate)

    with pytest.raises(ValueError, match="FactTableSource missing column 'created_at'"):
        register_report(Broken)


@pytest.mark.parametrize(
    ("filters", "message"),
    [
        (["nope"], "unknown field"),
        ([IsOwnerFilter(owner_fields=("owner", "nope"))], "unknown field"),
        ([42], "filters: list_filter entries must be str or FilterDef"),
        ([BooleanFilter(field="period")], "reserved query key"),
    ],
)
def test_invalid_filter_declarations_fail_validation(filters: list[Any], message: str) -> None:
    class Broken(Unfiltered):
        slug = "rf-broken"

    Broken.filters = filters

    with pytest.raises(ValueError, match=message):
        Broken.validate()


@pytest.mark.anyio
async def test_filters_combine_with_where_clauses(session: AsyncSession) -> None:
    result = await Revenue.run(session, filters=FROM_FEB, where=[RfOrder.sku == "A"])  # type: ignore[arg-type]

    assert _totals(result) == {"A": 20}


@pytest.mark.anyio
async def test_invalid_input_is_dropped_not_sent_to_the_database(session: AsyncSession) -> None:
    query = {"created_at__gte": "not-a-date"}

    result = await Revenue.run(session, filters=query)

    assert _totals(result) == {"A": 30, "B": 12}
    assert filter_errors(Revenue, query) == {"created_at": "Enter a valid date (YYYY-MM-DD)."}
    assert filter_errors(Revenue, FROM_FEB) == {}


@pytest.mark.anyio
async def test_a_session_factory_runs_the_filtered_query(session: AsyncSession) -> None:
    factory = lambda: AsyncSession(session.bind)  # noqa: E731

    assert _totals(await Revenue.run(factory, filters=FROM_FEB)) == {"A": 20, "B": 7}


@pytest.mark.anyio
async def test_period_default_applies_only_through_the_filter_pipeline(
    session: AsyncSession,
) -> None:
    class ThisMonth(Unfiltered):
        slug = "rf-this-month"
        filters = [CurrentPeriodDefault(field="created_at")]

    binding = FilterBinding(today=date(2026, 3, 20))

    assert _totals(await ThisMonth.run(session, filters={}, binding=binding)) == {"B": 7}
    assert _totals(await ThisMonth.run(session, binding=binding)) == {"A": 30, "B": 12}
    assert describe_filters(ThisMonth, {}) == {"Created At": "this month"}


@pytest.mark.anyio
async def test_auto_bucket_spans_the_filtered_range(session: AsyncSession) -> None:
    year = {"created_at__gte": "2026-01-01", "created_at__lte": "2026-12-31"}

    closed = await AutoRevenue.run(session, filters=year)
    open_ended = await AutoRevenue.run(session, filters=FROM_FEB)

    # A closed range sizes the bucket by what was asked for: a year reads by quarter.
    assert closed.periods == {"created_at": "quarter"}
    assert closed.auto_spans == {"created_at": 365}
    # An open-ended one falls back to the filtered rows' own span (Feb 10 .. Mar 15).
    assert open_ended.periods == {"created_at": "week"}
    assert open_ended.auto_spans == {"created_at": 34}


def test_filtered_span_needs_both_bounds() -> None:
    year = {"created_at__gte": "2026-01-01", "created_at__lte": "2026-12-31"}

    span = filtered_span(compile_filters(Revenue, year), "created_at")

    # Whole days, first to last; aware or naive as the column is (it depends on the sqlmodel version).
    assert span is not None
    assert [bound.replace(tzinfo=None) for bound in span] == [  # type: ignore[call-arg]
        datetime(2026, 1, 1),
        datetime(2026, 12, 31, 23, 59, 59, 999999),
    ]
    assert filtered_span(compile_filters(Revenue, FROM_FEB), "created_at") is None
    assert filtered_span(compile_filters(Revenue, year), "sku") is None


@pytest.mark.anyio
async def test_owner_filter_uses_the_bindings_user_key(session: AsyncSession) -> None:
    mine = {"is_owner": "1"}

    as_user = await RevenueByMonth.run(
        session, filters=mine, binding=FilterBinding(user_key="allowed")
    )
    anonymous = await RevenueByMonth.run(session, filters=mine)

    assert _totals(as_user) == {"A": 10, "B": 7}
    # Without a user key the switch applies nothing: it can never widen a result.
    assert _totals(anonymous) == {"A": 30, "B": 12}


def test_owner_filter_declares_every_owner_column() -> None:
    both = IsOwnerFilter(owner_fields=("owner", "reviewer"))

    class Mine(Unfiltered):
        slug = "rf-mine"
        filters = [both]

    Mine.validate()
    assert filter_fields(both) == ("owner", "reviewer")
    assert filter_query_keys(Mine) == {"is_owner"}
    sql = _sql(Mine, {"is_owner": "1"}, FilterBinding(user_key="allowed"))
    assert "owner = 'allowed' OR" in sql


def test_bind_keeps_what_the_caller_supplied() -> None:
    kind = lambda _name: "aware"  # noqa: E731
    given = FilterBinding(model=RfOrderFact, datetime_kind=kind, user_key=7)

    assert bind(Revenue, given) == given
    default = bind(CachedRevenue)
    assert default.model is RfOrder
    assert default.datetime_kind is not None
    # The source table decides (aware or naive depends on the sqlmodel version's column type).
    assert default.datetime_kind("created_at") == datetime_kind(RfOrderFact, "created_at")
    assert default.datetime_kind("sku") is None


def test_describe_filters_lists_the_applied_ones() -> None:
    query = {"created_at__gte": "2026-02-01", "filter_sku": "A", "supplier_id__in": "1,2"}

    assert describe_filters(RevenueByMonth, query) == {
        "Created At": "from 2026-02-01",
        "Sku": "A",
        "Supplier Id": "2 selected",
    }
    assert describe_filters(RevenueByMonth, {}) == {}


# ---------------------------------------------------------------------------
# Sidebar choices
# ---------------------------------------------------------------------------


@pytest.mark.anyio
async def test_choices_come_from_the_report_source(session: AsyncSession) -> None:
    choices = await filter_choices(RevenueByMonth, session, {"supplier_id__in": "2, 99"})

    assert choices["sku"] == [{"value": "A", "label": "A"}, {"value": "B", "label": "B"}]
    assert choices["paid"] == [{"value": "true", "label": "Yes"}, {"value": "false", "label": "No"}]
    assert [choice["value"] for choice in choices["status"]] == ["new", "done"]
    # A foreign key shows the related rows' display names; a stale applied value stays listed.
    assert [choice["value"] for choice in choices["supplier_id"]] == ["1", "2", "99"]
    assert "Acme" in choices["supplier_id"][0]["label"]
    assert choices["supplier_id"][2]["label"] == "99"
    assert set(choices) == {"sku", "paid", "status", "supplier_id"}


@pytest.mark.anyio
async def test_choices_of_an_empty_source_are_the_applied_values() -> None:
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.create_all)

    async with AsyncSession(engine) as empty:
        choices = await filter_choices(RevenueByMonth, empty, {"supplier_id__in": "7"})
    await engine.dispose()

    assert choices["supplier_id"] == [{"value": "7", "label": "7"}]
    assert choices["sku"] == []


def test_annotation_of_a_class_without_a_schema_is_unknown() -> None:
    class Plain:
        pass

    assert _annotation(Plain, "x") is None
    assert _annotation(RfOrder, "supplier_id") is int
    assert _annotation(RfOrder, "paid") is bool


@pytest.mark.anyio
async def test_panel_is_none_without_filters(session: AsyncSession) -> None:
    assert await build_filter_panel(Unfiltered, session, {}) is None


@pytest.mark.anyio
async def test_panel_renders_groups_chips_and_kept_pairs(session: AsyncSession) -> None:
    query = {"created_at__gte": "2026-02-01", "period": "quarter", "embed": "1"}

    panel = await build_filter_panel(RevenueByMonth, session, query)

    assert panel is not None
    assert [group["slug"] for group in panel["groups"]] == [
        "created_at",
        "sku",
        "paid",
        "status",
        "supplier_id",
        "sku",
        "is_owner",
    ]
    assert 'name="created_at__gte" value="2026-02-01"' in panel["groups"][0]["html"]
    assert panel["applied"] == [
        {"label": "Created At", "value": "from 2026-02-01", "clear_href": "?period=quarter&embed=1"}
    ]
    assert panel["kept"] == [("period", "quarter")]
    assert panel["reset_query"] == "?period=quarter"
    bare = await build_filter_panel(RevenueByMonth, session, {})
    assert bare is not None
    assert (bare["applied"], bare["kept"], bare["reset_query"]) == ([], [], "")


# ---------------------------------------------------------------------------
# Routes: the page, the chart and both exports are narrowed alike
# ---------------------------------------------------------------------------


def _get_user(authorization: str | None = Header(default=None)) -> Any:
    tokens = {"Bearer allowed": "allowed", "Bearer denied": "denied"}
    return (
        SimpleNamespace(id=tokens[authorization], name=tokens[authorization], is_staff=True)
        if authorization in tokens
        else None
    )


def _has_permission(user: Any, codename: str) -> bool:
    return user.name == "allowed" and codename.startswith("view_report_rf_")


@pytest.fixture
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
def client(tmp_path: Path, _registered: None) -> TestClient:
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'report_filters.db'}")
    anyio.run(_seed, engine)
    app = FastAPI()
    Admin(
        app,
        engine=engine,
        settings=HyperAdminSettings(secret_key="report-filters-test-secret"),
        auth=ExternalAuth(get_user=_get_user, has_permission=_has_permission),
    ).mount("/admin")
    return TestClient(app, follow_redirects=False, headers=_ALLOWED)


def _csv(client: TestClient, slug: str, query: str = "") -> list[str]:
    response = client.get(f"/admin/reports/{slug}/export.csv{query}")
    assert response.status_code == 200
    return response.text.splitlines()


def test_page_shows_the_sidebar_and_the_filtered_grid(client: TestClient) -> None:
    response = client.get("/admin/reports/rf-revenue-by-month/?created_at__gte=2026-02-01")

    assert response.status_code == 200
    body = response.text
    assert 'data-testid="report-filters"' in body
    assert 'data-testid="report-filter-apply"' in body
    assert 'data-testid="report-applied-filters"' in body
    assert "Created At: from 2026-02-01" in body
    assert 'data-testid="report-filter-count">1<' in body
    # January is filtered out before the aggregate, so its bucket is gone.
    assert "2026-01" not in body.split('data-testid="report-grid"', 1)[1]
    # The chart fragment and both exports are requested with the same filters.
    assert "chart?created_at__gte=2026-02-01&amp;embed=1" in body
    assert "export.csv?created_at__gte=2026-02-01" in body
    assert "export.xlsx?created_at__gte=2026-02-01" in body


def test_page_without_filters_has_no_sidebar(client: TestClient) -> None:
    body = client.get("/admin/reports/rf-unfiltered/").text

    assert 'data-testid="report-grid"' in body
    assert 'data-testid="report-filters"' not in body


def test_htmx_fragment_carries_the_sidebar_and_keeps_the_period(client: TestClient) -> None:
    response = client.get(
        "/admin/reports/rf-revenue-by-month/?period=quarter&filter_sku=A",
        headers={"HX-Request": "true"},
    )

    body = response.text
    assert body.lstrip().startswith('<div id="report-page"')
    assert '<input type="hidden" name="period" value="quarter">' in body
    assert (
        '/admin/reports/rf-revenue-by-month/?period=quarter" data-testid="report-filters-reset"'
        in body
    )
    assert "Sku: A" in body


def test_invalid_filter_input_renders_the_inline_error(client: TestClient) -> None:
    body = client.get("/admin/reports/rf-revenue/?created_at__gte=nope").text

    assert 'data-testid="filter-created_at-error"' in body
    assert 'data-testid="report-filter-ignored"' in body
    assert "Created At filter ignored." in body
    assert "Enter a valid date (YYYY-MM-DD)." in body
    assert 'data-testid="report-applied-filters"' not in body


def test_bucket_switch_keeps_repeated_filter_values(client: TestClient) -> None:
    body = client.get("/admin/reports/rf-revenue-by-month/?sku__in=A&sku__in=B&period=month").text

    assert "?sku__in=A&amp;sku__in=B&amp;period=quarter" in body
    assert "chart?sku__in=A&amp;sku__in=B&amp;period=month&amp;embed=1" in body


def test_csv_export_is_filtered_like_the_page(client: TestClient) -> None:
    assert _csv(client, "rf-revenue") == ["Sku,Sum of Amount", "A,30", "B,12", "Total,42"]
    assert _csv(client, "rf-revenue", "?created_at__gte=2026-02-01") == [
        "Sku,Sum of Amount",
        "A,20",
        "B,7",
        "Total,27",
    ]


def test_xlsx_export_is_filtered_and_lists_the_filters_used(client: TestClient) -> None:
    response = client.get(
        "/admin/reports/rf-revenue-by-month/export.xlsx"
        "?created_at__gte=2026-02-01&filter_paid=true&period=quarter"
    )

    assert response.status_code == 200
    workbook = load_workbook(io.BytesIO(response.content))
    rows = [list(row) for row in workbook["Revenue by month"].iter_rows(values_only=True)]
    assert rows[1:] == [["B", 7, 7], ["Total", 7, 7]]
    cover = list(workbook["Filters used"].iter_rows(values_only=True))
    assert ("Created At", "from 2026-02-01") in cover
    assert ("Paid", "true") in cover
    assert ("period", "quarter") in cover
    assert ("None", None) not in cover


def test_xlsx_cover_sheet_says_none_when_unfiltered(client: TestClient) -> None:
    response = client.get("/admin/reports/rf-revenue/export.xlsx")

    workbook = load_workbook(io.BytesIO(response.content))
    cover = list(workbook["Filters used"].iter_rows(values_only=True))
    assert cover[-1][0] == "None"


def test_chart_fragment_is_filtered_like_the_page(client: TestClient) -> None:
    everything = client.get("/admin/reports/rf-revenue/chart").text
    from_march = client.get("/admin/reports/rf-revenue/chart?created_at__gte=2026-03-01").text

    assert "the largest value, 30, is at A" in everything
    assert "the largest value, 7, is at B" in from_march


def test_owner_switch_reads_the_requests_user_key(client: TestClient) -> None:
    assert _csv(client, "rf-revenue-by-month", "?is_owner=1")[1:] == [
        "A,10,,10",
        "B,,7,7",
        "Total,10,7,17",
    ]


@pytest.mark.parametrize("path", ["", "chart", "export.csv", "export.xlsx"])
def test_filters_never_bypass_the_report_permission(client: TestClient, path: str) -> None:
    response = client.get(
        f"/admin/reports/rf-revenue/{path}?created_at__gte=2026-02-01", headers=_DENIED
    )

    assert response.status_code == 403
    assert "view_report_rf_revenue" in response.text
    assert "Total" not in response.text
