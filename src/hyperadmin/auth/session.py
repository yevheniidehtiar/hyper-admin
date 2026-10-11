"""Session-based authentication service.

Implements ``AuthBackend`` and ``CurrentUserProvider`` protocols using
Starlette's ``SessionMiddleware``-backed cookie sessions.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from sqlmodel import select

from hyperadmin.auth.backend import verify_password
from hyperadmin.auth.models import User
from hyperadmin.core.adapters import open_session, require_engine_or_session_factory

if TYPE_CHECKING:
    from contextlib import AbstractAsyncContextManager

    from sqlalchemy.ext.asyncio import AsyncEngine

    from hyperadmin.core.adapters import AsyncSessionLike, SessionFactory


class SessionAuthBackend:
    """Cookie-session authentication backed by an async engine or session factory."""

    def __init__(
        self, engine: AsyncEngine | None = None, *, session_factory: SessionFactory | None = None
    ) -> None:
        require_engine_or_session_factory("SessionAuthBackend", engine, session_factory)
        self.engine = engine
        self.session_factory = session_factory

    def _session(self) -> AbstractAsyncContextManager[AsyncSessionLike]:
        """Open a session from whichever of ``engine`` / ``session_factory`` was given."""
        return open_session(self.engine, self.session_factory)

    async def authenticate(self, username: str, password: str) -> User | None:
        """Return the user if credentials are valid, else ``None``."""
        async with self._session() as session:
            stmt = select(User).where(User.username == username)
            user = (await session.execute(stmt)).scalar_one_or_none()
            if user is None:
                return None
            if not user.is_active:
                return None
            if not verify_password(password, user.password_hash):
                return None
            return user

    async def login(self, request: Any, user: User) -> None:
        """Store the user ID in the session."""
        request.session["user_id"] = user.id

    async def logout(self, request: Any) -> None:
        """Clear the session."""
        request.session.pop("user_id", None)

    async def get_current_user(self, request: Any) -> User | None:
        """Resolve the current user from the session, or ``None``."""
        user_id = request.session.get("user_id")
        if user_id is None:
            return None
        async with self._session() as session:
            stmt = select(User).where(User.id == user_id)
            return (await session.execute(stmt)).scalar_one_or_none()
