"""Object-level-permission HyperAdmin app for E2E testing (C3-B, #482).

Spec: ``docs/specs/object-permissions-mfa.md`` — Track A.

Two test models keep each enforcement layer isolated, so individual
scenarios pin down a single rule:

* ``Order`` — protected ONLY by an :class:`ObjectPermissionChecker` that
  denies non-superusers any interaction with id 40. ``OrderAdmin`` does
  NOT override ``get_queryset`` (every row is visible to every authenticated
  user; the only authz layer that can deny is the object-level checker).
  Verifies the 4 detail/update/delete/superuser-bypass scenarios.
* ``Document`` — protected ONLY by an ``OwnerScopedAdmin.get_queryset``
  that filters list/detail to ``request.state.user.id`` for non-superusers.
  No object-permission checker is attached. Verifies the RLS list scenario.

Seeded users (password ``secret123`` for both):
  * ``bob`` (id=1) — non-superuser holding all model-level Order permissions
    (so any 403 is purely the object-level checker, not the model-level one).
  * ``admin`` (id=2) — superuser, used to verify the bypass scenario.

Seeded data:
  * Orders: #10/#20 (owner_id=1, bob), #40 (owner_id=99).
  * Documents: #100/#200 owned by bob (id=1); #400 owned by user 99.
"""

from __future__ import annotations

import os
from typing import TYPE_CHECKING, Any

from fastapi import FastAPI
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlmodel import Field, SQLModel, select

if TYPE_CHECKING:
    from starlette.requests import Request

from hyperadmin.auth.backend import hash_password
from hyperadmin.auth.models import (
    Permission,
    User,
    UserPermission,
)
from hyperadmin.auth.permissions import (
    ModelPermissionChecker,
    PermissionSyncService,
)
from hyperadmin.auth.session import SessionAuthBackend
from hyperadmin.core.app import Admin
from hyperadmin.core.model import ModelAdmin
from hyperadmin.core.options import AdminOptions
from hyperadmin.core.registry import site
from hyperadmin.core.settings import HyperAdminSettings


class Order(SQLModel, table=True):
    """Order model — protected by an ObjectPermissionChecker only."""

    __tablename__ = "test_e2e_order_object_perm"

    id: int | None = Field(default=None, primary_key=True)
    title: str = Field(max_length=120)
    owner_id: int = Field(default=0, index=True)


class Document(SQLModel, table=True):
    """Document model — protected by ModelAdmin.get_queryset (RLS) only."""

    __tablename__ = "test_e2e_document_rls"

    id: int | None = Field(default=None, primary_key=True)
    title: str = Field(max_length=120)
    owner_id: int = Field(default=0, index=True)


# Use a single shared on-disk SQLite database file so the uvicorn subprocess
# (and any sub-workers) sees the seeded users + rows. ``sqlite:///:memory:``
# creates a per-connection isolated DB, which would defeat the seed.
_DB_PATH = os.environ.get("HYPERADMIN_E2E_OBJPERM_DB", "/tmp/hyperadmin-e2e-objperm.db")  # noqa: S108
if os.path.exists(_DB_PATH):
    os.remove(_DB_PATH)

engine = create_async_engine(
    f"sqlite+aiosqlite:///{_DB_PATH}",
    connect_args={"check_same_thread": False},
)


class _BlockOrderFortyChecker:
    """ObjectPermissionChecker that denies non-superusers access to order id=40.

    Models the SDD's "superuser bypass lives in the checker, not the helper"
    requirement: superusers are explicitly allowed regardless of object id.
    """

    BLOCKED_ID = 40

    async def has_object_permission(self, user: Any, obj: Any, action: str) -> bool:
        if getattr(user, "is_superuser", False):
            return True
        return getattr(obj, "id", None) != self.BLOCKED_ID


class OrderAdmin(ModelAdmin):
    """No row-level filter — only the ObjectPermissionChecker can deny."""


class DocumentAdmin(ModelAdmin):
    """Row-level scoped to ``request.state.user.id`` for non-superusers.

    Used to verify ``ModelAdmin.get_queryset`` flows into the rendered list
    table without a separate object-permission layer.
    """

    def get_queryset(self, request: Request | None = None) -> dict[str, Any]:
        if request is None:
            return {}
        user = getattr(request.state, "user", None)
        if user is None:
            return {}
        if getattr(user, "is_superuser", False):
            return {}
        return {"owner_id": user.id}


