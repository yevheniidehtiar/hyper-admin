import pytest
from fastapi import FastAPI, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import selectinload
from sqlmodel import SQLModel, select

from hyperadmin.auth.middleware import require_authenticated_user
from hyperadmin.auth.models import Permission, User, UserPermissions


@pytest.fixture
async def engine():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.create_all)
    return engine


@pytest.mark.anyio
async def test_require_authenticated_user_no_session(engine):
    app = FastAPI()
    app.state.admin_prefix = "/admin"
    app.state.admin_engine = engine

    # Mock request
    class MockRequest:
        def __init__(self):
            self.session = {}
            self.app = app

    request = MockRequest()
    with pytest.raises(HTTPException) as excinfo:
        await require_authenticated_user(request)

    assert excinfo.value.status_code == 302
    assert excinfo.value.headers["Location"] == "/admin/login"


@pytest.mark.anyio
async def test_require_authenticated_user_valid_session(engine):
    async with AsyncSession(engine) as session:
        user = User(
            username="testuser", email="test@example.com", first_name="Test", last_name="User"
        )
        session.add(user)
        await session.commit()
        await session.refresh(user)
        user_id = user.id

    app = FastAPI()
    app.state.admin_prefix = "/admin"
    app.state.admin_engine = engine

    class MockRequest:
        def __init__(self):
            self.session = {"user_id": user_id}
            self.app = app
            self.state = type("state", (), {})()

    request = MockRequest()
    result = await require_authenticated_user(request)
    assert result.id == user_id
    assert request.state.user.id == user_id


@pytest.mark.anyio
async def test_user_has_perm(engine):
    async with AsyncSession(engine) as session:
        user = User(
            username="staff",
            email="staff@example.com",
            first_name="Staff",
            last_name="User",
            is_superuser=False,
        )
        perm = Permission(name="Can create user", codename="create_user")
        session.add_all([user, perm])
        await session.commit()
        await session.refresh(user)
        await session.refresh(perm)

        up = UserPermissions(user_id=user.id, permission_id=perm.id)
        session.add(up)
        await session.commit()
        # session.commit() expires attributes, including .id
        # We need to refresh or access it while session is active
        await session.refresh(user)
        user_id = user.id

    async with AsyncSession(engine) as session:
        result = await session.execute(
            select(User)
            .where(User.id == user_id)
            .options(selectinload(User.user_permissions).selectinload(UserPermissions.permission))
        )
        user_with_perms = result.scalar_one()

        assert user_with_perms.has_perm("create_user") is True
        assert user_with_perms.has_perm("delete_user") is False


@pytest.mark.anyio
async def test_superuser_has_all_perms():
    user = User(
        username="admin",
        email="admin@example.com",
        first_name="Admin",
        last_name="User",
        is_superuser=True,
    )
    assert user.has_perm("any_perm") is True
    assert user.has_perm("create_product") is True
