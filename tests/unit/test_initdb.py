"""Unit tests for the ``hyperadmin init-db`` CLI command (SDD C.2).

Spec: ``docs/specs/bring-your-own-app.md`` section C.2.
"""

from __future__ import annotations

import pytest
from sqlalchemy import create_engine, inspect
from typer.testing import CliRunner

from hyperadmin.__main__ import app

runner = CliRunner()


def _table_names(db_url: str) -> set[str]:
    sync_url = db_url.replace("sqlite+aiosqlite", "sqlite")
    engine = create_engine(sync_url)
    try:
        return set(inspect(engine).get_table_names())
    finally:
        engine.dispose()


def test_init_db_creates_only_hyperadmin_tables(tmp_path) -> None:
    """
    Scenario: init-db creates only hyperadmin tables
      Given an empty DB and host SQLModel models imported
      When  hyperadmin init-db --database-url URL runs
      Then  only hyperadmin_* tables exist
    """
    # Given
    import examples.simple.models  # noqa: F401 — registers a host model on SQLModel.metadata

    db_path = tmp_path / "init.db"
    db_url = f"sqlite+aiosqlite:///{db_path}"

    # When
    result = runner.invoke(app, ["init-db", "--database-url", db_url])

    # Then
    assert result.exit_code == 0, result.stdout
    names = _table_names(db_url)
    assert "hyperadmin_users" in names
    assert "hyperadmin_permissions" in names
    assert all(name.startswith("hyperadmin_") for name in names)


def test_init_db_with_all_flag_creates_every_table(tmp_path) -> None:
    """
    Scenario: init-db --all creates every SQLModel table
      Given an empty DB and a host model imported
      When  hyperadmin init-db --database-url URL --all runs
      Then  the host's own table exists alongside the hyperadmin_* tables
    """
    import examples.simple.models  # noqa: F401

    db_path = tmp_path / "init_all.db"
    db_url = f"sqlite+aiosqlite:///{db_path}"

    result = runner.invoke(app, ["init-db", "--database-url", db_url, "--all"])

    assert result.exit_code == 0, result.stdout
    names = _table_names(db_url)
    assert "hyperadmin_users" in names
    assert any(not name.startswith("hyperadmin_") for name in names)


def test_init_db_reports_which_tables_were_created(tmp_path) -> None:
    """``init-db`` echoes a clear message distinguishing scope."""
    db_path = tmp_path / "msg.db"
    db_url = f"sqlite+aiosqlite:///{db_path}"

    hyperadmin_only = runner.invoke(app, ["init-db", "--database-url", db_url])
    assert "hyperadmin_" in hyperadmin_only.stdout

    all_tables = runner.invoke(
        app, ["init-db", "--database-url", f"sqlite+aiosqlite:///{tmp_path / 'msg2.db'}", "--all"]
    )
    assert "every" in all_tables.stdout.lower()


def test_init_db_connection_failure_never_leaks_the_password() -> None:
    """
    Scenario: a connection failure never prints the database password
      Given a --database-url with a password, pointing at an unreachable host
      When  hyperadmin init-db --database-url URL runs
      Then  the command exits 1 with a clear error, and the password never
        appears in the output — not in the error message, and not in a
        pretty-exception traceback with frame locals (Typer's default on
        every release before 0.17, inside this project's typer>=0.12 floor)
    """
    pytest.importorskip("asyncpg")
    password = "S3cretPW"
    db_url = f"postgresql+asyncpg://admin:{password}@127.0.0.1:1/db"

    result = runner.invoke(app, ["init-db", "--database-url", db_url])

    assert result.exit_code == 1
    assert password not in result.output
    assert "init-db failed" in result.output
