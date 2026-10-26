"""Filter-library fixture app for E2E testing (H12, v0.5.6).

Started by the ``filter_library_base_url`` fixture in
``tests/e2e/test_filter_library.py`` via a uvicorn subprocess. Spec:
``docs/specs/filter-library.md`` (BDD scenarios); designs:
``docs/design/system/components/FilterSidebar`` and ``SavedViews``.

Auth is on: superusers ``alice`` (user key ``1``) and ``bob`` (user key ``2``),
both with password ``secret123``.

* ``Order`` — ``list_filter`` mixes a legacy string (``status``) with an
  explicit :class:`DateRangeFilter` and :class:`IsOwnerFilter`. ``created_by``
  holds the owner's user key. Rows 1 and 3 belong to alice, 2 and 4 to bob.
* ``Shipment`` — ``list_filter`` is a ``DateRangeFilter`` plus a
  ``CurrentPeriodDefault`` for the current month. Shipment ``S-NOW`` was
  created today, ``S-OLD`` in 2020.
"""

from __future__ import annotations

import os
import tempfile
from contextlib import asynccontextmanager
from datetime import UTC, date, datetime
from typing import TYPE_CHECKING

from fastapi import FastAPI
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlmodel import Field, SQLModel, select

from hyperadmin.adapters.sqlmodel import SQLModelAdapter
from hyperadmin.auth.backend import hash_password
from hyperadmin.auth.models import User
from hyperadmin.auth.permissions import ModelPermissionChecker, PermissionSyncService
from hyperadmin.auth.session import SessionAuthBackend
from hyperadmin.core.app import Admin
from hyperadmin.core.model import ModelAdmin
from hyperadmin.core.options import AdminOptions
from hyperadmin.core.registry import site
from hyperadmin.core.settings import HyperAdminSettings
from hyperadmin.filters import CurrentPeriodDefault, DateRangeFilter, IsOwnerFilter

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

_db_path = os.path.join(tempfile.mkdtemp(prefix="hyperadmin_e2e_filters_"), "app.db")
engine = create_async_engine(
    f"sqlite+aiosqlite:///{_db_path}",
    connect_args={"check_same_thread": False},
)


class Order(SQLModel, table=True):
    __tablename__ = "e2e_filter_order"

    id: int | None = Field(default=None, primary_key=True)
    number: str
    status: str = "new"
    created_on: date
    created_by: str


class Shipment(SQLModel, table=True):
    __tablename__ = "e2e_filter_shipment"

    id: int | None = Field(default=None, primary_key=True)
    code: str
    shipped_on: date


class OrderAdmin(ModelAdmin):
    adapter_class = SQLModelAdapter
    options = AdminOptions(
        list_display=["number", "status", "created_on"],
        list_filter=[
            "status",
            DateRangeFilter(field="created_on"),
            IsOwnerFilter(owner_fields="created_by"),
        ],
    )


class ShipmentAdmin(ModelAdmin):
    adapter_class = SQLModelAdapter
    options = AdminOptions(
        list_display=["code", "shipped_on"],
        list_filter=[
            DateRangeFilter(field="shipped_on"),
            CurrentPeriodDefault(field="shipped_on", period="month"),
        ],
    )


async def _seed() -> None:
    async with engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.create_all)
    async with AsyncSession(engine) as session:
        for name in ("alice", "bob"):
            if (await session.execute(select(User).where(User.username == name))).first() is None:
                session.add(
                    User(
                        username=name,
                        email=f"{name}@example.com",
                        password_hash=hash_password("secret123"),
                        is_superuser=True,
                    )
                )
        if (await session.execute(select(Order))).first() is None:
            session.add_all(
                [
                    Order(
                        number="ORD-1", status="new", created_on=date(2026, 1, 5), created_by="1"
                    ),
                    Order(
                        number="ORD-2",
                        status="shipped",
                        created_on=date(2026, 1, 15),
                        created_by="2",
                    ),
                    Order(
                        number="ORD-3", status="new", created_on=date(2025, 6, 1), created_by="1"
                    ),
                    Order(
                        number="ORD-4",
                        status="shipped",
                        created_on=date(2025, 7, 9),
                        created_by="2",
                    ),
                ]
            )
        if (await session.execute(select(Shipment))).first() is None:
            session.add_all(
                [
                    Shipment(code="S-NOW", shipped_on=datetime.now(UTC).date()),
                    Shipment(code="S-OLD", shipped_on=date(2020, 3, 3)),
                ]
            )
        await session.commit()


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
    await _seed()
    yield


app = FastAPI(lifespan=lifespan)

settings = HyperAdminSettings(
    create_tables=False,
    secret_key="e2e-filter-library-secret",
    auto_discover=False,
)

site._registry = {}
site.register(Order, OrderAdmin)
site.register(Shipment, ShipmentAdmin)

admin = Admin(
    app,
    engine=engine,
    settings=settings,
    auth_backend=SessionAuthBackend(engine=engine),
    permission_checker=ModelPermissionChecker(engine=engine),
    permission_registry=PermissionSyncService(engine=engine),
)
admin.mount(path="/admin")


@app.get("/")
def root() -> dict[str, str]:
    return {"status": "ok"}
