"""Detail-panel HyperAdmin app for E2E testing (``docs/specs/detail-panels.md``).

Started by the ``panels_base_url`` fixture in ``tests/e2e/test_detail_panels.py``.
Registers an ``Order`` model whose detail page has one panel per scenario:

* ``invoice`` — the bundled ``pdf_stream_panel`` streaming ``tests/_fixtures/sample.pdf``
* ``history`` — a ``@panel`` method returning HTML
* ``refused`` — a handler that raises ``HTTPException(403)``
* ``receipt`` — hidden by its ``enabled`` predicate unless the order is paid

Seeded users (password ``secret123``):

* ``alice`` — superuser
* ``bob`` — holds ``view_order`` and ``view_order_panel_history`` only, so the
  Invoice tab is omitted for him and its URL answers 403.

Orders: #1 ``unpaid`` (``paid=False``) and #2 ``paid`` (``paid=True``).
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path
from typing import TYPE_CHECKING, Any, ClassVar

from fastapi import FastAPI, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlmodel import Field, SQLModel, select
from starlette.responses import HTMLResponse, Response

from hyperadmin.auth.backend import hash_password
from hyperadmin.auth.models import Permission, User, UserPermission
from hyperadmin.auth.permissions import ModelPermissionChecker, PermissionSyncService
from hyperadmin.auth.session import SessionAuthBackend
from hyperadmin.core.app import Admin
from hyperadmin.core.model import ModelAdmin
from hyperadmin.core.options import AdminOptions
from hyperadmin.core.panels import PanelDef, panel
from hyperadmin.core.registry import site
from hyperadmin.core.settings import HyperAdminSettings
from hyperadmin.panels import pdf_stream_panel

if TYPE_CHECKING:
    from starlette.requests import Request

SAMPLE_PDF = Path(__file__).resolve().parents[2] / "_fixtures" / "sample.pdf"

#: What bob may do: the detail page and the History panel, nothing else.
BOB_PERMISSIONS = ("view_order", "view_order_panel_history")

#: Panel codenames ``PermissionSyncService`` does not derive; seeded by hand.
PANEL_PERMISSIONS = (
    "view_order_panel_invoice",
    "view_order_panel_history",
    "view_order_panel_refused",
    "view_order_panel_receipt",
)

engine = create_async_engine(
    "sqlite+aiosqlite:///:memory:",
    connect_args={"check_same_thread": False},
)


class Order(SQLModel, table=True):
    __tablename__ = "e2e_panel_order"

    id: int | None = Field(default=None, primary_key=True)
    title: str = Field(max_length=120)
    paid: bool = False


async def _refused(request: Request, obj: Any) -> Response:
    raise HTTPException(status_code=403, detail="handler says no")


async def _receipt(request: Request, obj: Any) -> Response:
    return HTMLResponse(f'<p data-testid="receipt-body">Receipt for {obj.title}</p>')


class OrderAdmin(ModelAdmin):
    options: ClassVar[AdminOptions] = AdminOptions(
        panels=[
            pdf_stream_panel(
                slug="invoice",
                label="Invoice",
                icon="file-text",
                path_resolver=lambda _order: SAMPLE_PDF,
            ),
            PanelDef(slug="refused", label="Refused", handler=_refused),
            PanelDef(
                slug="receipt", label="Receipt", handler=_receipt, enabled=lambda o: bool(o.paid)
            ),
        ]
    )

    @panel(label="History", icon="clock")
    async def history(self, request: Request, obj: Any) -> Response:
        return HTMLResponse(
            f'<p data-testid="history-body">Order {obj.title} was created by alice.</p>'
        )


async def _seed() -> None:
    async with AsyncSession(engine, expire_on_commit=False) as session:
        if (await session.execute(select(User).where(User.username == "alice"))).first():
            return
        alice = User(
            username="alice",
            email="alice@example.com",
            password_hash=hash_password("secret123"),
            is_superuser=True,
        )
        bob = User(
            username="bob",
            email="bob@example.com",
            password_hash=hash_password("secret123"),
            is_superuser=False,
        )
        session.add_all([alice, bob])
        session.add_all(
            Permission(codename=codename, name=codename.replace("_", " "), content_type="order")
            for codename in PANEL_PERMISSIONS
        )
        session.add_all(
            [Order(id=1, title="unpaid", paid=False), Order(id=2, title="paid", paid=True)]
        )
        await session.commit()

        perms = (
            await session.execute(
                select(Permission).where(
                    Permission.codename.in_(BOB_PERMISSIONS)  # type: ignore[attr-defined]
                )
            )
        ).scalars()
        assert bob.id is not None
        session.add_all(UserPermission(user_id=bob.id, permission_id=perm.id) for perm in perms)
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
        create_tables=False, secret_key="e2e-panels-secret", auto_discover=False
    ),
    auth_backend=SessionAuthBackend(engine=engine),
    permission_checker=ModelPermissionChecker(engine=engine),
    permission_registry=PermissionSyncService(engine=engine),
)
admin.mount(path="/admin")
