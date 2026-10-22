"""Permission-matrix HyperAdmin app for E2E testing (``docs/specs/permission-matrix-ui.md``).

Started by the ``matrix_base_url`` fixture in ``tests/e2e/test_permissions_matrix.py``.
Registers ``Order`` (with an extra ``export_order`` permission, so the grid has a
column that does not apply to every model), ``Invoice`` and ``Product``.

Users (password ``secret123``):

* ``alice`` — superuser.
* ``editor`` — holds ``change_groups_permissions`` plus view/add/change/export
  Order and view Invoice; not ``delete_order`` and not ``add_invoice``, so a
  save that grants either is rejected (403).
* ``viewer`` — a member of ``Viewers`` only: sees the matrix link neither in the
  sidebar nor by URL (403), and may view but not edit orders.

Groups:

* ``Editors`` — view/change/add Order, view Invoice; two object rules on Order
  (change #1, view #2).
* ``Viewers`` — view Order.
* ``Finance`` — nothing yet.

Orders #1 and #2 are seeded. The host exposes ``POST /_test/bump?group=<name>``,
which bumps that group's ``permissions_version`` the way a save by someone
else would, for the conflict scenario.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlmodel import Field, SQLModel, select

from hyperadmin.auth.backend import hash_password
from hyperadmin.auth.models import (
    Group,
    GroupPermission,
    Permission,
    User,
    UserGroup,
    UserPermission,
)
from hyperadmin.auth.permissions import ModelPermissionChecker, PermissionSyncService
from hyperadmin.auth.session import SessionAuthBackend
from hyperadmin.core.app import Admin
from hyperadmin.core.model import ModelAdmin
from hyperadmin.core.registry import site
from hyperadmin.core.settings import HyperAdminSettings
from hyperadmin.permissions import ObjectRuleKey, ObjectRuleService

MATRIX_CODENAME = "change_groups_permissions"
EDITOR_PERMISSIONS = (
    MATRIX_CODENAME,
    "view_order",
    "add_order",
    "change_order",
    "export_order",
    "view_invoice",
)
GROUPS: dict[str, tuple[str, ...]] = {
    "Editors": ("view_order", "change_order", "add_order", "view_invoice"),
    "Viewers": ("view_order",),
    "Finance": (),
}

engine = create_async_engine(
    "sqlite+aiosqlite:///:memory:",
    connect_args={"check_same_thread": False},
)


class Order(SQLModel, table=True):
    __tablename__ = "e2e_pmx_order"

    id: int | None = Field(default=None, primary_key=True)
    title: str = Field(max_length=120)


class Invoice(SQLModel, table=True):
    __tablename__ = "e2e_pmx_invoice"

    id: int | None = Field(default=None, primary_key=True)
    number: str = Field(max_length=40)


class Product(SQLModel, table=True):
    __tablename__ = "e2e_pmx_product"

    id: int | None = Field(default=None, primary_key=True)
    name: str = Field(max_length=120)


class OrderAdmin(ModelAdmin):
    permissions = [("export_order", "Can export order")]


async def _seed() -> None:
    async with AsyncSession(engine, expire_on_commit=False) as session:
        if (await session.execute(select(User).where(User.username == "alice"))).first():
            return
        ids = dict((await session.execute(select(Permission.codename, Permission.id))).all())
        users = {
            name: User(
                username=name,
                email=f"{name}@example.com",
                password_hash=hash_password("secret123"),
                is_superuser=name == "alice",
            )
            for name in ("alice", "editor", "viewer")
        }
        groups = {name: Group(name=name) for name in GROUPS}
        session.add_all([*users.values(), *groups.values()])
        session.add_all([Order(id=1, title="first"), Order(id=2, title="second")])
        await session.commit()

        session.add_all(
            UserPermission(user_id=users["editor"].id, permission_id=ids[codename])
            for codename in EDITOR_PERMISSIONS
        )
        session.add_all(
            GroupPermission(group_id=groups[name].id, permission_id=ids[codename])
            for name, codenames in GROUPS.items()
            for codename in codenames
        )
        session.add(UserGroup(user_id=users["viewer"].id, group_id=groups["Viewers"].id))
        await session.commit()
        editors_id = groups["Editors"].id

    assert editors_id is not None
    rules = ObjectRuleService(engine=engine)
    await rules.add(
        editors_id, ObjectRuleKey(model="order", codename="change_order", object_pk="1")
    )
    await rules.add(editors_id, ObjectRuleKey(model="order", codename="view_order", object_pk="2"))


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
    async with engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.create_all)
    await admin._sync_permissions()
    await _seed()
    yield


app = FastAPI(lifespan=lifespan)


@app.post("/_test/bump")
async def bump_version(group: str) -> dict[str, int]:
    """Bump ``group``'s ``permissions_version`` as a save by someone else would."""
    async with AsyncSession(engine, expire_on_commit=False) as session:
        row = (await session.execute(select(Group).where(Group.name == group))).scalar_one()
        version = row.permissions_version + 1
        row.permissions_version = version
        session.add(row)
        await session.commit()
    return {"version": version}


site._registry = {}
site.register(Order, OrderAdmin)
site.register(Invoice, ModelAdmin)
site.register(Product, ModelAdmin)

admin = Admin(
    app,
    engine=engine,
    settings=HyperAdminSettings(
        create_tables=False, secret_key="e2e-matrix-secret", auto_discover=False
    ),
    auth_backend=SessionAuthBackend(engine=engine),
    permission_checker=ModelPermissionChecker(engine=engine),
    permission_registry=PermissionSyncService(engine=engine),
)
admin.mount(path="/admin")
