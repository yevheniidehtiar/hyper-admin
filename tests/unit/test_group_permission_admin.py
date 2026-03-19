import pytest
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlmodel import SQLModel, select

from examples.rbac_app.models import Group, Permission, User, UserGroup


@pytest.fixture
async def engine():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.create_all)
    yield engine
    async with engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.drop_all)


@pytest.mark.anyio
async def test_group_creation_retrieval(engine):
    """Test that Groups can be created and retrieved."""
    async with AsyncSession(engine) as session:
        group = Group(name="Admins", description="Full access")
        session.add(group)
        await session.commit()
        await session.refresh(group)
        group_id = group.id
        group_name = group.name

    async with AsyncSession(engine) as session:
        statement = select(Group).where(Group.id == group_id)
        result = await session.execute(statement)
        retrieved_group = result.scalar_one()
        assert retrieved_group.name == group_name
        assert retrieved_group.description == "Full access"


@pytest.mark.anyio
async def test_permission_creation_retrieval(engine):
    """Test that Permissions can be created and retrieved."""
    async with AsyncSession(engine) as session:
        permission = Permission(name="Can Edit", codename="can_edit", content_type="post")
        session.add(permission)
        await session.commit()
        await session.refresh(permission)
        permission_id = permission.id
        permission_name = permission.name

    async with AsyncSession(engine) as session:
        statement = select(Permission).where(Permission.id == permission_id)
        result = await session.execute(statement)
        retrieved_permission = result.scalar_one()
        assert retrieved_permission.name == permission_name
        assert retrieved_permission.codename == "can_edit"


@pytest.mark.anyio
async def test_user_group_assignment(engine):
    """Test that UserGroup assignment can be created (user-group many-to-many)."""
    async with AsyncSession(engine) as session:
        user = User(
            username="testuser",
            email="test@example.com",
            first_name="Test",
            last_name="User",
        )
        group = Group(name="Editors", description="Limited access")
        session.add(user)
        session.add(group)
        await session.commit()
        await session.refresh(user)
        await session.refresh(group)
        user_id = user.id
        group_id = group.id

        user_group = UserGroup(user_id=user_id, group_id=group_id)
        session.add(user_group)
        await session.commit()
        await session.refresh(user_group)
        user_group_id = user_group.id

    async with AsyncSession(engine) as session:
        statement = select(UserGroup).where(UserGroup.id == user_group_id)
        result = await session.execute(statement)
        retrieved_ug = result.scalar_one()
        assert retrieved_ug.user_id == user_id
        assert retrieved_ug.group_id == group_id