async def _seed() -> None:
    """Create users, grant model-level permissions, and seed orders + documents.

    After this runs:
      * ``bob`` (id=1) is a non-superuser with all Order CRUD model permissions
        (so any 403 we observe in the 4 object-permission scenarios is
        unambiguously caused by the OBJECT-level checker, not by the
        model-level one).
      * ``admin`` (id=2) is a superuser.
      * Orders ``#10/#20`` (owner_id=1) and ``#40`` (owner_id=99).
      * Documents ``#100/#200`` (owner_id=1) and ``#400`` (owner_id=99).
    """
    async with AsyncSession(engine) as session:
        existing = await session.execute(select(User).where(User.username == "bob"))
        if existing.scalar_one_or_none() is None:
            session.add(
                User(
                    id=1,
                    username="bob",
                    email="bob@example.com",
                    password_hash=hash_password("secret123"),
                    is_superuser=False,
                )
            )
            session.add(
                User(
                    id=2,
                    username="admin",
                    email="admin@example.com",
                    password_hash=hash_password("secret123"),
                    is_superuser=True,
                )
            )
            await session.commit()

        existing_orders = (await session.execute(select(Order))).scalars().all()
        if not existing_orders:
            session.add(Order(id=10, title="bob-order-A", owner_id=1))
            session.add(Order(id=20, title="bob-order-B", owner_id=1))
            session.add(Order(id=40, title="alice-order-A", owner_id=99))
            await session.commit()

        existing_docs = (await session.execute(select(Document))).scalars().all()
        if not existing_docs:
            session.add(Document(id=100, title="bob-doc-A", owner_id=1))
            session.add(Document(id=200, title="bob-doc-B", owner_id=1))
            session.add(Document(id=400, title="alice-doc-A", owner_id=99))
            await session.commit()

        # Grant bob the model-level Order + Document permissions so any
        # observed 403/404 is attributable to the layer under test, not to
        # missing model-level grants.
        codenames = [
            "view_order",
            "change_order",
            "delete_order",
            "view_document",
            "change_document",
            "delete_document",
        ]
        perms = (
            (
                await session.execute(
                    select(Permission).where(
                        Permission.codename.in_(codenames)  # type: ignore[attr-defined]
                    )
                )
            )
            .scalars()
            .all()
        )
        existing_grants = (
            (await session.execute(select(UserPermission).where(UserPermission.user_id == 1)))
            .scalars()
            .all()
        )
        granted_ids = {g.permission_id for g in existing_grants}
        for perm in perms:
            if perm.id is not None and perm.id not in granted_ids:
                session.add(UserPermission(user_id=1, permission_id=perm.id))
        await session.commit()


app = FastAPI()

backend = SessionAuthBackend(engine=engine)
settings = HyperAdminSettings(
    create_tables=False,
    secret_key="e2e-object-perm-secret",
    auto_discover=False,  # we register models ourselves with custom admins.
)


# Register the test models BEFORE ``Admin.mount()`` so their options carry the
# object-permission checker / queryset hook into the generated routes.
site._registry = {}  # clean registry per process
site.register(
    Order,
    admin_class=OrderAdmin,
    options=AdminOptions(object_permission_checker=_BlockOrderFortyChecker()),
)
site.register(Document, admin_class=DocumentAdmin)

admin = Admin(
    app,
    engine=engine,
    settings=settings,
    auth_backend=backend,
    permission_checker=ModelPermissionChecker(engine=engine),
    permission_registry=PermissionSyncService(engine=engine),
)
admin.mount(path="/admin")


# Startup ordering:
# 1. Create tables (so PermissionSyncService can write to hyperadmin_permissions).
# 2. ``_sync_permissions`` (queued by ``Admin.mount`` and copied to
#    ``app.router.on_startup`` by ``include_router``) — creates the
#    order_*/document_* Permission rows.
# 3. ``_seed`` — seeds users, orders, documents, and bob's permission grants.
#
# Registering on ``app.router.on_startup`` directly preserves ordering
# relative to the ``include_router``-copied hook.


async def _create_tables() -> None:
    async with engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.create_all)


app.router.on_startup.insert(0, _create_tables)
app.router.on_startup.append(_seed)
