"""Unit tests for the report pages and CSV / XLSX export routes (st-v054-olap-03).

The first four tests map 1:1 to the scenarios of
``.meta/epics/epic-v054-olap-reporting/stories/featviews-report-routes-and-export.md``;
the rest cover the index, registry and plugin wiring edge cases. A real admin is
mounted (the ``reports`` plugin is discovered from its entry point), in bridge
mode where a permission matters.
"""

from __future__ import annotations

import io
from collections.abc import Iterator
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import anyio
import pytest
from fastapi import FastAPI, Header, HTTPException
from fastapi.testclient import TestClient
from openpyxl import load_workbook
from sqlalchemy import delete
from sqlalchemy.ext.asyncio import AsyncEngine, async_sessionmaker, create_async_engine
from sqlmodel import Field, SQLModel
from sqlmodel.ext.asyncio.session import AsyncSession

from hyperadmin import Admin
from hyperadmin.auth.bridge import ExternalAuth
from hyperadmin.core.plugins import PluginRegistry
from hyperadmin.core.registry import site
from hyperadmin.core.settings import HyperAdminSettings
from hyperadmin_reports import (
    Group,
    ReportView,
    Sum,
    TimeBucket,
    get_report,
    register_report,
    registered_reports,
    unregister_report,
)
from hyperadmin_reports.export import XLSX_MEDIA_TYPE
from hyperadmin_reports.plugin import ReportsPlugin
from hyperadmin_reports.routes import can_view


class RrOrder(SQLModel, table=True):
    __tablename__ = "test_report_routes_order"

    id: int | None = Field(default=None, primary_key=True)
    sku: str
    amount: int
    created_at: datetime


class OrdersRevenue(ReportView):
    slug = "orders-revenue"
    model = RrOrder
    rows = [Group("sku")]
    cols = [TimeBucket("created_at", period="month")]
    values = [Sum("amount")]


class OrdersBySku(ReportView):
    slug = "orders-by-sku"
    label = "Orders by SKU"
    model = RrOrder
    rows = [Group("sku")]
    values = [Sum("amount")]


GRID_HEADER = ["Sku", "2025-01", "2025-02"]
GRID_ROWS = [["A", 10, 20], ["B", 5, None]]

_ALLOWED = {"Authorization": "Bearer allowed"}
_DENIED = {"Authorization": "Bearer denied"}


def _get_user(authorization: str | None = Header(default=None)) -> Any:
    tokens = {"Bearer allowed": "allowed", "Bearer denied": "denied"}
    return (
        SimpleNamespace(id=tokens[authorization], name=tokens[authorization], is_staff=True)
        if authorization in tokens
        else None
    )


def _has_permission(user: Any, codename: str) -> bool:
    return user.name == "allowed" and codename == "view_report_orders_revenue"


@pytest.fixture(autouse=True)
def _registered() -> Iterator[None]:
    saved_models = dict(site._registry)
    site._registry = {}
    saved_reports = registered_reports()
    for report in saved_reports:
        unregister_report(report)
    for report in (OrdersRevenue, OrdersBySku):
        register_report(report)
    yield
    for report in registered_reports():
        unregister_report(report)
    for report in saved_reports:
        register_report(report)
    site._registry = saved_models


@pytest.fixture
def engine(tmp_path: Path) -> AsyncEngine:
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'reports.db'}")

    async def _seed() -> None:
        async with engine.begin() as conn:
            await conn.run_sync(SQLModel.metadata.create_all, tables=[RrOrder.__table__])  # type: ignore[attr-defined]
        async with AsyncSession(engine) as session:
            for sku, amount, month in (("A", 10, 1), ("A", 20, 2), ("B", 5, 1)):
                session.add(
                    RrOrder(
                        sku=sku,
                        amount=amount,
                        created_at=datetime(2025, month, 3, tzinfo=timezone.utc),
                    )
                )
            await session.commit()

    anyio.run(_seed)
    return engine


def _client(engine: AsyncEngine, *, bridge: bool = False, **admin_kwargs: Any) -> TestClient:
    app = FastAPI()
    if bridge:
        admin_kwargs["auth"] = ExternalAuth(get_user=_get_user, has_permission=_has_permission)
    Admin(
        app,
        engine=engine,
        settings=HyperAdminSettings(secret_key="reports-test-secret"),
        **admin_kwargs,
    ).mount("/admin")
    return TestClient(app, follow_redirects=False)


