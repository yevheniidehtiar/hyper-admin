"""Minimal auth-enabled HyperAdmin app for E2E testing.

Started by the ``auth_base_url`` fixture via uvicorn subprocess.
Seeds a superuser ``alice / secret123`` on startup.
"""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlmodel import SQLModel, select

from hyperadmin.auth.backend import hash_password
from hyperadmin.auth.models import User
from hyperadmin.auth.permissions import (
    ModelPermissionChecker,
    PermissionSyncService,
)
from hyperadmin.auth.session import SessionAuthBackend
from hyperadmin.core.app import Admin

engine = create_async_engine(
    "sqlite+aiosqlite:///:memory:",
    connect_args={"check_same_thread": False},
)


async def _seed_superuser() -> None:
    """Create the test superuser if it doesn't exist."""
    async with AsyncSession(engine) as session:
        result = await session.execute(select(User).where(User.username == "alice"))
        if not result.scalar_one_or_none():
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
    async with engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.create_all)
    await _seed_superuser()
    yield


app = FastAPI(lifespan=lifespan)

backend = SessionAuthBackend(engine=engine)
admin = Admin(
    app,
    engine=engine,
    create_tables=False,
    auth_backend=backend,
    permission_checker=ModelPermissionChecker(engine=engine),
    permission_registry=PermissionSyncService(engine=engine),
    session_secret="e2e-test-secret",
)
admin.mount(path="/admin")
