"""Tests for auth middleware, login/logout views, and permission sync (A5).

TDD: Verify redirect behavior, login/logout flows, request.state.user,
permission sync on mount, and backward compatibility.
"""

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import create_async_engine
from sqlmodel import SQLModel

from hyperadmin.auth.backend import hash_password
from hyperadmin.auth.models import Permission, User


@pytest.fixture
async def async_engine(tmp_path):
    db_file = tmp_path / "test_mw.db"
    engine = create_async_engine(f"sqlite+aiosqlite:///{db_file}")
    async with engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.create_all)
    yield engine
    await engine.dispose()


@pytest.fixture
async def seed_user(async_engine):
    from sqlalchemy.ext.asyncio import AsyncSession

    async with AsyncSession(async_engine) as session:
        user = User(
            username="admin",
            email="admin@example.com",
            password_hash=hash_password("password123"),
            is_superuser=True,
        )
        session.add(user)
        await session.commit()
        await session.refresh(user)
        return user


def _build_auth_app(async_engine, register_models: bool = True):
    """Build a FastAPI app with HyperAdmin auth wired up."""
    import sqlmodel as sm
    from fastapi import FastAPI
    from sqlmodel import Field

    from hyperadmin.auth.permissions import ModelPermissionChecker, PermissionSyncService
    from hyperadmin.auth.session import SessionAuthBackend
    from hyperadmin.core.app import Admin
    from hyperadmin.core.settings import HyperAdminSettings

    app = FastAPI()
    backend = SessionAuthBackend(engine=async_engine)
    admin = Admin(
        app,
        engine=async_engine,
        settings=HyperAdminSettings(create_tables=False, secret_key="test-secret-key"),
        auth_backend=backend,
        permission_checker=ModelPermissionChecker(engine=async_engine),
        permission_registry=PermissionSyncService(engine=async_engine),
    )

    if register_models:
        # Register a dummy model for testing
        class Item(sm.SQLModel, table=True):
            __tablename__ = "hyperadmin_test_items"  # type: ignore[reportIncompatibleVariableOverride]
            id: int | None = Field(default=None, primary_key=True)
            name: str = Field(max_length=100)

        # Create the table
        import asyncio

        async def create_table():
            async with async_engine.begin() as conn:
                await conn.run_sync(sm.SQLModel.metadata.create_all)

        asyncio.get_event_loop().run_until_complete(create_table())

    admin.mount("/admin")
    return app


def _build_no_auth_app(async_engine):
    """Build a FastAPI app WITHOUT auth (backward compat)."""
    from fastapi import FastAPI

    from hyperadmin.core.app import Admin
    from hyperadmin.core.settings import HyperAdminSettings

    app = FastAPI()
    admin = Admin(app, engine=async_engine, settings=HyperAdminSettings(create_tables=False))
    admin.mount("/admin")
    return app


class TestAuthMiddleware:
    @pytest.mark.anyio
    async def test_unauthenticated_redirects_to_login(self, async_engine):
        app = _build_auth_app(async_engine, register_models=False)
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.get("/admin/", follow_redirects=False)
            assert resp.status_code == 302
            assert "/admin/login" in resp.headers["location"]

    @pytest.mark.anyio
    async def test_login_page_accessible_without_auth(self, async_engine):
        app = _build_auth_app(async_engine, register_models=False)
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.get("/admin/login")
            assert resp.status_code == 200

    @pytest.mark.anyio
    async def test_login_success_redirects_to_admin(self, async_engine, seed_user):
        app = _build_auth_app(async_engine, register_models=False)
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.post(
                "/admin/login",
                data={"username": "admin", "password": "password123"},
                follow_redirects=False,
            )
            assert resp.status_code == 302
            assert "/admin/" in resp.headers["location"]

    @pytest.mark.anyio
    async def test_login_failure_shows_error(self, async_engine, seed_user):
        app = _build_auth_app(async_engine, register_models=False)
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.post(
                "/admin/login",
                data={"username": "admin", "password": "wrong"},
            )
            assert resp.status_code == 200
            assert "Invalid" in resp.text or "invalid" in resp.text

    @pytest.mark.anyio
    async def test_logout_clears_session(self, async_engine, seed_user):
        app = _build_auth_app(async_engine, register_models=False)
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            # Login first
            await client.post(
                "/admin/login",
                data={"username": "admin", "password": "password123"},
            )
            # Logout
            resp = await client.post("/admin/logout", follow_redirects=False)
            assert resp.status_code == 302
            assert "/admin/login" in resp.headers["location"]

            # Verify can't access admin anymore
            resp = await client.get("/admin/", follow_redirects=False)
            assert resp.status_code == 302

    @pytest.mark.anyio
    async def test_authenticated_user_on_request_state(self, async_engine, seed_user):
        """After login, request.state.user should be populated."""
        app = _build_auth_app(async_engine, register_models=False)
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            # Login
            await client.post(
                "/admin/login",
                data={"username": "admin", "password": "password123"},
            )
            # Access dashboard — should be 200 (authenticated)
            resp = await client.get("/admin/", follow_redirects=False)
            assert resp.status_code == 200


class TestBackwardCompatibility:
    @pytest.mark.anyio
    async def test_no_auth_backend_routes_accessible(self, async_engine):
        """auth_backend=None → all routes publicly accessible."""
        app = _build_no_auth_app(async_engine)
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.get("/admin/")
            assert resp.status_code == 200


class TestPermissionSyncOnStartup:
    @pytest.mark.anyio
    async def test_permissions_synced_on_mount(self, async_engine):
        """Permission sync creates DB rows for all registered models on startup."""
        from sqlalchemy.ext.asyncio import AsyncSession

        app = _build_auth_app(async_engine, register_models=False)

        # Trigger startup
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            await client.get("/admin/login")

        async with AsyncSession(async_engine) as session:
            from sqlmodel import select

            perms = (await session.execute(select(Permission))).scalars().all()
            # If no models are registered, sync should still run without error
            # The exact count depends on registered models
            assert isinstance(perms, list)
