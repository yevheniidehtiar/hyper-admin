"""Command palette app for E2E tests (st-v059-nav-04).

Spec: ``docs/specs/navigation-and-list-ux.md`` (Palette).

Models: ``Invoice`` and ``Bill`` in the "Accounting" group, ``Order`` in "Sales"
(seeded with order "ORD-1042", id 1042).

Seeded users (password ``secret123``):
  * ``alice`` — superuser: sees everything, may create everything.
  * ``bob`` — view_invoice, view_bill and view_order, but not add_invoice.
  * ``carol`` — view_order and view_bill only (no view_invoice).
"""

from __future__ import annotations

import os

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


class Invoice(SQLModel, table=True):
    __tablename__ = "test_e2e_palette_invoice"

    id: int | None = Field(default=None, primary_key=True)
    number: str = Field(max_length=40)


class Bill(SQLModel, table=True):
    __tablename__ = "test_e2e_palette_bill"

    id: int | None = Field(default=None, primary_key=True)
    number: str = Field(max_length=40)


class Order(SQLModel, table=True):
    __tablename__ = "test_e2e_palette_order"

    id: int | None = Field(default=None, primary_key=True)
    number: str = Field(max_length=40)

    def __str__(self) -> str:
        return self.number


class InvoiceAdmin(ModelAdmin):
    nav_group = "Accounting"
    icon = "receipt"


class BillAdmin(ModelAdmin):
    nav_group = "Accounting"
    icon = "wallet"


class OrderAdmin(ModelAdmin):
    nav_group = "Sales"
    icon = "shopping-cart"


_DB_PATH = os.environ.get("HYPERADMIN_E2E_PALETTE_DB", "/tmp/hyperadmin-e2e-palette.db")  # noqa: S108
if os.path.exists(_DB_PATH):
    os.remove(_DB_PATH)

engine = create_async_engine(
    f"sqlite+aiosqlite:///{_DB_PATH}", connect_args={"check_same_thread": False}
)

_GRANTS = {
    3: ["view_invoice", "view_bill", "view_order"],  # bob: no add_invoice
    4: ["view_order", "view_bill"],  # carol: no view_invoice
}


async def _seed() -> None:
    async with AsyncSession(engine) as session:
        if (await session.execute(select(User))).first() is None:
            for user_id, name, superuser in (
                (2, "alice", True),
                (3, "bob", False),
                (4, "carol", False),
            ):
                session.add(
                    User(
                        id=user_id,
                        username=name,
                        email=f"{name}@example.com",
                        password_hash=hash_password("secret123"),
                        is_superuser=superuser,
                    )
                )
            session.add(Order(id=1042, number="ORD-1042"))
            session.add(Invoice(id=1, number="INV-1"))
            session.add(Bill(id=1, number="BILL-1"))
            await session.commit()
        perms = {p.codename: p.id for p in (await session.execute(select(Permission))).scalars()}
        for user_id, codenames in _GRANTS.items():
            for codename in codenames:
                session.add(UserPermission(user_id=user_id, permission_id=perms[codename]))
        await session.commit()


async def _create_tables() -> None:
    async with engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.create_all)


app = FastAPI()

site._registry = {}
site.register(Invoice, admin_class=InvoiceAdmin)
site.register(Bill, admin_class=BillAdmin)
site.register(Order, admin_class=OrderAdmin)

admin = Admin(
    app,
    engine=engine,
    settings=HyperAdminSettings(
        create_tables=False, secret_key="e2e-palette-secret", auto_discover=False
    ),
    auth_backend=SessionAuthBackend(engine=engine),
    permission_checker=ModelPermissionChecker(engine=engine),
    permission_registry=PermissionSyncService(engine=engine),
    nav_groups=[NavGroup("Sales", order=0), NavGroup("Accounting", order=1)],
)
admin.mount(path="/admin")

app.router.on_startup.insert(0, _create_tables)
app.router.on_startup.append(admin._sync_permissions)
app.router.on_startup.append(_seed)
