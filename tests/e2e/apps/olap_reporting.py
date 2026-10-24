"""Auth-enabled admin with generic Order/Product/Supplier reports, for the OLAP report E2E.

Started by the ``olap_reporting_base_url`` fixture via uvicorn subprocess. Seeds superuser
``alice`` and permissionless ``bob`` (both ``secret123``) and these 2025 orders:

========  ========  ======  =======
product   supplier  amount  month
========  ========  ======  =======
Widget    Acme      100     Jan
Widget    Acme      50      Feb
Gadget    Globex    70      Jan
Gadget    Globex    30      Apr
Gizmo     Acme      200     Jul
Gizmo     Acme      10      Dec
========  ========  ======  =======

Reports: ``olap-by-product`` (sum per product), ``olap-by-month`` (product x month) and
``olap-auto`` (product x auto-bucketed ``created_at``; a full year picks quarter).
"""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import datetime, timezone

from fastapi import FastAPI
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlmodel import Field, SQLModel, select

from hyperadmin.auth.backend import hash_password
from hyperadmin.auth.models import User
from hyperadmin.auth.permissions import ModelPermissionChecker, PermissionSyncService
from hyperadmin.auth.session import SessionAuthBackend
from hyperadmin.core.app import Admin
from hyperadmin.core.settings import HyperAdminSettings
from hyperadmin_reports import Group, ReportView, Sum, TimeBucket, register_report

engine = create_async_engine(
    "sqlite+aiosqlite:///:memory:",
    connect_args={"check_same_thread": False},
)


class OlapOrder(SQLModel, table=True):
    __tablename__ = "e2e_olap_order"

    id: int | None = Field(default=None, primary_key=True)
    product: str
    supplier: str
    amount: int
    created_at: datetime


class ByProduct(ReportView):
    slug = "olap-by-product"
    label = "Revenue by product"
    description = "Total revenue per product."
    model = OlapOrder
    rows = [Group("product")]
    values = [Sum("amount")]


class ByMonth(ReportView):
    slug = "olap-by-month"
    label = "Revenue by month"
    description = "Revenue per product and month."
    model = OlapOrder
    rows = [Group("product")]
    cols = [TimeBucket("created_at", period="month")]
    values = [Sum("amount")]


class AutoBucket(ReportView):
    slug = "olap-auto"
    label = "Revenue over time"
    description = "Revenue per product, bucketed by the data's span."
    model = OlapOrder
    rows = [Group("product")]
    cols = [TimeBucket("created_at", period="auto")]
    values = [Sum("amount")]


for _report in (ByProduct, ByMonth, AutoBucket):
    register_report(_report)

#: Seed rows as product, supplier, amount, month.
_ORDERS = (
    ("Widget", "Acme", 100, 1),
    ("Widget", "Acme", 50, 2),
    ("Gadget", "Globex", 70, 1),
    ("Gadget", "Globex", 30, 4),
    ("Gizmo", "Acme", 200, 7),
    ("Gizmo", "Acme", 10, 12),
)


async def _seed() -> None:
    async with AsyncSession(engine) as session:
        for username, superuser in (("alice", True), ("bob", False)):
            exists = await session.execute(select(User).where(User.username == username))
            if not exists.scalar_one_or_none():
                session.add(
                    User(
                        username=username,
                        email=f"{username}@example.com",
                        password_hash=hash_password("secret123"),
                        is_superuser=superuser,
                    )
                )
        for product, supplier, amount, month in _ORDERS:
            session.add(
                OlapOrder(
                    product=product,
                    supplier=supplier,
                    amount=amount,
                    created_at=datetime(2025, month, 5, tzinfo=timezone.utc),
                )
            )
        await session.commit()


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
    async with engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.create_all)
    await _seed()
    yield


app = FastAPI(lifespan=lifespan)

admin = Admin(
    app,
    engine=engine,
    settings=HyperAdminSettings(create_tables=False, secret_key="e2e-test-secret"),
    auth_backend=SessionAuthBackend(engine=engine),
    permission_checker=ModelPermissionChecker(engine=engine),
    permission_registry=PermissionSyncService(engine=engine),
)
admin.mount(path="/admin")
