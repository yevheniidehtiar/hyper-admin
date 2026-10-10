"""Engine helpers and DDL for HyperAdmin's own database access.

Importing this module creates **no** engine. Demo mode (``Admin(app)`` without
``engine=``) builds one lazily from ``HyperAdminSettings.database_url`` through
:func:`get_default_engine`. The ORM-specific table creation lives here rather
than in ``core/``.
"""

from __future__ import annotations

import warnings
from typing import TYPE_CHECKING, Any

from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import AsyncConnection, AsyncEngine, create_async_engine
from sqlmodel import SQLModel

if TYPE_CHECKING:
    from collections.abc import Sequence

    from sqlalchemy import Table
    from sqlalchemy.engine import URL, Connection

    from hyperadmin.core.settings import HyperAdminSettings

sqlite_url = "sqlite+aiosqlite:///:memory:"

_default_engines: dict[str, AsyncEngine] = {}


def get_default_engine(settings: HyperAdminSettings | None = None) -> AsyncEngine:
    """Return the demo-mode engine for ``settings.database_url``.

    The engine is created on first use and cached per URL, so every caller
    using the same URL (including an in-memory SQLite database) shares it.

    Args:
        settings: The settings to read ``database_url`` from. When ``None``, a
            default ``HyperAdminSettings()`` is used (``HYPERADMIN_*`` env vars).
    """
    if settings is None:
        # Deferred: ``core`` depends on ``db``, never the other way round at import.
        from hyperadmin.core.settings import HyperAdminSettings  # noqa: PLC0415

        settings = HyperAdminSettings()
    url = settings.database_url
    engine = _default_engines.get(url)
    if engine is None:
        engine = create_async_engine(url, echo=False)
        _default_engines[url] = engine
    return engine


def is_sqlite_url(url: str | URL) -> bool:
    """Return ``True`` when ``url`` points at a SQLite database (any driver)."""
    return make_url(url).get_backend_name() == "sqlite"


def resolve_bind(session_factory: Any) -> AsyncEngine | AsyncConnection:
    """Return the engine a session factory is bound to, for running DDL.

    Works with ``async_sessionmaker(engine)`` (it reads ``session_factory.kw["bind"]``).

    Raises:
        ValueError: when the factory carries no async bind, explaining what to pass.
    """
    kw = getattr(session_factory, "kw", None)
    bind = kw.get("bind") if isinstance(kw, dict) else None
    if isinstance(bind, (AsyncEngine, AsyncConnection)):
        return bind
    msg = (
        "Cannot create tables: the session_factory has no async engine bound to it. "
        "Pass engine= to Admin(...), or use async_sessionmaker(engine)."
    )
    raise ValueError(msg)


def _create_some(sync_conn: Connection, tables: list[Table]) -> None:
    SQLModel.metadata.create_all(sync_conn, tables=tables)


async def _run_create(conn: AsyncConnection, tables: Sequence[Table] | None) -> None:
    if tables is None:
        await conn.run_sync(SQLModel.metadata.create_all)
    else:
        await conn.run_sync(_create_some, list(tables))


async def create_tables(
    engine: AsyncEngine | AsyncConnection, tables: Sequence[Table] | None = None
) -> None:
    """Create ``tables`` (default: every table on ``SQLModel.metadata``) if missing."""
    if isinstance(engine, AsyncConnection):
        await _run_create(engine, tables)
        return
    async with engine.begin() as conn:
        await _run_create(conn, tables)


async def create_db_and_tables() -> None:
    """Create every ``SQLModel`` table on the default engine (legacy helper)."""
    await create_tables(get_default_engine())


def __getattr__(name: str) -> Any:
    """Keep ``from hyperadmin.db import engine`` working, with a deprecation warning."""
    if name == "engine":
        warnings.warn(
            "hyperadmin.db.engine is deprecated and will be removed in 0.6; pass your "
            "own engine to Admin(engine=...) or call hyperadmin.db.get_default_engine().",
            DeprecationWarning,
            stacklevel=2,
        )
        return get_default_engine()
    msg = f"module {__name__!r} has no attribute {name!r}"
    raise AttributeError(msg)
