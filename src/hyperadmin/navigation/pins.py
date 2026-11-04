"""Per-user pinned sidebar pages: the ``hyperadmin_nav_pin`` table and its service.

A pin is a user's bookmark on a sidebar item (``docs/specs/navigation-and-list-ux.md``,
story st-v059-nav-03). Rows are keyed by ``request.state.user_key`` (what both
auth modes set) and by the item's pin key, ``NavItem.key``: a model slug
(``"order"``) or ``"plugin:<url_name>"``. ``(user_key, target)`` is unique in
the database as well as in the service, so a double click is not an error.

The table joins the ``hyperadmin_*`` metadata when this module is imported, so
``hyperadmin init-db`` creates it and Alembic hosts pick it up through
``hyperadmin.auth.metadata()``; the hand-written operation is in
``docs/guides/existing-app.md`` section 5.
"""

from __future__ import annotations

from datetime import datetime  # noqa: TC003 - SQLModel resolves the column annotation at runtime
from typing import TYPE_CHECKING, Any

from sqlalchemy import UniqueConstraint, delete, func
from sqlalchemy.exc import IntegrityError
from sqlmodel import Field, SQLModel, col, select

from hyperadmin.auth._types import UTCNaiveDateTime
from hyperadmin.core.adapters import open_session, require_engine_or_session_factory
from hyperadmin.core.timezones import utc_now

if TYPE_CHECKING:
    from collections.abc import Collection
    from contextlib import AbstractAsyncContextManager

    from hyperadmin.core.adapters import AsyncSessionLike, SessionFactory

__all__ = ["DEFAULT_MAX_PINS", "NavPin", "NavPinService", "PinLimitError"]

#: Default of ``HyperAdminSettings.nav_pins_max``.
DEFAULT_MAX_PINS = 20


class NavPin(SQLModel, table=True):
    """One sidebar item one user pinned."""

    __tablename__ = "hyperadmin_nav_pin"  # type: ignore[reportIncompatibleVariableOverride]
    __table_args__ = (UniqueConstraint("user_key", "target", name="uq_hyperadmin_nav_pin"),)

    id: int | None = Field(default=None, primary_key=True)
    #: ``request.state.user_key`` of the owner (``str`` so host user ids fit).
    user_key: str = Field(index=True, max_length=255)
    #: The pinned item's ``NavItem.key``.
    target: str = Field(max_length=255)
    created_at: datetime = Field(default_factory=utc_now, sa_type=UTCNaiveDateTime)


class PinLimitError(Exception):
    """The user already has ``limit`` pins."""

    def __init__(self, limit: int) -> None:
        super().__init__(f"You can pin up to {limit} pages")
        self.limit = limit


class NavPinService:
    """Lists, adds and removes one user's pins; at most ``max_pins`` per user.

    Every method takes the ``user_key`` explicitly, so a pin is only ever read or
    changed by its owner. ``pin`` and ``unpin`` accept ``known``, the pin keys
    that still exist in the nav tree: the user's other pins outside it (a model
    unregistered, a plugin disabled) are deleted on the way.
    """

    def __init__(
        self,
        engine: Any = None,
        *,
        session_factory: SessionFactory | None = None,
        max_pins: int = DEFAULT_MAX_PINS,
    ) -> None:
        require_engine_or_session_factory("NavPinService", engine, session_factory)
        self.engine = engine
        self.session_factory = session_factory
        self.max_pins = max_pins

    def _session(self) -> AbstractAsyncContextManager[AsyncSessionLike]:
        return open_session(self.engine, self.session_factory)

    async def list_for(self, user_key: Any) -> list[str]:
        """The user's pin keys, oldest first."""
        stmt = (
            select(NavPin.target)
            .where(NavPin.user_key == str(user_key))
            .order_by(NavPin.created_at, NavPin.id)  # type: ignore[arg-type]
        )
        async with self._session() as session:
            return [str(target) for target in (await session.execute(stmt)).scalars().all()]

    async def pin(
        self, user_key: Any, target: str, *, known: Collection[str] | None = None
    ) -> bool:
        """Pin ``target`` for the user; ``False`` when it was already pinned.

        Raises:
            PinLimitError: When the user already has ``max_pins`` pins.
        """
        owner = str(user_key)
        async with self._session() as session:
            await self._prune(session, owner, known)
            if await self._is_pinned(session, owner, target):
                await session.commit()
                return False
            count = await session.execute(
                select(func.count()).select_from(NavPin).where(NavPin.user_key == owner)
            )
            if count.scalar_one() >= self.max_pins:
                await session.commit()
                raise PinLimitError(self.max_pins)
            session.add(NavPin(user_key=owner, target=target))
            try:
                await session.commit()
            except IntegrityError:
                # A second click raced past the check above: the unique
                # constraint is the authority, and the pin exists.
                return False
        return True

    async def unpin(
        self, user_key: Any, target: str, *, known: Collection[str] | None = None
    ) -> bool:
        """Remove the user's pin on ``target``; ``False`` when there was none."""
        owner = str(user_key)
        async with self._session() as session:
            await self._prune(session, owner, known)
            result = await session.execute(
                delete(NavPin).where(col(NavPin.user_key) == owner, col(NavPin.target) == target)
            )
            await session.commit()
        return bool(getattr(result, "rowcount", 0))

    @staticmethod
    async def _is_pinned(session: AsyncSessionLike, owner: str, target: str) -> bool:
        found = await session.execute(
            select(NavPin.id).where(NavPin.user_key == owner, NavPin.target == target)
        )
        return found.scalar_one_or_none() is not None

    @staticmethod
    async def _prune(session: AsyncSessionLike, owner: str, known: Collection[str] | None) -> None:
        if known is None:
            return
        await session.execute(
            delete(NavPin).where(
                col(NavPin.user_key) == owner, col(NavPin.target).not_in(list(known))
            )
        )
