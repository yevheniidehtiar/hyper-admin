"""Tests for session-based auth service (A3).

TDD: Verify authenticate, login, logout, get_current_user.
"""

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlmodel import SQLModel

from hyperadmin.auth.backend import hash_password
from hyperadmin.auth.models import User


@pytest.fixture
async def async_engine(tmp_path):
    db_file = tmp_path / "test_session.db"
    engine = create_async_engine(f"sqlite+aiosqlite:///{db_file}")
    async with engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.create_all)
    yield engine
    await engine.dispose()


@pytest.fixture
async def seed_user(async_engine):
    """Create a test user in the database."""
    async with AsyncSession(async_engine) as session:
        user = User(
            username="testuser",
            email="test@example.com",
            password_hash=hash_password("correctpassword"),
            is_active=True,
        )
        session.add(user)
        await session.commit()
        await session.refresh(user)
        return user


@pytest.fixture
def backend(async_engine):
    from hyperadmin.auth.session import SessionAuthBackend

    return SessionAuthBackend(engine=async_engine)


class FakeRequest:
    """Minimal request mock with session dict."""

    def __init__(self, session_data: dict | None = None):
        self.session: dict = session_data or {}


class TestSessionAuthBackend:
    @pytest.mark.anyio
    async def test_authenticate_success(self, backend, seed_user):
        user = await backend.authenticate("testuser", "correctpassword")
        assert user is not None
        assert user.username == "testuser"

    @pytest.mark.anyio
    async def test_authenticate_wrong_password(self, backend, seed_user):
        user = await backend.authenticate("testuser", "wrongpassword")
        assert user is None

    @pytest.mark.anyio
    async def test_authenticate_nonexistent_user(self, backend, seed_user):
        user = await backend.authenticate("nouser", "anything")
        assert user is None

    @pytest.mark.anyio
    async def test_authenticate_inactive_user(self, async_engine):
        from hyperadmin.auth.session import SessionAuthBackend

        async with AsyncSession(async_engine) as session:
            user = User(
                username="inactive",
                email="inactive@example.com",
                password_hash=hash_password("password123"),
                is_active=False,
            )
            session.add(user)
            await session.commit()

        backend = SessionAuthBackend(engine=async_engine)
        result = await backend.authenticate("inactive", "password123")
        assert result is None

    @pytest.mark.anyio
    async def test_login_sets_session(self, backend, seed_user):
        request = FakeRequest()
        await backend.login(request, seed_user)
        assert request.session["user_id"] == seed_user.id

    @pytest.mark.anyio
    async def test_logout_clears_session(self, backend, seed_user):
        request = FakeRequest({"user_id": seed_user.id})
        await backend.logout(request)
        assert "user_id" not in request.session

    @pytest.mark.anyio
    async def test_get_current_user_valid(self, backend, seed_user):
        request = FakeRequest({"user_id": seed_user.id})
        user = await backend.get_current_user(request)
        assert user is not None
        assert user.username == "testuser"

    @pytest.mark.anyio
    async def test_get_current_user_no_session(self, backend):
        request = FakeRequest()
        user = await backend.get_current_user(request)
        assert user is None

    @pytest.mark.anyio
    async def test_get_current_user_invalid_id(self, backend, seed_user):
        request = FakeRequest({"user_id": 99999})
        user = await backend.get_current_user(request)
        assert user is None

    @pytest.mark.anyio
    async def test_satisfies_auth_backend_protocol(self, backend):
        from hyperadmin.core.auth import AuthBackend, CurrentUserProvider

        assert isinstance(backend, AuthBackend)
        assert isinstance(backend, CurrentUserProvider)

    @pytest.mark.anyio
    async def test_no_views_import(self):
        """session.py must not import from views/."""
        import ast
        from pathlib import Path

        source = Path("src/hyperadmin/auth/session.py").read_text()
        tree = ast.parse(source)
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.module:
                assert not node.module.startswith("hyperadmin.views"), (
                    f"Forbidden import: {node.module}"
                )
