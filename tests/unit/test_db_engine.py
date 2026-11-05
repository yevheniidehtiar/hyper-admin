"""Engine factory with configurable pool arguments in ``hyperadmin.db`` (#231, #232)."""

from __future__ import annotations

from typing import Any

import pytest
from pydantic import ValidationError
from sqlalchemy import text
from sqlalchemy.pool import AsyncAdaptedQueuePool, StaticPool

from hyperadmin import db
from hyperadmin.core.settings import HyperAdminSettings

_PG_URL = "postgresql+asyncpg://user:pass@db.example/app"
_POOL_KWARGS: dict[str, Any] = {
    "pool_size": 20,
    "max_overflow": 40,
    "pool_timeout": 15,
    "pool_recycle": 1800,
}


@pytest.fixture(autouse=True)
def _fresh_engine_cache(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(db, "_default_engines", {})


def test_build_engine_forwards_pool_kwargs() -> None:
    """Scenario: pool_size, max_overflow, pool_timeout and pool_recycle reach the pool."""
    engine = db.build_engine(_PG_URL, _POOL_KWARGS)

    pool = engine.sync_engine.pool
    assert isinstance(pool, AsyncAdaptedQueuePool)
    assert pool.size() == 20
    assert pool._max_overflow == 40
    assert pool.timeout() == 15
    assert pool._recycle == 1800


def test_build_engine_without_kwargs_keeps_sqlalchemy_defaults() -> None:
    """Scenario: no engine_kwargs leaves SQLAlchemy's default pool sizing."""
    engine = db.build_engine(_PG_URL)

    pool = engine.sync_engine.pool
    assert pool.size() == 5
    assert pool._max_overflow == 10
    assert pool.timeout() == 30


@pytest.mark.anyio
async def test_build_engine_drops_pool_kwargs_for_in_memory_sqlite() -> None:
    """Scenario: an in-memory SQLite engine ignores pool sizing and stays one shared DB."""
    engine = db.build_engine(
        "sqlite+aiosqlite:///:memory:", {**_POOL_KWARGS, "pool_pre_ping": True}
    )

    assert isinstance(engine.sync_engine.pool, StaticPool)
    assert engine.sync_engine.pool._pre_ping is True
    async with engine.begin() as conn:
        await conn.execute(text("CREATE TABLE t (id INTEGER)"))
    async with engine.connect() as conn:
        assert (await conn.execute(text("SELECT count(*) FROM t"))).scalar() == 0
    await engine.dispose()


def test_build_engine_keeps_pool_kwargs_for_file_sqlite(tmp_path: Any) -> None:
    """Scenario: a file SQLite engine uses a queue pool, so its sizing is honoured."""
    engine = db.build_engine(f"sqlite+aiosqlite:///{tmp_path / 'app.db'}", _POOL_KWARGS)

    assert engine.sync_engine.pool.size() == 20


@pytest.mark.parametrize(
    ("url", "expected"),
    [
        ("sqlite+aiosqlite:///:memory:", True),
        ("sqlite+aiosqlite://", True),
        ("sqlite+aiosqlite:///file:shared?mode=memory&cache=shared&uri=true", True),
        ("sqlite+aiosqlite:///app.db", False),
        (_PG_URL, False),
    ],
)
def test_is_sqlite_memory_url(url: str, expected: bool) -> None:
    """Scenario: only in-memory SQLite URLs are detected as in-memory."""
    assert db.is_sqlite_memory_url(url) is expected


def test_settings_engine_kwargs_empty_by_default() -> None:
    """Scenario: with no database_pool_* settings no pool arguments are passed."""
    assert HyperAdminSettings().database_engine_kwargs == {}


def test_settings_engine_kwargs_maps_every_pool_setting() -> None:
    """Scenario: each database_pool_* setting becomes its create_async_engine argument."""
    settings = HyperAdminSettings(
        database_pool_size=20,
        database_max_overflow=40,
        database_pool_timeout=15,
        database_pool_recycle=1800,
        database_pool_pre_ping=True,
    )

    assert settings.database_engine_kwargs == {**_POOL_KWARGS, "pool_pre_ping": True}


def test_settings_pool_size_reads_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    """Scenario: HYPERADMIN_DATABASE_POOL_SIZE configures the pool without code."""
    monkeypatch.setenv("HYPERADMIN_DATABASE_POOL_SIZE", "25")

    assert HyperAdminSettings().database_engine_kwargs == {"pool_size": 25}


def test_settings_reject_an_empty_pool() -> None:
    """Scenario: a pool size below one is rejected at startup."""
    with pytest.raises(ValidationError):
        HyperAdminSettings(database_pool_size=0)


def test_default_engine_uses_pool_settings() -> None:
    """Scenario: the engine built from database_url gets the database_pool_* settings."""
    settings = HyperAdminSettings(database_url=_PG_URL, database_pool_size=20)

    engine = db.get_default_engine(settings)

    assert engine.sync_engine.pool.size() == 20
    assert engine.echo is False


def test_default_engine_is_cached_per_url_and_pool() -> None:
    """Scenario: equal settings share one engine; a different pool gets its own."""
    first = db.get_default_engine(HyperAdminSettings(database_url=_PG_URL))
    again = db.get_default_engine(HyperAdminSettings(database_url=_PG_URL))
    tuned = db.get_default_engine(HyperAdminSettings(database_url=_PG_URL, database_pool_size=20))

    assert first is again
    assert tuned is not first