def test_html_grid_renders_pivot(engine: AsyncEngine) -> None:
    """
    Scenario: HTML grid renders pivot
      When  GET /admin/reports/orders-revenue/
      Then  response is 200 and body has a <table data-testid="report-grid">
      And   the grid holds the pivoted cells and links both exports
    """
    response = _client(engine).get("/admin/reports/orders-revenue/")

    assert response.status_code == 200
    assert 'data-testid="report-grid"' in response.text
    for heading in GRID_HEADER:
        assert f">{heading}</th>" in response.text
    assert response.text.count('data-testid="report-row"') == 2
    assert '/admin/reports/orders-revenue/export.csv"' in response.text
    assert '/admin/reports/orders-revenue/export.xlsx"' in response.text
    assert 'data-testid="report-export-csv"' in response.text
    assert 'data-testid="report-export-xlsx"' in response.text


def test_csv_stream_sets_attachment_disposition(engine: AsyncEngine) -> None:
    """
    Scenario: CSV stream sets attachment disposition
      When  GET /admin/reports/orders-revenue/export.csv
      Then  Content-Type is "text/csv"
      And   Content-Disposition is "attachment; filename=orders-revenue.csv"
      And   the body is the grid as BOM-free UTF-8 CSV
    """
    response = _client(engine).get("/admin/reports/orders-revenue/export.csv")

    assert response.status_code == 200
    assert response.headers["content-type"].split(";")[0] == "text/csv"
    assert response.headers["content-disposition"] == "attachment; filename=orders-revenue.csv"
    assert not response.content.startswith(b"\xef\xbb\xbf")
    assert response.text.splitlines() == ["Sku,2025-01,2025-02", "A,10,20", "B,5,"]


def test_xlsx_stream_is_openable_by_openpyxl(engine: AsyncEngine) -> None:
    """
    Scenario: XLSX stream is openable by openpyxl
      When  GET /admin/reports/orders-revenue/export.xlsx
      Then  Content-Type is the XLSX media type
      And   loading the body with openpyxl.load_workbook yields a data sheet matching the grid
      And   a "Filters used" cover sheet before it
    """
    response = _client(engine).get("/admin/reports/orders-revenue/export.xlsx")

    assert response.status_code == 200
    assert response.headers["content-type"] == XLSX_MEDIA_TYPE
    assert response.headers["content-disposition"] == "attachment; filename=orders-revenue.xlsx"
    workbook = load_workbook(io.BytesIO(response.content))
    assert workbook.sheetnames == ["Filters used", "Orders revenue"]
    rows = [list(row) for row in workbook["Orders revenue"].iter_rows(values_only=True)]
    assert rows == [GRID_HEADER, *GRID_ROWS]
    cover = list(workbook["Filters used"].iter_rows(values_only=True))
    assert cover[0] == ("Report", "Orders revenue")
    assert ("None", None) in cover


@pytest.mark.parametrize("path", ["", "export.csv", "export.xlsx"])
def test_permission_codename_gates_report_access(engine: AsyncEngine, path: str) -> None:
    """
    Scenario: permission codename gates report access
      Given the user lacks "view_report_orders_revenue"
      When  GET /admin/reports/orders-revenue/ (or either export)
      Then  response is 403
      And   a user holding it gets 200
    """
    client = _client(engine, bridge=True)
    url = f"/admin/reports/orders-revenue/{path}"

    assert client.get(url, headers=_DENIED).status_code == 403
    assert client.get(url, headers=_ALLOWED).status_code == 200


def test_unknown_report_is_404(engine: AsyncEngine) -> None:
    """
    Scenario: an unregistered slug is not found
      When  GET /admin/reports/nope/
      Then  response is 404
    """
    assert _client(engine).get("/admin/reports/nope/").status_code == 404


