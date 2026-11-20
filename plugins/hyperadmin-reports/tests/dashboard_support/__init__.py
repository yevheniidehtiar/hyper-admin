"""Shared fixtures of the dashboard tests: a model, reports, users and a mounted admin.

Not a test module. The dashboard tests import it by name (pytest puts this
directory on ``sys.path``), so the model and the reports are declared once.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable, Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import anyio
from fastapi import APIRouter, FastAPI
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine
from sqlmodel import Field, SQLModel
from sqlmodel.ext.asyncio.session import AsyncSession
from starlette.requests import Request

from hyperadmin import Admin
from hyperadmin.core.csrf import CsrfTokenSigner
from hyperadmin.core.registry import site
from hyperadmin.core.settings import HyperAdminSettings
from hyperadmin_reports import (
    Count,
    DashboardWidget,
    Group,
    ReportView,
    StringAggComma,
    Sum,
    TimeBucket,
    WidgetBody,
    create_layout_table,
    register_report,
    register_widget,
    registered_reports,
    registered_widgets,
    unregister_report,
    unregister_widget,
)

SECRET = "x" * 40
HX = {"HX-Request": "true"}


class DashOrder(SQLModel, table=True):
    __tablename__ = "test_dashboard_order"

    id: int | None = Field(default=None, primary_key=True)
    status: str
    sku: str
    amount: int
    created_at: datetime


class OrderRevenueReport(ReportView):
    slug = "orders-revenue"
    model = DashOrder
    rows = [Group("status")]
    values = [Sum("amount"), Count()]


class OrdersByMonthReport(ReportView):
    slug = "orders-by-month"
    model = DashOrder
    cols = [TimeBucket("created_at", period="month")]
    values = [Sum("amount")]


class PayrollTotalReport(ReportView):
    slug = "payroll-total"
    model = DashOrder
    rows = [Group("status")]
    values = [Sum("amount")]


class SkuListReport(ReportView):
    slug = "sku-list"
    model = DashOrder
    rows = [Group("status")]
    values = [StringAggComma("sku")]


class GrandTotalReport(ReportView):
    slug = "grand-total"
    model = DashOrder
    values = [Sum("amount")]


REPORTS = (OrderRevenueReport, OrdersByMonthReport, PayrollTotalReport, SkuListReport)


class TextWidget(DashboardWidget):
    """A custom widget with a fixed body, an optional codename and an optional failure."""

    def __init__(
        self, key: str, *, permission: str | None = None, fail: bool = False, lazy: bool = True
    ) -> None:
        self.key = key
        self.title = key.upper()
        self.codename = permission
        self.fail = fail
        self.lazy = lazy  # type: ignore[misc]

    def permission(self) -> str | None:
        return self.codename

    async def render(self, request: Request, admin: Any) -> WidgetBody:
        if self.fail:
            raise RuntimeError(f"{self.key} exploded")
        return WidgetBody("dashboard/_actions.html", {"widget": self, "actions": []})


@dataclass
class User:
    id: int
    username: str
    is_superuser: bool = False


class Backend:
    """Signs in whoever the ``x-user`` header names (alice by default)."""

    users = {
        "alice": User(1, "alice"),
        "bob": User(2, "bob"),
        "viewer": User(3, "viewer"),
        "nobody": User(4, "nobody"),
    }

    async def get_current_user(self, request: Any) -> User:
        return self.users[request.headers.get("x-user", "alice")]

    async def authenticate(self, username: str, password: str) -> None:
        return None


ALL_REPORT_CODENAMES = {
    "view_report_orders_revenue",
    "view_report_orders_by_month",
    "view_report_payroll_total",
    "add_dashorder",
    "view_dashorder",
    "view_a",
    "view_b",
    "view_c",
}


class Checker:
    granted: dict[str, set[str]] = {
        "alice": ALL_REPORT_CODENAMES,
        "bob": ALL_REPORT_CODENAMES,
        "viewer": {"view_report_orders_revenue", "view_a", "view_b", "view_c"},
        "nobody": set(),
    }

    async def has_permission(self, user: Any, codename: str) -> bool:
        return codename in self.granted.get(user.username, set())

    async def get_user_permissions(self, user: Any) -> set[str]:
        return set(self.granted.get(user.username, set()))


@contextmanager
def registry(*widgets: DashboardWidget, reports: tuple[type[ReportView], ...] = REPORTS) -> Any:
    """Swap in ``reports`` and ``widgets`` (and an empty model registry) for one test."""
    saved_models = dict(site._registry)
    site._registry = {}
    saved_reports = registered_reports()
    saved_widgets = registered_widgets()
    for widget in saved_widgets:
        unregister_widget(widget)
    for report in saved_reports:
        unregister_report(report)
    for report in reports:
        register_report(report)
    for widget in widgets:
        register_widget(widget)
    try:
        yield
    finally:
        for widget in registered_widgets():
            unregister_widget(widget)
        for report in registered_reports():
            unregister_report(report)
        for report in saved_reports:
            register_report(report)
        for widget in saved_widgets:
            register_widget(widget)
        site._registry = saved_models


def clean_registry() -> Iterator[None]:
    """Fixture body: the test reports and no widgets."""
    with registry():
        yield


def make_engine(
    tmp_path: Path, *, amounts: tuple[int, ...] = (100, 200, 300), layouts: bool = True
) -> AsyncEngine:
    """A SQLite database with the order table, ``amounts`` as orders and the layout table."""
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'dashboard.db'}")

    async def _seed() -> None:
        async with engine.begin() as conn:
            await conn.run_sync(SQLModel.metadata.create_all, tables=[DashOrder.__table__])  # type: ignore[attr-defined]
        if layouts:
            await create_layout_table(engine)
        async with AsyncSession(engine) as session:
            for index, amount in enumerate(amounts):
                session.add(
                    DashOrder(
                        status="paid" if index % 2 else "open",
                        sku=f"S{index}",
                        amount=amount,
                        created_at=datetime(2025, index + 1, 3, tzinfo=timezone.utc),
                    )
                )
            await session.commit()

    anyio.run(_seed)
    return engine


class ProbePlugin:
    """A page that runs a test's coroutine inside a real admin request."""

    name = "probe"

    def __init__(self) -> None:
        self.call: Callable[[Request], Awaitable[Any]] | None = None
        self.result: Any = None

    def on_register(self, admin: Any) -> None:
        router = APIRouter()

        @router.get("/", name="probe-run")
        async def run(request: Request) -> dict[str, bool]:
            assert self.call is not None
            self.result = await self.call(request)
            return {"ok": True}

        # Stands in for the dashboard's widget route when no widget was registered
        # before the admin was built (the real route is found first otherwise).
        @router.get("/widgets/{key}", name="dashboard-widget")
        async def widget(key: str) -> dict[str, str]:
            return {"key": key}

        admin.plugins.add_page(self, router)


