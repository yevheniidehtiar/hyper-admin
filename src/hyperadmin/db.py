"""Engine helpers and DDL for HyperAdmin's own database access.

Importing this module creates **no** engine. Demo mode (``Admin(app)`` without
``engine=``) builds one lazily from ``HyperAdminSettings.database_url`` through
:func:`get_default_engine`. The ORM-specific table creation lives here rather
than in ``core/``.
"""

from __future__ import annotations

import warnings
from typing import TYPE_CHECKING, Any, Literal

from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import AsyncConnection, AsyncEngine, create_async_engine
from sqlmodel import SQLModel

if TYPE_CHECKING:
    from collections.abc import Mapping, Sequence

    from sqlalchemy import Table
    from sqlalchemy.engine import URL, Connection

    from hyperadmin.core.settings import HyperAdminSettings

sqlite_url = "sqlite+aiosqlite:///:memory:"

#: ``"hyperadmin"`` creates only the built-in ``hyperadmin_*`` tables; ``"all"`` creates
#: every table registered on ``SQLModel.metadata`` (the host's own models too). Used by
#: ``Admin.create_tables(scope=)`` and the ``hyperadmin init-db`` CLI (SDD C.2).
TableScope = Literal["hyperadmin", "all"]

#: Pool arguments an in-memory SQLite engine cannot take: its ``StaticPool`` rejects the
#: sizing ones, and recycling its single connection would drop the whole database.
_QUEUE_POOL_KWARGS = frozenset(
    {"pool_size", "max_overflow", "pool_timeout", "pool_recycle", "pool_use_lifo"}
)

_default_engines: dict[tuple[str, tuple[tuple[str, Any], ...]], AsyncEngine] = {}


def build_engine(url: str | URL, engine_kwargs: Mapping[str, Any] | None = None) -> AsyncEngine:
    """Create an async engine for ``url``, forwarding ``engine_kwargs`` to SQLAlchemy.

    Pool arguments (``pool_size``, ``max_overflow``, ``pool_timeout``, ``pool_recycle``,
    ``pool_use_lifo``) are dropped for an in-memory SQLite URL, whose ``StaticPool``
    cannot take them, so one configuration works for tests and production alike.
    Without ``engine_kwargs`` SQLAlchemy's own defaults apply (``pool_size=5``,
    ``max_overflow=10``, ``pool_timeout=30``). For a production PostgreSQL behind
    several workers, a starting point is ``pool_size=20, max_overflow=40,
    pool_timeout=30, pool_pre_ping=True``; keep ``workers * (pool_size +
    max_overflow)`` below the server's ``max_connections``.

    Args:
        url: The database URL.
        engine_kwargs: Extra keyword arguments for ``create_async_engine``.
    """
    kwargs = dict(engine_kwargs or {})
    if is_sqlite_memory_url(url):
        kwargs = {key: value for key, value in kwargs.items() if key not in _QUEUE_POOL_KWARGS}
    return create_async_engine(url, **kwargs)


def get_default_engine(settings: HyperAdminSettings | None = None) -> AsyncEngine:
    """Return the demo-mode engine for ``settings.database_url``.

    The engine is built by :func:`build_engine` with the ``database_pool_*`` settings
    on first use and cached per URL and pool configuration, so every caller using
    the same URL (including an in-memory SQLite database) shares it.

    Args:
        settings: The settings to read ``database_url`` from. When ``None``, a
            default ``HyperAdminSettings()`` is used (``HYPERADMIN_*`` env vars).
    """
    if settings is None:
        # Deferred: ``core`` depends on ``db``, never the other way round at import.
        from hyperadmin.core.settings import HyperAdminSettings  # noqa: PLC0415

        settings = HyperAdminSettings()
    url = settings.database_url
    engine_kwargs = settings.database_engine_kwargs
    key = (url, tuple(sorted(engine_kwargs.items())))
    engine = _default_engines.get(key)
    if engine is None:
        engine = build_engine(url, {"echo": False, **engine_kwargs})
        _default_engines[key] = engine
    return engine


def is_sqlite_url(url: str | URL) -> bool:
    """Return ``True`` when ``url`` points at a SQLite database (any driver)."""
    return make_url(url).get_backend_name() == "sqlite"


def is_sqlite_memory_url(url: str | URL) -> bool:
    """Return ``True`` when ``url`` points at an in-memory SQLite database."""
    parsed = make_url(url)
    if parsed.get_backend_name() != "sqlite":
        return False
    return parsed.database in (None, "", ":memory:") or parsed.query.get("mode") == "memory"


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