def test_index_lists_only_reports_the_user_may_view(engine: AsyncEngine) -> None:
    """
    Scenario: the reports index hides reports the user cannot open
      Given the user holds only "view_report_orders_revenue"
      When  GET /admin/reports/
      Then  the index links "Orders revenue" but not "Orders by SKU"
      And   the sidebar links the index
    """
    client = _client(engine, bridge=True)

    allowed = client.get("/admin/reports/", headers=_ALLOWED)
    denied = client.get("/admin/reports/", headers=_DENIED)

    assert allowed.status_code == 200
    assert '/admin/reports/orders-revenue/"' in allowed.text
    assert "Orders by SKU" not in allowed.text
    assert 'data-testid="sidebar-plugin-reports-reports-index"' in allowed.text
    assert 'data-testid="report-list-empty"' in denied.text


def test_report_without_column_dimension_uses_session_factory(engine: AsyncEngine) -> None:
    """
    Scenario: a host session factory serves report queries
      Given Admin(session_factory=...) and a report with no column dimension
      When  GET /admin/reports/orders-by-sku/export.csv
      Then  the CSV has one column per row dimension and aggregate
    """
    factory = async_sessionmaker(engine, expire_on_commit=False)

    response = _client(engine, session_factory=factory).get(
        "/admin/reports/orders-by-sku/export.csv"
    )

    assert response.text.splitlines() == ["Sku,Sum of Amount", "A,30", "B,5"]


def test_empty_report_renders_no_data(engine: AsyncEngine) -> None:
    """
    Scenario: an empty result set renders a "No data" cell
      Given the report's table has no rows
      When  GET /admin/reports/orders-revenue/
      Then  the grid shows "No data"
    """

    async def _clear() -> None:
        async with AsyncSession(engine) as session:
            await session.exec(delete(RrOrder))  # type: ignore[call-overload]
            await session.commit()

    anyio.run(_clear)

    response = _client(engine).get("/admin/reports/orders-revenue/")

    assert 'data-testid="report-empty"' in response.text


@pytest.mark.anyio
async def test_can_view_without_a_user_is_403() -> None:
    """
    Scenario: auth is configured but the request carries no user
      Given an admin with auth and a permission checker
      When  can_view runs for a request without request.state.user
      Then  it raises 403
    """
    admin = SimpleNamespace(auth=object(), auth_backend=None, permission_checker=object())
    request = SimpleNamespace(state=SimpleNamespace())

    with pytest.raises(HTTPException) as exc:
        await can_view(admin, request, OrdersRevenue)  # type: ignore[arg-type]

    assert exc.value.status_code == 403


def test_register_report_rejects_unsafe_and_taken_slugs() -> None:
    """
    Scenario: report slugs are URL-safe and unique
      Given "orders-revenue" is registered
      When  another class registers that slug, or a slug with a "/"
      Then  register_report raises ValueError
      And   re-registering the same class is a no-op
    """

    class Clash(OrdersRevenue):
        pass

    class Unsafe(OrdersRevenue):
        slug = "a/b"

    with pytest.raises(ValueError, match="already registered by OrdersRevenue"):
        register_report(Clash)
    with pytest.raises(ValueError, match="is not URL-safe"):
        register_report(Unsafe)
    assert register_report(OrdersRevenue) is OrdersRevenue
    assert get_report("orders-revenue") is OrdersRevenue

    unregister_report(Clash)  # not registered: no-op

    assert get_report("orders-revenue") is OrdersRevenue


def test_plugin_declares_one_permission_per_codename() -> None:
    """
    Scenario: the plugin declares each registered report's permission once
      Given two reports, one sharing a custom codename with another
      When  ReportsPlugin is registered
      Then  the page, the nav entry and one permission per distinct codename are contributed
    """

    class Shared(OrdersBySku):
        slug = "orders-shared"
        permission = "view_report_orders_by_sku"

    register_report(Shared)
    try:
        registry = PluginRegistry()
        assert registry.register(ReportsPlugin(), admin=SimpleNamespace(plugins=registry))
    finally:
        unregister_report(Shared)

    assert [r.slug for r in registered_reports()] == ["orders-revenue", "orders-by-sku"]
    assert [p.prefix for p in registry.pages] == ["/reports"]
    assert [e.url_name for e in registry.nav_entries] == ["reports-index"]
    assert [(p.codename, p.name) for p in registry.permissions] == [
        ("view_report_orders_revenue", "Can view report Orders revenue"),
        ("view_report_orders_by_sku", "Can view report Orders by SKU"),
    ]
