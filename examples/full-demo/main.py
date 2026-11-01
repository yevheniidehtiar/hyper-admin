"""HyperAdmin full-demo: one app exercising every upstream-readiness capability.

Run it (sign in as ``alice`` / ``secret123``)::

    uv run examples/full-demo/main.py

The qualification suite (``poe test:e2e:qualification``) boots this same module.
"""

import os
import tempfile
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

from admins import register_all
from fastapi import FastAPI
from models import upload_storage
from reports import register_reports
from seed import seed
from sqlalchemy.ext.asyncio import create_async_engine
from sqlmodel import SQLModel

from hyperadmin.auth.permissions import ModelPermissionChecker, PermissionSyncService
from hyperadmin.auth.session import SessionAuthBackend
from hyperadmin.core.app import Admin
from hyperadmin.core.settings import HyperAdminSettings
from hyperadmin.realtime import RealtimeSettings

_HERE = Path(__file__).resolve().parent

# The qualification suite gets a throwaway database per server; a manual run keeps its own.
_db_path = (
    os.path.join(tempfile.mkdtemp(prefix="hyperadmin_full_demo_"), "app.db")
    if os.environ.get("E2E_TESTING")
    else str(_HERE / "full_demo.db")
)
engine = create_async_engine(
    f"sqlite+aiosqlite:///{_db_path}", connect_args={"check_same_thread": False}
)

register_all()
register_reports()


def _realtime_settings() -> RealtimeSettings | None:
    """Realtime on by default; ``DEMO_REALTIME=0`` turns it off, ``REDIS_URL`` moves it to Redis.

    Notifications are off globally: only ``OrderAdmin`` and ``ProductAdmin`` opt in.
    """
    if os.environ.get("DEMO_REALTIME", "1") == "0":
        return None
    redis_url = os.environ.get("REDIS_URL")
    return RealtimeSettings(
        notifications=False,
        pubsub_redis_url=redis_url,
        presence_redis_url=redis_url,
        enable_test_endpoints=bool(os.environ.get("E2E_TESTING")),
    )


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
    async with engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.create_all)
    await admin._sync_permissions()
    await seed(engine)
    yield


app = FastAPI(lifespan=lifespan)

admin = Admin(
    app,
    engine=engine,
    settings=HyperAdminSettings(
        create_tables=False,
        secret_key="full-demo-secret",  # noqa: S106
        auto_discover=False,
    ),
    auth_backend=SessionAuthBackend(engine=engine),
    permission_checker=ModelPermissionChecker(engine=engine),
    permission_registry=PermissionSyncService(engine=engine),
    storage=upload_storage,
    realtime=_realtime_settings(),
)
admin.mount(path="/admin")


@app.get("/")
def root() -> dict[str, str]:
    return {"message": "Go to /admin (alice / secret123)."}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="127.0.0.1", port=8000)
