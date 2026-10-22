"""Admin with the ``reports`` plugin and chart-backed reports, plus a host page, for E2E.

Started by the ``report_charts_base_url`` fixture via uvicorn subprocess. No auth, so the
chart fragment is reachable directly. Reports:

* ``chart-revenue-trend``: sku x month  -> line chart, period switch
* ``chart-by-category``: category        -> bar chart
* ``chart-channel-mix``: category x channel -> stacked bar chart
* ``chart-balance``: category x channel with negative sums -> chart error state
* ``chart-empty``: a table without rows  -> no-data state
* ``chart-broken``: a table that does not exist -> query-failure state with Retry

``/host`` is a plain host page that lazy-loads a chart fragment, the way a host template
embeds one.
"""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import datetime, timezone

from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlmodel import Field, SQLModel

from hyperadmin.core.app import Admin
from hyperadmin.core.settings import HyperAdminSettings
from hyperadmin_reports import Group, ReportView, Sum, TimeBucket, register_report

engine = create_async_engine(
    "sqlite+aiosqlite:///:memory:",
    connect_args={"check_same_thread": False},
)


class ChartOrder(SQLModel, table=True):
    __tablename__ = "e2e_chart_order"

    id: int | None = Field(default=None, primary_key=True)
    sku: str
    category: str
    channel: str
    amount: int
    delta: int
    created_at: datetime


class ChartEmptyOrder(SQLModel, table=True):
    __tablename__ = "e2e_chart_empty_order"

    id: int | None = Field(default=None, primary_key=True)
    category: str
    amount: int


class ChartBrokenOrder(SQLModel, table=True):
    """Mapped but never created, so every query against it fails."""

    __tablename__ = "e2e_chart_broken_order"

    id: int | None = Field(default=None, primary_key=True)
    category: str
    amount: int


class RevenueTrend(ReportView):
    slug = "chart-revenue-trend"
    label = "Revenue trend"
    description = "Revenue per SKU and month."
    model = ChartOrder
    rows = [Group("sku")]
    cols = [TimeBucket("created_at", period="month")]
    values = [Sum("amount")]


class ByCategory(ReportView):
    slug = "chart-by-category"
    label = "Revenue by category"
    model = ChartOrder
    rows = [Group("category")]
    values = [Sum("amount")]


class ChannelMix(ReportView):
    slug = "chart-channel-mix"
    label = "Channel mix"
    model = ChartOrder
    rows = [Group("category")]
    cols = [Group("channel")]
    values = [Sum("amount")]


class Balance(ReportView):
    slug = "chart-balance"
    label = "Balance"
    model = ChartOrder
    rows = [Group("category")]
    cols = [Group("channel")]
    values = [Sum("delta")]


class Empty(ReportView):
    slug = "chart-empty"
    label = "Empty report"
    model = ChartEmptyOrder
    rows = [Group("category")]
    values = [Sum("amount")]


class Broken(ReportView):
    slug = "chart-broken"
    label = "Broken report"
    model = ChartBrokenOrder
    rows = [Group("category")]
    values = [Sum("amount")]


for _report in (RevenueTrend, ByCategory, ChannelMix, Balance, Empty, Broken):
    register_report(_report)

# (sku, category, channel, amount, delta, month): coffee/tea over Jan-Apr 2025
_ORDERS = (
    ("beans", "coffee", "web", 100, -30, 1),
    ("beans", "coffee", "store", 40, 10, 2),
    ("filter", "coffee", "web", 60, -5, 3),
    ("sencha", "tea", "web", 30, 5, 1),
    ("sencha", "tea", "store", 50, -20, 4),
    ("rooibos", "tea", "store", 20, 8, 4),
)


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
    async with engine.begin() as conn:
        await conn.run_sync(
            SQLModel.metadata.create_all,
            tables=[ChartOrder.__table__, ChartEmptyOrder.__table__],  # type: ignore[attr-defined]
        )
    async with AsyncSession(engine) as session:
        for sku, category, channel, amount, delta, month in _ORDERS:
            session.add(
                ChartOrder(
                    sku=sku,
                    category=category,
                    channel=channel,
                    amount=amount,
                    delta=delta,
                    created_at=datetime(2025, month, 5, tzinfo=timezone.utc),
                )
            )
        await session.commit()
    yield


app = FastAPI(lifespan=lifespan)

_HOST_PAGE = """<!doctype html>
<html lang="en"><head><meta charset="utf-8"><title>Host dashboard</title>
<link rel="stylesheet" href="/admin/static/css/hyperadmin.css">
<link rel="stylesheet" href="/admin/static/plugins/reports/charts.css">
<script src="/admin/static/js/vendor/htmx-1.9.10.min.js"></script></head>
<body class="ha-root"><main><h1>Host dashboard</h1>
<div id="slot" hx-get="/admin/reports/chart-revenue-trend/chart" hx-trigger="load" hx-swap="outerHTML">
<p>Loading chart…</p></div></main></body></html>"""


@app.get("/host", response_class=HTMLResponse)
async def host() -> str:
    return _HOST_PAGE


admin = Admin(
    app,
    engine=engine,
    settings=HyperAdminSettings(create_tables=False, secret_key="e2e-test-secret"),
)
admin.mount(path="/admin")
