"""Form-safety fixture app for E2E testing (v0.5.9, st-v059-kbd-01).

Started by the ``form_safety_base_url`` fixture in ``tests/e2e/test_form_safety.py``.
Spec: ``docs/specs/navigation-and-list-ux.md`` ("Form safety (kbd-01)").

Registers ``Order`` (``number``, ``customer``, ``notes``; the unsaved-changes guard
on, the default) and ``Note`` (``title``; ``AdminOptions(warn_unsaved_changes=False)``).
The superuser ``alice`` (password ``secret123``) may do everything.

Rows: order #42 ``ORD-1042`` (customer "Acme"), note #1 "Call Acme".
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

_db_path = os.path.join(tempfile.mkdtemp(prefix="hyperadmin_e2e_form_safety_"), "app.db")
engine = create_async_engine(
    f"sqlite+aiosqlite:///{_db_path}",
    connect_args={"check_same_thread": False},
)


class Order(SQLModel, table=True):
    __tablename__ = "e2e_guard_order"

    id: int | None = Field(default=None, primary_key=True)
    number: str = Field(max_length=20)
    customer: str = Field(default="", max_length=60)
    notes: str = Field(default="", max_length=400)

    def __str__(self) -> str:
        return self.number


class Note(SQLModel, table=True):
    __tablename__ = "e2e_guard_note"

    id: int | None = Field(default=None, primary_key=True)
    title: str = Field(max_length=60)

    def __str__(self) -> str:
        return self.title


class OrderAdmin(ModelAdmin):
    adapter_class = SQLModelAdapter


class NoteAdmin(ModelAdmin):
    adapter_class = SQLModelAdapter
    options: ClassVar[AdminOptions] = AdminOptions(warn_unsaved_changes=False)


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
        session.add(Order(id=42, number="ORD-1042", customer="Acme"))
        session.add(Note(id=1, title="Call Acme"))
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
site.register(Note, NoteAdmin)

admin = Admin(
    app,
    engine=engine,
    settings=HyperAdminSettings(
        create_tables=False, secret_key="e2e-form-safety-secret", auto_discover=False
    ),
    auth_backend=SessionAuthBackend(engine=engine),
    permission_checker=ModelPermissionChecker(engine=engine),
    permission_registry=PermissionSyncService(engine=engine),
)
admin.mount(path="/admin")
