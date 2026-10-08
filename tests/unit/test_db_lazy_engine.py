"""Lazy default engine and DDL helpers in ``hyperadmin.db`` (st-v058-byoa-20, SDD C.3)."""

from __future__ import annotations

import subprocess
import sys
import textwrap
import warnings

import pytest
from fastapi import FastAPI
from sqlalchemy import inspect
from sqlalchemy.ext.asyncio import AsyncEngine, async_sessionmaker, create_async_engine
from sqlalchemy.orm import sessionmaker
from sqlmodel import Field, SQLModel

from hyperadmin import db
from hyperadmin.core.app import Admin
from hyperadmin.core.settings import HyperAdminSettings

_SPY_PRELUDE = """
import gc
import sqlalchemy.ext.asyncio as sa_async
import sqlalchemy.ext.asyncio.engine as sa_async_engine
from sqlalchemy.ext.asyncio import AsyncEngine

calls = []
_original = sa_async.create_async_engine

def _spy(*args, **kwargs):
    calls.append(args)
    return _original(*args, **kwargs)

sa_async.create_async_engine = _spy
sa_async_engine.create_async_engine = _spy
"""

_SPY_REPORT = """
engines = sum(isinstance(o, AsyncEngine) for o in gc.get_objects())
print(len(calls), engines)
"""


def _run(code: str) -> str:
    result = subprocess.run(
        [sys.executable, "-W", "error::DeprecationWarning:hyperadmin", "-c", code],
        check=False,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr
    return result.stdout.strip()


@pytest.mark.parametrize("statement", ["import hyperadmin", "import hyperadmin.db"])
def test_importing_hyperadmin_creates_no_engine(statement: str) -> None:
    """Scenario: importing hyperadmin creates no engine."""
    out = _run(_SPY_PRELUDE + statement + "\n" + _SPY_REPORT)
    assert out == "0 0"


def test_legacy_engine_import_still_works() -> None:
    """Scenario: legacy engine import still works (with a DeprecationWarning)."""
    out = _run(
        textwrap.dedent(
            """
            import warnings
            from sqlalchemy.ext.asyncio import AsyncEngine
            with warnings.catch_warnings(record=True) as caught:
                warnings.simplefilter("always")
                from hyperadmin.db import engine
            deprecations = [w for w in caught if issubclass(w.category, DeprecationWarning)]
            print(isinstance(engine, AsyncEngine), len(deprecations),
                  "get_default_engine" in str(deprecations[0].message))
            """
        )
    )
    assert out == "True 1 True"


def test_legacy_engine_attribute_is_the_cached_default_engine() -> None:
    with pytest.warns(DeprecationWarning, match="hyperadmin.db.engine"):
        legacy = db.engine
    assert legacy is db.get_default_engine()


def test_unknown_module_attribute_raises() -> None:
    with pytest.raises(AttributeError, match="no_such_name"):
        db.no_such_name  # noqa: B018 - attribute access is the behaviour under test


def test_get_default_engine_is_built_from_settings_and_cached_per_url(tmp_path) -> None:
    url_a = f"sqlite+aiosqlite:///{tmp_path / 'a.db'}"
    url_b = f"sqlite+aiosqlite:///{tmp_path / 'b.db'}"

    first = db.get_default_engine(HyperAdminSettings(database_url=url_a))
    again = db.get_default_engine(HyperAdminSettings(database_url=url_a))
    other = db.get_default_engine(HyperAdminSettings(database_url=url_b))

    assert isinstance(first, AsyncEngine)
    assert first is again
    assert other is not first
    assert first.url.database == str(tmp_path / "a.db")


def test_get_default_engine_without_settings_uses_default_settings(monkeypatch) -> None:
    monkeypatch.setenv("HYPERADMIN_DATABASE_URL", "sqlite+aiosqlite:///:memory:")
    engine = db.get_default_engine()
    assert engine is db.get_default_engine(HyperAdminSettings())
    assert engine.url.render_as_string() == "sqlite+aiosqlite:///:memory:"


def test_admin_without_engine_uses_the_default_engine_for_its_settings(tmp_path) -> None:
    settings = HyperAdminSettings(
        database_url=f"sqlite+aiosqlite:///{tmp_path / 'demo.db'}", create_tables=False
    )
    admin = Admin(FastAPI(), settings=settings)
    assert admin.engine is db.get_default_engine(settings)


def test_admin_with_engine_never_builds_a_default_engine(monkeypatch) -> None:
    def _fail(_settings: object = None) -> None:
        pytest.fail("get_default_engine must not be called when an engine is passed")

    monkeypatch.setattr(db, "get_default_engine", _fail)
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    admin = Admin(FastAPI(), engine=engine, settings=HyperAdminSettings(create_tables=False))
    assert admin.engine is engine


@pytest.mark.parametrize(
    ("url", "expected"),
    [
        ("sqlite+aiosqlite:///:memory:", True),
        ("sqlite:///./demo.db", True),
        ("postgresql+asyncpg://u:p@localhost/app", False),
        ("mysql+aiomysql://u:p@localhost/app", False),
    ],
)
def test_is_sqlite_url(url: str, expected: bool) -> None:
    assert db.is_sqlite_url(url) is expected


class _LazyEngineAlpha(SQLModel, table=True):
    __tablename__ = "lazy_engine_alpha"  # type: ignore[reportIncompatibleVariableOverride]
    id: int | None = Field(default=None, primary_key=True)


class _LazyEngineBeta(SQLModel, table=True):
    __tablename__ = "lazy_engine_beta"  # type: ignore[reportIncompatibleVariableOverride]
    id: int | None = Field(default=None, primary_key=True)


async def _table_names(engine: AsyncEngine) -> set[str]:
    async with engine.connect() as conn:
        return set(await conn.run_sync(lambda sync: inspect(sync).get_table_names()))


@pytest.mark.anyio
async def test_create_tables_creates_only_the_given_tables() -> None:
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    await db.create_tables(engine, [_LazyEngineAlpha.__table__])  # type: ignore[attr-defined]

    names = await _table_names(engine)
    assert "lazy_engine_alpha" in names
    assert "lazy_engine_beta" not in names
    await engine.dispose()


@pytest.mark.anyio
async def test_create_tables_without_a_table_list_creates_everything() -> None:
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    await db.create_tables(engine)

    assert {"lazy_engine_alpha", "lazy_engine_beta"} <= await _table_names(engine)
    await engine.dispose()


def test_resolve_bind_reads_the_session_factory_bind() -> None:
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    assert db.resolve_bind(async_sessionmaker(engine)) is engine


@pytest.mark.parametrize("factory", [async_sessionmaker(), sessionmaker(), object()])
def test_resolve_bind_without_a_bind_explains_what_to_pass(factory: object) -> None:
    with pytest.raises(ValueError, match="engine="):
        db.resolve_bind(factory)


@pytest.mark.anyio
async def test_legacy_create_db_and_tables_uses_the_default_engine() -> None:
    with warnings.catch_warnings():
        warnings.simplefilter("error", DeprecationWarning)
        await db.create_db_and_tables()
    assert "lazy_engine_alpha" in await _table_names(db.get_default_engine())


@pytest.mark.anyio
async def test_create_tables_accepts_an_open_connection() -> None:
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await db.create_tables(conn, [_LazyEngineBeta.__table__])  # type: ignore[attr-defined]

    names = await _table_names(engine)
    assert "lazy_engine_beta" in names
    assert "lazy_engine_alpha" not in names
    await engine.dispose()
