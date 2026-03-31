"""Tests for authorization checks in CRUD views (A7).

TDD: Verify permission gates on list/create/update/delete views,
superuser bypass, and backward compat with auth_backend=None.
"""

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlmodel import Field, SQLModel

from hyperadmin.auth.backend import hash_password
from hyperadmin.auth.models import Permission, User, UserPermission


@pytest.fixture
async def async_engine(tmp_path):
    db_file = tmp_path / "test_authz.db"
    engine = create_async_engine(f"sqlite+aiosqlite:///{db_file}")
    async with engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.create_all)
    yield engine
    await engine.dispose()


class Article(SQLModel, table=True):
    __tablename__ = "hyperadmin_test_articles"  # type: ignore[reportIncompatibleVariableOverride]
    id: int | None = Field(default=None, primary_key=True)
    title: str = Field(max_length=200)


@pytest.fixture
async def superuser(async_engine):
    async with AsyncSession(async_engine) as session:
        user = User(
            username="superadmin",
            email="super@example.com",
            password_hash=hash_password("password123"),
            is_superuser=True,
        )
        session.add(user)
        await session.commit()
        await session.refresh(user)
        return user


@pytest.fixture
async def regular_user(async_engine):
    async with AsyncSession(async_engine) as session:
        user = User(
            username="regular",
            email="regular@example.com",
            password_hash=hash_password("password123"),
        )
        session.add(user)
        await session.commit()
        await session.refresh(user)
        return user


@pytest.fixture
async def user_with_view_perm(async_engine):
    async with AsyncSession(async_engine) as session:
        user = User(
            username="viewer",
            email="viewer@example.com",
            password_hash=hash_password("password123"),
        )
        perm = Permission(codename="view_article", name="Can view article")
        session.add_all([user, perm])
        await session.commit()
        await session.refresh(user)
        await session.refresh(perm)

        session.add(UserPermission(user_id=user.id, permission_id=perm.id))
        await session.commit()
        return user


def _build_app(async_engine, with_auth: bool = True):
    """Build a FastAPI app with Article registered, optionally with auth."""
    from fastapi import FastAPI

    from hyperadmin.auth.permissions import ModelPermissionChecker, PermissionSyncService
    from hyperadmin.auth.session import SessionAuthBackend
    from hyperadmin.core.app import Admin
    from hyperadmin.core.registry import site
    from hyperadmin.core.settings import HyperAdminSettings

    # Clear registry to avoid conflicts
    site._registry.clear()

    app = FastAPI()

    if with_auth:
        backend = SessionAuthBackend(engine=async_engine)
        admin = Admin(
            app,
            engine=async_engine,
            settings=HyperAdminSettings(create_tables=False, secret_key="test-secret"),
            auth_backend=backend,
            permission_checker=ModelPermissionChecker(engine=async_engine),
            permission_registry=PermissionSyncService(engine=async_engine),
        )
    else:
        admin = Admin(app, engine=async_engine, settings=HyperAdminSettings(create_tables=False))

    from hyperadmin.core.model import ModelAdmin

    site.register(Article, admin_class=ModelAdmin)
    admin.mount("/admin")
    return app


async def _login(client: AsyncClient, username: str, password: str = "password123"):  # noqa: S107
    """Helper to login and get authenticated session."""
    await client.post("/admin/login", data={"username": username, "password": password})


class TestSuperuserAccess:
    @pytest.mark.anyio
    async def test_superuser_can_list(self, async_engine, superuser):
        app = _build_app(async_engine)
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            await _login(client, "superadmin")
            resp = await client.get("/admin/article", follow_redirects=False)
            assert resp.status_code == 200

    @pytest.mark.anyio
    async def test_superuser_can_access_create_form(self, async_engine, superuser):
        app = _build_app(async_engine)
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            await _login(client, "superadmin")
            resp = await client.get("/admin/article/create", follow_redirects=False)
            assert resp.status_code == 200


class TestPermissionDenied:
    @pytest.mark.anyio
    async def test_user_without_view_perm_gets_403(self, async_engine, regular_user):
        app = _build_app(async_engine)
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            await _login(client, "regular")
            resp = await client.get("/admin/article", follow_redirects=False)
            assert resp.status_code == 403

    @pytest.mark.anyio
    async def test_user_with_view_but_not_change_gets_403_on_edit(
        self, async_engine, user_with_view_perm
    ):
        app = _build_app(async_engine)

        # Create an article first
        async with AsyncSession(async_engine) as session:
            article = Article(title="Test Article")
            session.add(article)
            await session.commit()
            await session.refresh(article)

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            await _login(client, "viewer")
            resp = await client.get(f"/admin/article/{article.id}/edit", follow_redirects=False)
            assert resp.status_code == 403

    @pytest.mark.anyio
    async def test_user_with_view_can_list(self, async_engine, user_with_view_perm):
        app = _build_app(async_engine)
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            await _login(client, "viewer")
            resp = await client.get("/admin/article", follow_redirects=False)
            assert resp.status_code == 200


class TestBackwardCompat:
    @pytest.mark.anyio
    async def test_no_auth_all_views_accessible(self, async_engine):
        """auth_backend=None → all views accessible without permissions."""
        app = _build_app(async_engine, with_auth=False)
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.get("/admin/article")
            assert resp.status_code == 200

            resp = await client.get("/admin/article/create")
            assert resp.status_code == 200
