"""Auth-enabled HyperAdmin app with the test-only demo plugin, for E2E testing.

Started by the ``plugin_base_url`` fixture via uvicorn subprocess. Seeds a
superuser ``alice / secret123`` and a user ``bob / secret123`` without the
plugin's ``view_demo_report`` permission. The demo plugin is registered by
hand (it has no installed entry point); the workspace's ``reports`` plugin is
discovered as usual.
"""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlmodel import SQLModel, select

from hyperadmin.auth.backend import hash_password
from hyperadmin.auth.models import User
from hyperadmin.auth.permissions import ModelPermissionChecker, PermissionSyncService
from hyperadmin.auth.session import SessionAuthBackend
from hyperadmin.core.app import Admin
from hyperadmin.core.settings import HyperAdminSettings
from tests.demo_plugin import DemoPlugin

engine = create_async_engine(
    "sqlite+aiosqlite:///:memory:",
    connect_args={"check_same_thread": False},
)


async def _seed_users() -> None:
    async with AsyncSession(engine) as session:
        for username, superuser in (("alice", True), ("bob", False)):
            result = await session.execute(select(User).where(User.username == username))
            if not result.scalar_one_or_none():
                session.add(
                    User(
                        username=username,
                        email=f"{username}@example.com",
                        password_hash=hash_password("secret123"),
                        is_superuser=superuser,
                    )
                )
        await session.commit()


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
    async with engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.create_all)
    await _seed_users()
    yield


app = FastAPI(lifespan=lifespan)

admin = Admin(
    app,
    engine=engine,
    settings=HyperAdminSettings(create_tables=False, secret_key="e2e-test-secret"),
    auth_backend=SessionAuthBackend(engine=engine),
    permission_checker=ModelPermissionChecker(engine=engine),
    permission_registry=PermissionSyncService(engine=engine),
)
admin.plugins.register(DemoPlugin(), admin=admin)
admin.mount(path="/admin")
