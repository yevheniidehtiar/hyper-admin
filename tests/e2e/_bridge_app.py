"""Bridge-mode HyperAdmin app for E2E testing (st-v058-byoa-46, SDD B.3 / D.1).

Started by the ``bridge_base_url`` fixture via uvicorn subprocess. The host
authenticates with its own ``host_user`` cookie (no built-in login); the admin
is wired with ``Admin(auth=ExternalAuth(...))``, so CSRF is enforced.

Seeded host user ``ada`` (superuser, display name ``Ada``) and orders #1, #2.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import Cookie, FastAPI
from sqlalchemy.ext.asyncio import create_async_engine
from sqlmodel import Field, SQLModel
from sqlmodel.ext.asyncio.session import AsyncSession

from hyperadmin.adapters.sqlmodel import SQLModelAdapter
from hyperadmin.auth.bridge import ExternalAuth
from hyperadmin.core.app import Admin
from hyperadmin.core.model import ModelAdmin
from hyperadmin.core.registry import site
from hyperadmin.core.settings import HyperAdminSettings


class HostUser(SQLModel, table=True):
    """The host application's own user model."""

    __tablename__ = "test_e2e_bridge_host_user"

    id: int | None = Field(default=None, primary_key=True)
    username: str = ""
    full_name: str = ""
    is_superuser: bool = False


class BridgeOrder(SQLModel, table=True):
    __tablename__ = "test_e2e_bridge_order"

    id: int | None = Field(default=None, primary_key=True)
    title: str = ""


class BridgeOrderAdmin(ModelAdmin):
    adapter_class = SQLModelAdapter


ADA = HostUser(id=1, username="ada", full_name="Ada", is_superuser=True)

engine = create_async_engine(
    "sqlite+aiosqlite:///:memory:",
    connect_args={"check_same_thread": False},
)


def get_current_user(host_user: str | None = Cookie(default=None)) -> HostUser | None:
    """The host's ``get_user``: its own session cookie, ``None`` when anonymous."""
    return ADA if host_user == "ada" else None


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
    async with engine.begin() as conn:
        await conn.run_sync(
            SQLModel.metadata.create_all,
            tables=[HostUser.__table__, BridgeOrder.__table__],  # type: ignore[attr-defined]
        )
    async with AsyncSession(engine) as session:
        session.add(BridgeOrder(id=1, title="first"))
        session.add(BridgeOrder(id=2, title="second"))
        await session.commit()
    yield


app = FastAPI(lifespan=lifespan)


@app.get("/healthz")
def healthz() -> dict[str, str]:
    """Readiness probe for the E2E fixture (bridge mode has no admin login page)."""
    return {"status": "ok"}


site.register(BridgeOrder, BridgeOrderAdmin)
admin = Admin(
    app,
    engine=engine,
    settings=HyperAdminSettings(create_tables=False, secret_key="e2e-bridge-secret"),
    auth=ExternalAuth(
        get_user=get_current_user,
        display_name=lambda user: user.full_name,
        logout_url="/auth/logout",
    ),
)
admin.mount(path="/admin")
