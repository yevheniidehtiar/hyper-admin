"""Tests for permission checking and auto-registration (A4).

TDD: Verify permission generation, sync, checking (direct + group-inherited),
superuser bypass, and custom permissions.
"""

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlmodel import SQLModel, select

from hyperadmin.auth.backend import hash_password
from hyperadmin.auth.models import (
    Group,
    GroupPermission,
    Permission,
    User,
    UserGroup,
    UserPermission,
)


@pytest.fixture
async def async_engine(tmp_path):
    db_file = tmp_path / "test_perms.db"
    engine = create_async_engine(f"sqlite+aiosqlite:///{db_file}")
    async with engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.create_all)
    yield engine
    await engine.dispose()


@pytest.fixture
def checker(async_engine):
    from hyperadmin.auth.permissions import ModelPermissionChecker

    return ModelPermissionChecker(engine=async_engine)


@pytest.fixture
def sync_service(async_engine):
    from hyperadmin.auth.permissions import PermissionSyncService

    return PermissionSyncService(engine=async_engine)


@pytest.fixture
async def superuser(async_engine):
    async with AsyncSession(async_engine) as session:
        user = User(
            username="admin",
            email="admin@example.com",
            password_hash=hash_password("password"),
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
            password_hash=hash_password("password"),
        )
        session.add(user)
        await session.commit()
        await session.refresh(user)
        return user


class TestGenerateDefaultPermissions:
    def test_generate_default_permissions(self):
        from hyperadmin.auth.permissions import generate_default_permissions

        perms = generate_default_permissions("order")
        assert perms == [
            ("view_order", "Can view order"),
            ("add_order", "Can add order"),
            ("change_order", "Can change order"),
            ("delete_order", "Can delete order"),
        ]

    def test_generate_default_permissions_lowercases(self):
        from hyperadmin.auth.permissions import generate_default_permissions

        perms = generate_default_permissions("Order")
        codenames = [p[0] for p in perms]
        assert all(c == c.lower() for c in codenames)


class TestPermissionSyncService:
    @pytest.mark.anyio
    async def test_sync_creates_permissions(self, sync_service, async_engine):
        """sync_permissions creates default permissions for registered models."""

        class FakeModelAdmin:
            permissions: list = []

        models = [("user", FakeModelAdmin)]
        await sync_service.sync_permissions(models)

        async with AsyncSession(async_engine) as session:
            perms = (await session.execute(select(Permission))).scalars().all()
            codenames = {p.codename for p in perms}
            assert codenames == {"view_user", "add_user", "change_user", "delete_user"}

    @pytest.mark.anyio
    async def test_sync_is_idempotent(self, sync_service, async_engine):
        """Running sync twice doesn't duplicate rows."""

        class FakeModelAdmin:
            permissions: list = []

        models = [("user", FakeModelAdmin)]
        await sync_service.sync_permissions(models)
        await sync_service.sync_permissions(models)

        async with AsyncSession(async_engine) as session:
            perms = (await session.execute(select(Permission))).scalars().all()
            assert len(perms) == 4

    @pytest.mark.anyio
    async def test_sync_custom_permissions(self, sync_service, async_engine):
        """Custom permissions from ModelAdmin.permissions are synced."""

        class OrderAdmin:
            permissions = [
                ("export_order", "Can export orders"),
                ("approve_order", "Can approve orders"),
            ]

        models = [("order", OrderAdmin)]
        await sync_service.sync_permissions(models)

        async with AsyncSession(async_engine) as session:
            perms = (await session.execute(select(Permission))).scalars().all()
            codenames = {p.codename for p in perms}
            assert "export_order" in codenames
            assert "approve_order" in codenames
            # Also has 4 default + 2 custom = 6
            assert len(perms) == 6


class TestModelPermissionChecker:
    @pytest.mark.anyio
    async def test_superuser_bypasses_all(self, checker, superuser):
        result = await checker.has_permission(superuser, "anything")
        assert result is True

    @pytest.mark.anyio
    async def test_direct_user_permission_grant(self, checker, regular_user, async_engine):
        async with AsyncSession(async_engine) as session:
            perm = Permission(codename="view_user", name="Can view user")
            session.add(perm)
            await session.commit()
            await session.refresh(perm)

            up = UserPermission(user_id=regular_user.id, permission_id=perm.id)
            session.add(up)
            await session.commit()

        assert await checker.has_permission(regular_user, "view_user") is True

    @pytest.mark.anyio
    async def test_permission_denied(self, checker, regular_user):
        assert await checker.has_permission(regular_user, "view_user") is False

    @pytest.mark.anyio
    async def test_group_inherited_permission(self, checker, regular_user, async_engine):
        async with AsyncSession(async_engine) as session:
            group = Group(name="Editors")
            perm = Permission(codename="change_article", name="Can change article")
            session.add_all([group, perm])
            await session.commit()
            await session.refresh(group)
            await session.refresh(perm)

            session.add(UserGroup(user_id=regular_user.id, group_id=group.id))
            session.add(GroupPermission(group_id=group.id, permission_id=perm.id))
            await session.commit()

        assert await checker.has_permission(regular_user, "change_article") is True

    @pytest.mark.anyio
    async def test_get_user_permissions_combined(self, checker, regular_user, async_engine):
        """get_user_permissions returns union of direct + group-inherited."""
        async with AsyncSession(async_engine) as session:
            p1 = Permission(codename="view_user", name="Can view user")
            p2 = Permission(codename="add_user", name="Can add user")
            group = Group(name="Writers")
            session.add_all([p1, p2, group])
            await session.commit()
            await session.refresh(p1)
            await session.refresh(p2)
            await session.refresh(group)

            # Direct grant
            session.add(UserPermission(user_id=regular_user.id, permission_id=p1.id))
            # Group grant
            session.add(UserGroup(user_id=regular_user.id, group_id=group.id))
            session.add(GroupPermission(group_id=group.id, permission_id=p2.id))
            await session.commit()

        perms = await checker.get_user_permissions(regular_user)
        assert perms == {"view_user", "add_user"}

    @pytest.mark.anyio
    async def test_satisfies_protocols(self, checker):
        from hyperadmin.core.auth import PermissionChecker

        assert isinstance(checker, PermissionChecker)

    @pytest.mark.anyio
    async def test_sync_service_satisfies_protocol(self, sync_service):
        from hyperadmin.core.auth import PermissionRegistry

        assert isinstance(sync_service, PermissionRegistry)
