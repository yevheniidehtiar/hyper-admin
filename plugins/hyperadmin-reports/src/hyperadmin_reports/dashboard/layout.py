"""Per-user dashboard order: the ``hyperadmin_reports_dashboard_layout`` table and its store.

The table belongs to this plugin. It is declared with SQLAlchemy Core on a
``MetaData`` of its own, never on ``SQLModel.metadata`` or the core's
``hyperadmin_*`` metadata, so a host's Alembic autogenerate does not see it
unless the host adds :func:`dashboard_metadata` on purpose. Hosts opt in with
:func:`create_layout_table` or the hand-written Alembic operation in the plugin
README; without the table the dashboard keeps the default order.

One row per ``(user_key, dashboard)`` holds the ordered widget keys. Widget
configuration stays in code (SDD ``docs/specs/dashboard-builder.md``).
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from sqlalchemy import (
    JSON,
    Column,
    DateTime,
    Integer,
    MetaData,
    String,
    Table,
    UniqueConstraint,
    delete,
    insert,
    select,
    update,
)
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncEngine

from hyperadmin.core.adapters import open_session, require_engine_or_session_factory
from hyperadmin.core.timezones import utc_now

if TYPE_CHECKING:
    from collections.abc import Sequence
    from contextlib import AbstractAsyncContextManager
    from datetime import datetime

    from sqlalchemy.ext.asyncio import AsyncConnection

    from hyperadmin.core.adapters import AsyncSessionLike, SessionFactory

#: Name of the layout table (also what the "table missing" warning names).
LAYOUT_TABLE_NAME = "hyperadmin_reports_dashboard_layout"
#: The only dashboard there is today; the column lets a second one come without a migration.
DEFAULT_DASHBOARD = "home"

_metadata = MetaData()

layout_table = Table(
    LAYOUT_TABLE_NAME,
    _metadata,
    Column("id", Integer, primary_key=True),
    # ``request.state.user_key`` of the owner, as ``str`` so host user ids fit.
    Column("user_key", String(255), nullable=False, index=True),
    Column("dashboard", String(64), nullable=False, default=DEFAULT_DASHBOARD),
    # The ordered list of widget keys.
    Column("widgets", JSON, nullable=False),
    # Naive UTC.
    Column("updated_at", DateTime, nullable=False),
    UniqueConstraint("user_key", "dashboard", name="uq_hyperadmin_reports_dashboard_layout"),
)


class LayoutUnavailableError(Exception):
    """The layout table cannot be used (it is usually missing: the host did not create it)."""

    def __init__(self) -> None:
        super().__init__(f"the {LAYOUT_TABLE_NAME} table is not available")


def dashboard_metadata() -> MetaData:
    """The plugin-owned ``MetaData`` holding the layout table (for Alembic ``target_metadata``)."""
    return _metadata


async def create_layout_table(bind: AsyncEngine | AsyncConnection) -> None:
    """Create the layout table (and nothing else) if it does not exist.

    A one-off helper for hosts that do not use Alembic; ``bind`` is the host's
    async engine or an open async connection.
    """
    if isinstance(bind, AsyncEngine):
        async with bind.begin() as connection:
            await connection.run_sync(layout_table.create, checkfirst=True)
        return
    await bind.run_sync(layout_table.create, checkfirst=True)


def _now() -> datetime:
    return utc_now().replace(tzinfo=None)


class LayoutStore:
    """Loads, saves and resets one user's widget order.

    Every method takes the ``user_key`` explicitly and stores it as
    ``str(user_key)``, so a layout is only ever read or changed by its owner.
    A database error (in practice: the table is missing) is raised as
    :class:`LayoutUnavailableError`.
    """

    def __init__(
        self, engine: Any = None, *, session_factory: SessionFactory | None = None
    ) -> None:
        require_engine_or_session_factory("LayoutStore", engine, session_factory)
        self.engine = engine
        self.session_factory = session_factory

    def _session(self) -> AbstractAsyncContextManager[AsyncSessionLike]:
        return open_session(self.engine, self.session_factory)

    async def load(self, user_key: Any, dashboard: str = DEFAULT_DASHBOARD) -> list[str] | None:
        """The user's saved widget keys in order, or ``None`` without a saved row."""
        stmt = select(layout_table.c.widgets).where(*_owned(user_key, dashboard))
        try:
            async with self._session() as session:
                widgets = (await session.execute(stmt)).scalar_one_or_none()
        except SQLAlchemyError as exc:
            raise LayoutUnavailableError from exc
        return None if widgets is None else [str(key) for key in widgets]

    async def save(
        self, user_key: Any, keys: Sequence[str], dashboard: str = DEFAULT_DASHBOARD
    ) -> None:
        """Store ``keys`` as the user's order (update, else insert; the last writer wins)."""
        widgets = [str(key) for key in keys]
        try:
            if await self._update(user_key, dashboard, widgets):
                return
            try:
                await self._insert(user_key, dashboard, widgets)
            except IntegrityError:
                # Another request of the same user inserted the row between the
                # update above and this insert: the unique constraint is the
                # authority, so this save becomes an update.
                await self._update(user_key, dashboard, widgets)
        except SQLAlchemyError as exc:
            raise LayoutUnavailableError from exc

    async def reset(self, user_key: Any, dashboard: str = DEFAULT_DASHBOARD) -> bool:
        """Delete the user's saved order; ``False`` when there was none."""
        stmt = delete(layout_table).where(*_owned(user_key, dashboard))
        try:
            async with self._session() as session:
                result = await session.execute(stmt)
                await session.commit()
        except SQLAlchemyError as exc:
            raise LayoutUnavailableError from exc
        return bool(getattr(result, "rowcount", 0))

    async def _update(self, user_key: Any, dashboard: str, widgets: list[str]) -> bool:
        stmt = (
            update(layout_table)
            .where(*_owned(user_key, dashboard))
            .values(widgets=widgets, updated_at=_now())
        )
        async with self._session() as session:
            result = await session.execute(stmt)
            await session.commit()
        return bool(getattr(result, "rowcount", 0))

    async def _insert(self, user_key: Any, dashboard: str, widgets: list[str]) -> None:
        stmt = insert(layout_table).values(
            user_key=str(user_key), dashboard=dashboard, widgets=widgets, updated_at=_now()
        )
        async with self._session() as session:
            await session.execute(stmt)
            await session.commit()


def _owned(user_key: Any, dashboard: str) -> tuple[Any, Any]:
    """The ``WHERE`` clauses selecting one user's row of one dashboard."""
    return (layout_table.c.user_key == str(user_key), layout_table.c.dashboard == dashboard)
