"""Scalability fixture app for E2E testing (#243).

Started by the ``scalability_base_url`` fixture in ``tests/e2e/test_scalability.py``, which seeds
the SQLite file named by ``E2E_SCALABILITY_DB`` first (see
:mod:`tests.e2e.apps.scalability_models` for the tables and their sizes). Started on its own,
the app seeds the default dataset into a temporary file at startup.

Auth is on (superuser ``alice / secret123``). Every scalability option is set the way a host
with large tables would set it:

* ``Product`` - page-numbered list that shows the ``supplier`` relation, searches ``sku`` only,
  caches its total for a minute and filters by ``warehouse`` (filter choices cached by default).
  Its form has a foreign key to a large table (``Supplier``) and to a small one (``Warehouse``).
* ``Movement`` - ``pagination_mode="cursor"`` list that shows the ``product`` relation.

Host routes outside the admin (no auth):

* ``POST /_test/reset`` - forget the recorded SQL statements.
* ``GET /_test/queries`` - the SQL statements run since the last reset, each as
  ``{"sql": ..., "params": [...]}``.
"""

from __future__ import annotations

import asyncio
import os
import tempfile
from contextlib import asynccontextmanager
from pathlib import Path
from typing import TYPE_CHECKING, Any, ClassVar

from fastapi import FastAPI
from sqlalchemy import event
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlmodel import SQLModel, select

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
from tests.e2e.apps.scalability_models import (
    Movement,
    Product,
    Supplier,
    Warehouse,
    scale,
    seed_database,
)

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

_db_path = os.environ.get("E2E_SCALABILITY_DB", "")
# Without a database from the test fixture, the app seeds its own at startup.
_seed_at_startup = not _db_path
if _seed_at_startup:
    _db_path = os.path.join(tempfile.mkdtemp(prefix="hyperadmin_e2e_scalability_"), "app.db")

engine = create_async_engine(
    f"sqlite+aiosqlite:///{_db_path}",
    connect_args={"check_same_thread": False},
)

STATEMENTS: list[dict[str, Any]] = []


@event.listens_for(engine.sync_engine, "before_cursor_execute")
def _record(_conn: Any, _cursor: Any, statement: str, parameters: Any, *_rest: Any) -> None:
    params = parameters if isinstance(parameters, (list, tuple)) else [parameters]
    STATEMENTS.append({"sql": " ".join(statement.split()), "params": [str(p) for p in params]})


class WarehouseAdmin(ModelAdmin):
    adapter_class = SQLModelAdapter


class SupplierAdmin(ModelAdmin):
    adapter_class = SQLModelAdapter
    options: ClassVar[AdminOptions] = AdminOptions(search_fields=["name"])


class ProductAdmin(ModelAdmin):
    adapter_class = SQLModelAdapter
    options: ClassVar[AdminOptions] = AdminOptions(
        list_display=["sku", "name", "supplier"],
        search_fields=["sku"],
        list_filter=["warehouse_id"],
        count_cache_ttl=60,
    )


class MovementAdmin(ModelAdmin):
    adapter_class = SQLModelAdapter
    options: ClassVar[AdminOptions] = AdminOptions(
        list_display=["reference", "quantity", "product"],
        search_fields=["reference"],
        pagination_mode="cursor",
    )


async def _seed_admin_user() -> None:
    async with engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.create_all)
    async with AsyncSession(engine) as session:
        if (await session.execute(select(User).where(User.username == "alice"))).first() is None:
            session.add(
                User(
                    username="alice",
                    email="alice@example.com",
                    password_hash=hash_password("secret123"),
                    is_superuser=True,
                )
            )
            await session.commit()


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
    if _seed_at_startup:
        await asyncio.to_thread(seed_database, Path(_db_path), scale())
    await _seed_admin_user()
    yield


app = FastAPI(lifespan=lifespan)


@app.post("/_test/reset")
async def reset() -> dict[str, bool]:
    """Forget the recorded SQL statements."""
    STATEMENTS.clear()
    return {"ok": True}


@app.get("/_test/queries")
async def queries() -> dict[str, list[dict[str, Any]]]:
    """Return the SQL statements run since the last reset."""
    return {"statements": list(STATEMENTS)}


site._registry = {}
site.register(Warehouse, WarehouseAdmin)
site.register(Supplier, SupplierAdmin)
site.register(Product, ProductAdmin)
site.register(Movement, MovementAdmin)

admin = Admin(
    app,
    engine=engine,
    settings=HyperAdminSettings(
        create_tables=False,
        secret_key="e2e-scalability-secret",
        auto_discover=False,
    ),
    auth_backend=SessionAuthBackend(engine=engine),
    permission_checker=ModelPermissionChecker(engine=engine),
    permission_registry=PermissionSyncService(engine=engine),
)
admin.mount(path="/admin")
