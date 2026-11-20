"""Auth-enabled admin with a dashboard of report widgets, for the dashboard E2E.

Started by the ``dashboard_base_url`` fixture (``tests/e2e/plugins/conftest.py``) via uvicorn
subprocess. Orders of 100, 200 and 300 (January to March 2025) and two payslips are seeded, and
the plugin's layout table is created, so users can save their widget order.

Reports: ``orders-revenue`` (sum and count per status), ``orders-by-month`` (sum per month) and
``payroll-total`` (sum per department).

Widgets, in registration (default) order:

=========================  ==========================================================
key                        what it is
=========================  ==========================================================
``stat-orders-revenue``    ``StatWidget`` over ``orders-revenue`` (600)
``chart-orders-by-month``  ``ChartWidget`` over ``orders-by-month``
``stat-payroll-total``     ``StatWidget`` over ``payroll-total``
``quick-actions``          "New order" (needs ``add_order``) and "All reports"
``broken``                 a custom widget whose ``render()`` raises
=========================  ==========================================================

Users (password ``secret123``):

* ``alice`` - superuser.
* ``bob`` - not a superuser, holds every permission alice uses here.
* ``viewer`` - holds the two order report permissions only (no payroll, no ``add_order``).
* ``nobody`` - holds no permission.
"""

from __future__ import annotations

import os
import tempfile
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any

from fastapi import FastAPI
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlmodel import Field, SQLModel, select

from hyperadmin.auth.backend import hash_password
from hyperadmin.auth.models import Permission, User, UserPermission
from hyperadmin.auth.permissions import ModelPermissionChecker, PermissionSyncService
from hyperadmin.auth.session import SessionAuthBackend
from hyperadmin.core.app import Admin
from hyperadmin.core.registry import site
from hyperadmin.core.settings import HyperAdminSettings
from hyperadmin_reports import (
    ChartWidget,
    Count,
    DashboardWidget,
    Group,
    QuickAction,
    QuickActionsWidget,
    ReportView,
    StatWidget,
    Sum,
    TimeBucket,
    WidgetBody,
    create_layout_table,
    register_report,
    register_widget,
)

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

    from starlette.requests import Request

_db_path = os.path.join(tempfile.mkdtemp(prefix="hyperadmin_e2e_dashboard_"), "app.db")
engine = create_async_engine(
    f"sqlite+aiosqlite:///{_db_path}",
    connect_args={"check_same_thread": False},
)

ORDER_REPORTS = "view_report_orders_revenue"


class Order(SQLModel, table=True):
    __tablename__ = "e2e_dashboard_order"

    id: int | None = Field(default=None, primary_key=True)
    status: str = "open"
    amount: int = 0
    created_at: datetime = Field(default_factory=lambda: datetime(2025, 1, 5, tzinfo=timezone.utc))


class Payslip(SQLModel, table=True):
    __tablename__ = "e2e_dashboard_payslip"

    id: int | None = Field(default=None, primary_key=True)
    department: str
    amount: int


class OrdersRevenue(ReportView):
    slug = "orders-revenue"
    label = "Orders revenue"
    description = "Revenue and order count per status."
    model = Order
    rows = [Group("status")]
    values = [Sum("amount", label="Revenue"), Count(label="Orders")]


class OrdersByMonth(ReportView):
    slug = "orders-by-month"
    label = "Orders by month"
    description = "Revenue per month."
    model = Order
    cols = [TimeBucket("created_at", period="month")]
    values = [Sum("amount", label="Revenue")]


class PayrollTotal(ReportView):
    slug = "payroll-total"
    label = "Payroll total"
    description = "Payroll per department."
    model = Payslip
    rows = [Group("department")]
    values = [Sum("amount", label="Payroll")]


class StaffActions(QuickActionsWidget):
    """Quick actions for people who work with orders (not for a user without any permission)."""

    def permission(self) -> str | None:
        return ORDER_REPORTS


class BrokenWidget(DashboardWidget):
    """A custom widget that always fails, to show the error state."""

    key = "broken"
    title = "Broken widget"

    def permission(self) -> str | None:
        return ORDER_REPORTS

    async def render(self, request: Request, admin: Any) -> WidgetBody:
        raise RuntimeError("the broken widget always fails")


site.register(Order)
for _report in (OrdersRevenue, OrdersByMonth, PayrollTotal):
    register_report(_report)
register_widget(StatWidget(OrdersRevenue))
register_widget(ChartWidget(OrdersByMonth))
register_widget(StatWidget(PayrollTotal))
register_widget(
    StaffActions(
        [
            QuickAction("New order", "order-create-form", permission="add_order", icon="plus"),
            QuickAction("All reports", "reports-index", icon="file-text"),
        ]
    )
)
register_widget(BrokenWidget())

#: Direct permission grants per user; alice is a superuser and needs none.
_GRANTS: dict[str, tuple[str, ...]] = {
    "alice": (),
    "bob": (
        ORDER_REPORTS,
        "view_report_orders_by_month",
        "view_report_payroll_total",
        "view_order",
        "add_order",
    ),
    "viewer": (ORDER_REPORTS, "view_report_orders_by_month"),
    "nobody": (),
}


async def _seed() -> None:
    async with AsyncSession(engine, expire_on_commit=False) as session:
        if (await session.execute(select(User).where(User.username == "alice"))).first():
            return
        users = {
            name: User(
                username=name,
                email=f"{name}@example.com",
                password_hash=hash_password("secret123"),
                is_superuser=name == "alice",
            )
            for name in _GRANTS
        }
        session.add_all(users.values())
        for month, amount in enumerate((100, 200, 300), start=1):
            session.add(
                Order(
                    status="paid" if month > 1 else "open",
                    amount=amount,
                    created_at=datetime(2025, month, 5, tzinfo=timezone.utc),
                )
            )
        session.add_all(
            [Payslip(department="Ops", amount=40), Payslip(department="Sales", amount=60)]
        )
        await session.commit()
        permissions = {
            p.codename: p.id for p in (await session.execute(select(Permission))).scalars().all()
        }
        for name, codenames in _GRANTS.items():
            for codename in codenames:
                session.add(
                    UserPermission(user_id=users[name].id, permission_id=permissions[codename])
                )
        await session.commit()


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
    async with engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.create_all)
    await create_layout_table(engine)
    await admin._sync_permissions()
    await _seed()
    yield


app = FastAPI(lifespan=lifespan)

admin = Admin(
    app,
    engine=engine,
    settings=HyperAdminSettings(
        create_tables=False, secret_key="e2e-dashboard-secret", auto_discover=False
    ),
    auth_backend=SessionAuthBackend(engine=engine),
    permission_checker=ModelPermissionChecker(engine=engine),
    permission_registry=PermissionSyncService(engine=engine),
)
admin.mount(path="/admin")
