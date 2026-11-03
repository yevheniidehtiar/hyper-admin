"""Navigation fixture app for E2E testing (v0.5.9, epic-v059-navigation).

Started through the ``start_server`` fixture by ``tests/e2e/test_sidebar_groups.py``.
Spec: ``docs/specs/navigation-and-list-ux.md``.

Auth is on; every user's password is ``secret123``:

* ``alice`` — superuser.
* ``bob`` — may view orders, order lines and tags only (nothing in Accounting).

Models and groups (``nav_groups`` declares Sales first, then Accounting):

* Sales: ``Order`` ("Orders", ``/admin/order``; order 42 is seeded) and
  ``OrderLine`` ("Order lines", ``/admin/orderline``).
* Accounting: ``Invoice`` and ``Bill``.
* No group: ``Tag``.
"""

from __future__ import annotations

import os
import tempfile
from contextlib import asynccontextmanager
from typing import TYPE_CHECKING

from fastapi import FastAPI
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlmodel import Field, SQLModel, select

from hyperadmin import NavGroup
from hyperadmin.auth.backend import hash_password
from hyperadmin.auth.models import Permission, User, UserPermission
from hyperadmin.auth.permissions import ModelPermissionChecker, PermissionSyncService
from hyperadmin.auth.session import SessionAuthBackend
from hyperadmin.core.app import Admin
from hyperadmin.core.model import ModelAdmin
from hyperadmin.core.registry import site
from hyperadmin.core.settings import HyperAdminSettings

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

_db_path = os.path.join(tempfile.mkdtemp(prefix="hyperadmin_e2e_nav_"), "app.db")
engine = create_async_engine(
    f"sqlite+aiosqlite:///{_db_path}",
    connect_args={"check_same_thread": False},
)


class Order(SQLModel, table=True):
    __tablename__ = "e2e_nav_order"

    id: int | None = Field(default=None, primary_key=True)
    number: str = ""


class OrderLine(SQLModel, table=True):
    __tablename__ = "e2e_nav_orderline"

    id: int | None = Field(default=None, primary_key=True)
    qty: int = 0


class Invoice(SQLModel, table=True):
    __tablename__ = "e2e_nav_invoice"

    id: int | None = Field(default=None, primary_key=True)
    number: str = ""


class Bill(SQLModel, table=True):
    __tablename__ = "e2e_nav_bill"

    id: int | None = Field(default=None, primary_key=True)
    number: str = ""


class Tag(SQLModel, table=True):
    __tablename__ = "e2e_nav_tag"

    id: int | None = Field(default=None, primary_key=True)
    name: str = ""


class OrderAdmin(ModelAdmin):
    name_plural = "Orders"
    nav_group = "Sales"
    nav_order = 0
    icon = "receipt"


class OrderLineAdmin(ModelAdmin):
    name_plural = "Order lines"
    nav_group = "Sales"
    nav_order = 1
    icon = "layers"


class InvoiceAdmin(ModelAdmin):
    name_plural = "Invoices"
    nav_group = "Accounting"
    icon = "file-text"


class BillAdmin(ModelAdmin):
    name_plural = "Bills"
    nav_group = "Accounting"
    icon = "wallet"


class TagAdmin(ModelAdmin):
    name_plural = "Tags"
    icon = "tag"


#: Model permissions of the non-superusers, by username.
GRANTS: dict[str, tuple[str, ...]] = {
    "bob": ("view_order", "view_orderline", "view_tag"),
}


async def _seed() -> None:
    async with AsyncSession(engine) as session:
        for name in ("alice", *GRANTS):
            if (await session.execute(select(User).where(User.username == name))).first() is None:
                session.add(
                    User(
                        username=name,
                        email=f"{name}@example.com",
                        password_hash=hash_password("secret123"),
                        is_superuser=name == "alice",
                    )
                )
        if (await session.execute(select(Order))).first() is None:
            session.add(Order(id=42, number="ORD-42"))
        await session.commit()

        for name, codenames in GRANTS.items():
            user = (await session.execute(select(User).where(User.username == name))).scalar_one()
            perms = (
                (
                    await session.execute(
                        select(Permission).where(Permission.codename.in_(codenames))  # type: ignore[attr-defined]
                    )
                )
                .scalars()
                .all()
            )
            for perm in perms:
                session.add(UserPermission(user_id=user.id, permission_id=perm.id))
        await session.commit()


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
    async with engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.create_all)
    await admin.startup()
    await _seed()
    yield


app = FastAPI(lifespan=lifespan)

site._registry = {}
site.register(Order, OrderAdmin)
site.register(OrderLine, OrderLineAdmin)
site.register(Invoice, InvoiceAdmin)
site.register(Bill, BillAdmin)
site.register(Tag, TagAdmin)

admin = Admin(
    app,
    engine=engine,
    settings=HyperAdminSettings(
        create_tables=False, secret_key="e2e-navigation-secret", auto_discover=False
    ),
    auth_backend=SessionAuthBackend(engine=engine),
    permission_checker=ModelPermissionChecker(engine=engine),
    permission_registry=PermissionSyncService(engine=engine),
    nav_groups=[NavGroup("Sales", icon="shopping-cart", order=0), NavGroup("Accounting", order=1)],
)
admin.mount(path="/admin")


@app.get("/")
def root() -> dict[str, str]:
    return {"status": "ok"}
