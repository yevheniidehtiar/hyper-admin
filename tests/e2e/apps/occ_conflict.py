"""Optimistic-concurrency fixture app for E2E testing (v0.6.0a, #321).

Started by the ``occ_base_url`` fixture in ``tests/e2e/test_occ_conflict.py``.
Spec: ``docs/specs/realtime-occ.md``.

Registers ``Order`` (``number``, ``customer``, ``version``; ``enforce_occ=True`` and
``customer`` inline-editable) and ``Tag`` (``label``; OCC off, the legacy behaviour).
The superuser ``alice`` (password ``secret123``) may do everything.

Rows: order #42 ``ORD-1042`` (customer "Acme", version 3), tag #1 "red".
"""

from __future__ import annotations

import os
import tempfile
from contextlib import asynccontextmanager
from typing import TYPE_CHECKING, ClassVar

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

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

_db_path = os.path.join(tempfile.mkdtemp(prefix="hyperadmin_e2e_occ_"), "app.db")
engine = create_async_engine(
    f"sqlite+aiosqlite:///{_db_path}",
    connect_args={"check_same_thread": False},
)


class Order(SQLModel, table=True):
    __tablename__ = "e2e_occ_order"

    id: int | None = Field(default=None, primary_key=True)
    number: str = Field(max_length=20)
    customer: str = Field(default="", max_length=60)
    version: int = Field(default=1)

    def __str__(self) -> str:
        return self.number


class Tag(SQLModel, table=True):
    __tablename__ = "e2e_occ_tag"

    id: int | None = Field(default=None, primary_key=True)
    label: str = Field(max_length=60)

    def __str__(self) -> str:
        return self.label


class OrderAdmin(ModelAdmin):
    adapter_class = SQLModelAdapter
    options: ClassVar[AdminOptions] = AdminOptions(
        enforce_occ=True, list_editable=["customer"], warn_unsaved_changes=False
    )


class TagAdmin(ModelAdmin):
    adapter_class = SQLModelAdapter


async def _seed() -> None:
    async with AsyncSession(engine, expire_on_commit=False) as session:
        if (await session.execute(select(User).where(User.username == "alice"))).first():
            return
        session.add(
            User(
                username="alice",
                email="alice@example.com",
                password_hash=hash_password("secret123"),
                is_superuser=True,
            )
        )
        session.add(Order(id=42, number="ORD-1042", customer="Acme", version=3))
        session.add(Tag(id=1, label="red"))
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
site.register(Tag, TagAdmin)

admin = Admin(
    app,
    engine=engine,
    settings=HyperAdminSettings(
        create_tables=False, secret_key="e2e-occ-secret", auto_discover=False
    ),
    auth_backend=SessionAuthBackend(engine=engine),
    permission_checker=ModelPermissionChecker(engine=engine),
    permission_registry=PermissionSyncService(engine=engine),
)
admin.mount(path="/admin")
