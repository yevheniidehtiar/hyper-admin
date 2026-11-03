"""List-rows fixture app for E2E testing (v0.5.9, st-v059-list-02 / list-03).

Started by the ``list_rows_base_url`` fixture in ``tests/e2e/test_list_rows.py``.
Spec: ``docs/specs/navigation-and-list-ux.md`` ("Rows (list-02)", "Delete (list-03)").

Registers ``Order`` (``number``, ``customer``, ``status``; ``__str__`` is the number) with
``list_editable = ["status"]`` and a bulk ``archive`` action, so a row has a
checkbox, an inline-edit cell and a title link. A ``Shipment`` references order
#44 through a RESTRICT foreign key (SQLite ``foreign_keys=ON``), so deleting
that order answers 409.

Users (password ``secret123``):

* ``alice`` — every Order permission (view, add, change, delete, the action).
* ``bob`` — ``view_order`` only.

Orders: #42 ``ORD-1042``, #43 ``ORD-1043``, #44 ``ORD-1044`` (shipped, protected).
"""

from __future__ import annotations

import os
import tempfile
from contextlib import asynccontextmanager
from typing import TYPE_CHECKING, Any

from fastapi import FastAPI
from sqlalchemy import event
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlmodel import Field, SQLModel, select

from hyperadmin.adapters.sqlmodel import SQLModelAdapter
from hyperadmin.auth.backend import hash_password
from hyperadmin.auth.models import Permission, User, UserPermission
from hyperadmin.auth.permissions import ModelPermissionChecker, PermissionSyncService
from hyperadmin.auth.session import SessionAuthBackend
from hyperadmin.core.actions import action
from hyperadmin.core.app import Admin
from hyperadmin.core.model import ModelAdmin
from hyperadmin.core.options import AdminOptions
from hyperadmin.core.registry import site
from hyperadmin.core.settings import HyperAdminSettings

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

    from starlette.requests import Request

_db_path = os.path.join(tempfile.mkdtemp(prefix="hyperadmin_e2e_rows_"), "app.db")
engine = create_async_engine(
    f"sqlite+aiosqlite:///{_db_path}",
    connect_args={"check_same_thread": False},
)


@event.listens_for(engine.sync_engine, "connect")
def _enforce_foreign_keys(dbapi_connection: Any, _record: Any) -> None:
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.close()


class Order(SQLModel, table=True):
    __tablename__ = "e2e_rows_order"

    id: int | None = Field(default=None, primary_key=True)
    number: str = Field(max_length=20)
    customer: str = Field(default="", max_length=60)
    status: str = Field(default="new", max_length=20)

    def __str__(self) -> str:
        return self.number


class Shipment(SQLModel, table=True):
    __tablename__ = "e2e_rows_shipment"

    id: int | None = Field(default=None, primary_key=True)
    order_id: int = Field(foreign_key="e2e_rows_order.id", ondelete="RESTRICT")


class OrderAdmin(ModelAdmin):
    adapter_class = SQLModelAdapter
    options = AdminOptions(list_display=["number", "customer", "status"], list_editable=["status"])

    @action(label="Archive", bulk=True)
    async def archive(self, request: Request, item_id: int, *, params: Any = None) -> None:
        """Archives the orders."""


async def _seed() -> None:
    async with AsyncSession(engine, expire_on_commit=False) as session:
        if (await session.execute(select(User).where(User.username == "alice"))).first():
            return
        users = {
            name: User(
                username=name,
                email=f"{name}@example.com",
                password_hash=hash_password("secret123"),
                is_superuser=False,
            )
            for name in ("alice", "bob")
        }
        session.add_all(users.values())
        session.add_all(
            [
                Order(id=42, number="ORD-1042", customer="Acme", status="paid"),
                Order(id=43, number="ORD-1043", customer="Globex", status="new"),
                Order(id=44, number="ORD-1044", customer="Initech", status="shipped"),
            ]
        )
        await session.commit()
        session.add(Shipment(order_id=44))
        permissions = (await session.execute(select(Permission))).scalars().all()
        session.add_all(
            UserPermission(user_id=users["alice"].id, permission_id=p.id)
            for p in permissions
            if p.codename.endswith("_order")
        )
        session.add_all(
            UserPermission(user_id=users["bob"].id, permission_id=p.id)
            for p in permissions
            if p.codename == "view_order"
        )
        await session.commit()


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
    async with engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.create_all)
    await admin._sync_permissions()
    await _seed()
    yield


app = FastAPI(lifespan=lifespan)

site._registry = {}
site.register(Order, OrderAdmin)

admin = Admin(
    app,
    engine=engine,
    settings=HyperAdminSettings(
        create_tables=False, secret_key="e2e-list-rows-secret", auto_discover=False
    ),
    auth_backend=SessionAuthBackend(engine=engine),
    permission_checker=ModelPermissionChecker(engine=engine),
    permission_registry=PermissionSyncService(engine=engine),
)
admin.mount(path="/admin")
