"""HyperAdmin on plain SQLAlchemy 2.0 models.

Run it::

    uv run uvicorn examples.sqlalchemy.main:app    # http://127.0.0.1:8000/admin
"""

from __future__ import annotations

import os
from contextlib import asynccontextmanager
from typing import TYPE_CHECKING

from fastapi import FastAPI
from sqlalchemy.ext.asyncio import create_async_engine

from examples.sqlalchemy import admin as _admin  # noqa: F401  (registers the models)
from examples.sqlalchemy.models import Base
from examples.sqlalchemy.seed import seed
from hyperadmin import Admin
from hyperadmin.core.settings import HyperAdminSettings

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

DB_URL = (
    "sqlite+aiosqlite:///:memory:"
    if os.environ.get("E2E_TESTING")
    else "sqlite+aiosqlite:///sqlalchemy_app.db"
)
engine = create_async_engine(DB_URL, connect_args={"check_same_thread": False})


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    await seed(engine)
    yield


app = FastAPI(lifespan=lifespan)

admin = Admin(
    app,
    engine=engine,
    settings=HyperAdminSettings(create_tables=False, auto_discover=False),
)
admin.mount(path="/admin")


@app.get("/")
def root() -> dict[str, str]:
    return {"message": "Go to /admin/project to see the admin interface."}