@dataclass
class Mounted:
    admin: Admin
    client: TestClient
    probe: ProbePlugin

    def run(self, call: Callable[[Request], Awaitable[Any]], user: str = "alice") -> Any:
        """Await ``call(request)`` inside an admin request of ``user`` and return its result."""
        self.probe.call = call
        response = self.client.get("/admin/probe/", headers={"x-user": user})
        assert response.status_code == 200, response.text
        return self.probe.result


def mount(engine: AsyncEngine, *, auth: bool = True, **admin_kwargs: Any) -> Mounted:
    """Mount an admin (reports plugin from its entry point) and return it with a client."""
    app = FastAPI()
    if auth:
        admin_kwargs |= {"auth_backend": Backend(), "permission_checker": Checker()}
    admin = Admin(
        app,
        engine=engine,
        settings=HyperAdminSettings(secret_key=SECRET, create_tables=False),
        **admin_kwargs,
    )
    probe = ProbePlugin()
    assert admin.plugins.register(probe, admin=admin)
    admin.mount("/admin")
    client = TestClient(app, follow_redirects=False)
    if auth:
        token = CsrfTokenSigner(SECRET).issue()
        client.cookies.set("hyperadmin_csrf", token)
        client.headers["X-CSRF-Token"] = token
    return Mounted(admin, client, probe)
