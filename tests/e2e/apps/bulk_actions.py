"""Bulk-action fixture app for E2E testing (H3, v0.5.5).

Started by the ``bulk_base_url`` fixture via a uvicorn subprocess. Spec:
``docs/specs/bulk-actions.md`` (BDD scenarios); design:
``docs/design/system/components/BulkActionFlow``.

Auth is on (superuser ``alice / secret123``) so the CSRF guard and the
object-permission layer both apply, exactly as in a consumer admin.

Registered model ``Order`` (int primary key) with three bulk actions:

* ``archive`` — formless, ``requires_selection=True`` (the default for
  ``bulk=True``). Raises ``HTTPException(403, "permission denied")`` for the
  id listed in ``/_test/forbid`` (the "per-row failure" scenario) and calls
  ``adapter.delete`` otherwise.
* ``reassign`` — ``form=ReassignParams`` (``operator: int``). Records each
  call with its validated params.
* ``archive_overdue`` — ``requires_selection=False`` (kept so the bar offers
  an action that may run over nothing).

The configured :class:`ObjectPermissionChecker` denies ``action_archive`` on
the id listed in ``/_test/deny`` (the "object-level permission" scenario).

Host routes outside the admin, for the tests to observe the handler:

* ``GET /_test/calls`` — the handler calls so far, as
  ``[{"action", "id", "operator"}]``; ``adapter.delete`` calls are listed
  under ``"deleted"``.
* ``POST /_test/reset`` — clears the recorded calls and both deny lists.
* ``POST /_test/forbid?id=N`` — ``archive`` raises 403 for ``N``.
* ``POST /_test/deny?id=N`` — the checker denies ``action_archive`` on ``N``.
"""

from __future__ import annotations

import os
import tempfile
from contextlib import asynccontextmanager
from typing import TYPE_CHECKING, Any

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlmodel import Field, SQLModel, select

from hyperadmin.adapters.sqlmodel import SQLModelAdapter
from hyperadmin.auth.backend import hash_password
from hyperadmin.auth.models import User
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

_db_path = os.path.join(tempfile.mkdtemp(prefix="hyperadmin_e2e_bulk_"), "app.db")
engine = create_async_engine(
    f"sqlite+aiosqlite:///{_db_path}",
    connect_args={"check_same_thread": False},
)


class Order(SQLModel, table=True):
    __tablename__ = "e2e_bulk_order"

    id: int | None = Field(default=None, primary_key=True)
    title: str = Field(min_length=1)
    operator: int = 0


class ReassignParams(BaseModel):
    operator: int


# Observable state for the tests (one uvicorn process, so module globals do).
STATE: dict[str, Any] = {"calls": [], "deleted": [], "forbid": set(), "deny": set()}


def _reset_state() -> None:
    STATE["calls"] = []
    STATE["deleted"] = []
    STATE["forbid"] = set()
    STATE["deny"] = set()


class _DenyArchiveChecker:
    """ObjectPermissionChecker that denies ``action_archive`` on the ids in ``STATE["deny"]``."""

    async def has_object_permission(self, user: Any, obj: Any, action: str) -> bool:
        return not (action == "action_archive" and getattr(obj, "id", None) in STATE["deny"])


class OrderAdmin(ModelAdmin):
    adapter_class = SQLModelAdapter
    options = AdminOptions(object_permission_checker=_DenyArchiveChecker())

    @action(label="Archive", bulk=True)
    async def archive(self, request: Request, item_id: int, *, params: Any = None) -> None:
        """Archives the orders. They disappear from the list."""
        if item_id in STATE["forbid"]:
            raise HTTPException(status_code=403, detail="permission denied")
        STATE["calls"].append({"action": "archive", "id": item_id, "operator": None})
        await self.adapter.delete(pk=item_id)
        STATE["deleted"].append(item_id)

    @action(label="Reassign", bulk=True, form=ReassignParams)
    async def reassign(
        self,
        request: Request,
        item_id: int,
        *,
        params: ReassignParams | None = None,
    ) -> None:
        """Moves the orders to another operator. Customers are not notified."""
        operator = params.operator if params is not None else None
        STATE["calls"].append({"action": "reassign", "id": item_id, "operator": operator})

    @action(label="Archive overdue", bulk=True, requires_selection=False)
    async def archive_overdue(
        self,
        request: Request,
        item_id: int,
        *,
        params: Any = None,
    ) -> None:
        """Archives the overdue orders among the selection."""
        STATE["calls"].append({"action": "archive_overdue", "id": item_id, "operator": None})


async def _seed() -> None:
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
        if (await session.execute(select(Order))).first() is None:
            session.add_all(
                [
                    Order(id=1, title="ORD-1"),
                    Order(id=2, title="ORD-2"),
                    Order(id=3, title="ORD-3"),
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
    secret_key="e2e-bulk-actions-secret",
    auto_discover=False,
)

site._registry = {}
site.register(Order, OrderAdmin)

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


@app.get("/_test/calls")
def calls() -> dict[str, Any]:
    """Return the handler calls and ``adapter.delete`` calls recorded so far."""
    return {"calls": STATE["calls"], "deleted": STATE["deleted"]}


@app.post("/_test/reset")
def reset() -> dict[str, str]:
    _reset_state()
    return {"status": "ok"}


@app.post("/_test/forbid")
def forbid(id: int) -> dict[str, str]:  # noqa: A002
    """Make ``archive`` raise HTTPException(403) for ``id``."""
    STATE["forbid"].add(id)
    return {"status": "ok"}


@app.post("/_test/deny")
def deny(id: int) -> dict[str, str]:  # noqa: A002
    """Make the object-permission checker deny ``action_archive`` on ``id``."""
    STATE["deny"].add(id)
    return {"status": "ok"}
