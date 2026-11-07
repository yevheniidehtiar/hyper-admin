"""Query-count tests for the per-request user load (st-perf-01)."""

from types import SimpleNamespace

import pytest
from sqlalchemy import event
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlmodel import SQLModel

from hyperadmin.auth.backend import hash_password
from hyperadmin.auth.models import (
    Group,
    GroupPermission,
    Permission,
    User,
    UserGroup,
)
from hyperadmin.auth.permissions import ModelPermissionChecker
from hyperadmin.auth.session import SessionAuthBackend

pytestmark = pytest.mark.anyio


@pytest.fixture
async def engine(tmp_path):
    eng = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'qc.db'}")
    async with eng.begin() as conn:
        await conn.run_sync(SQLModel.metadata.create_all)
    yield eng
    await eng.dispose()


def _count_statements(engine) -> list[str]:
    statements: list[str] = []

    @event.listens_for(engine.sync_engine, "before_cursor_execute")
    def _record(conn, cursor, statement, parameters, context, executemany):
        statements.append(statement)

    return statements


def _request(user_id: int | None) -> SimpleNamespace:
    return SimpleNamespace(session={"user_id": user_id})


async def test_superuser_request_loads_user_once(engine) -> None:
    """
    Scenario: a superuser's request loads the user once
      Given a signed-in superuser
      When  the auth step resolves the current user
      Then  it runs 1 SQL statement
    """
    # Given
    async with AsyncSession(engine) as session:
        user = User(
            username="root",
            email="root@example.com",
            password_hash=hash_password("pw"),
            is_superuser=True,
        )
        session.add(user)
        await session.commit()
        await session.refresh(user)
        user_id = user.id
    statements = _count_statements(engine)

    # When
    loaded = await SessionAuthBackend(engine).get_current_user(_request(user_id))

    # Then
    assert loaded is not None
    assert loaded.username == "root"
    assert len(statements) == 1


async def test_staff_user_permissions_still_resolve(engine) -> None:
    """
    Scenario: a staff user's permissions still resolve
      Given a staff user with a group permission
      When  the user is loaded by the auth step and permissions are checked
      Then  the group permission is honoured
    """
    # Given
    async with AsyncSession(engine) as session:
        user = User(username="staff", email="s@example.com", password_hash=hash_password("pw"))
        group = Group(name="editors")
        perm = Permission(codename="view_invoice", name="View invoice")
        session.add_all([user, group, perm])
        await session.commit()
        await session.refresh(user)
        await session.refresh(group)
        await session.refresh(perm)
        user_id, group_id, perm_id = user.id, group.id, perm.id
        assert user_id is not None
        assert group_id is not None
        assert perm_id is not None
        session.add_all(
            [
                UserGroup(user_id=user_id, group_id=group_id),
                GroupPermission(group_id=group_id, permission_id=perm_id),
            ]
        )
        await session.commit()

    # When
    loaded = await SessionAuthBackend(engine).get_current_user(_request(user_id))
    checker = ModelPermissionChecker(engine)

    # Then
    assert loaded is not None
    assert await checker.has_permission(loaded, "view_invoice") is True
    assert await checker.has_permission(loaded, "delete_invoice") is False
