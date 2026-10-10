"""Unit tests for the ``hyperadmin seed`` Typer CLI (#254)."""

from sqlalchemy import create_engine
from sqlmodel import SQLModel
from typer.testing import CliRunner

import hyperadmin.auth.models  # noqa: F401 - registers hyperadmin_* tables on metadata
from hyperadmin.management.commands import seed as seed_cli
from hyperadmin.management.commands.seed import _to_sync_url, app

runner = CliRunner()


class TestUrlConversion:
    def test_aiosqlite_to_sqlite(self):
        assert _to_sync_url("sqlite+aiosqlite:///erp.db") == "sqlite:///erp.db"

    def test_asyncpg_to_psycopg2(self, monkeypatch):
        monkeypatch.setattr(seed_cli, "_sync_postgres_driver", lambda: "postgresql+psycopg2")
        assert _to_sync_url("postgresql+asyncpg://u@h/db") == "postgresql+psycopg2://u@h/db"

    def test_sync_url_passthrough(self, monkeypatch):
        monkeypatch.setattr(seed_cli, "_sync_postgres_driver", lambda: "postgresql+psycopg2")
        assert _to_sync_url("postgresql://u@h/db") == "postgresql://u@h/db"

    def test_postgres_urls_use_psycopg3_without_psycopg2(self, monkeypatch):
        """
        Scenario: seed a PostgreSQL URL when only psycopg 3 is installed
          Given psycopg2 is not installed and psycopg 3 is
          When  a postgresql:// or postgresql+asyncpg:// URL is converted
          Then  both use the postgresql+psycopg driver
        """
        monkeypatch.setattr(seed_cli, "_sync_postgres_driver", lambda: "postgresql+psycopg")
        assert _to_sync_url("postgresql://u@h/db") == "postgresql+psycopg://u@h/db"
        assert _to_sync_url("postgresql+asyncpg://u@h/db") == "postgresql+psycopg://u@h/db"

    def test_driver_prefers_psycopg2_when_installed(self, monkeypatch):
        monkeypatch.setattr(seed_cli, "find_spec", lambda name: object())
        assert seed_cli._sync_postgres_driver() == "postgresql+psycopg2"

    def test_driver_falls_back_to_psycopg3(self, monkeypatch):
        monkeypatch.setattr(
            seed_cli,
            "find_spec",
            lambda name: None if name == "psycopg2" else object(),
        )
        assert seed_cli._sync_postgres_driver() == "postgresql+psycopg"


class TestErrorPaths:
    def test_missing_database_url_exits_1(self, monkeypatch):
        monkeypatch.delenv("DATABASE_URL", raising=False)
        result = runner.invoke(app, ["--count", "10"])
        assert result.exit_code == 1
        assert "DATABASE_URL" in result.output

    def test_negative_count_exits_1(self, monkeypatch):
        monkeypatch.delenv("DATABASE_URL", raising=False)
        result = runner.invoke(app, ["--count", "-1", "--database-url", "sqlite:///:memory:"])
        assert result.exit_code == 1
        assert "--count" in result.output

    def test_unknown_plan_exits_1(self, monkeypatch):
        monkeypatch.delenv("DATABASE_URL", raising=False)
        result = runner.invoke(
            app,
            ["--count", "10", "--plan", "bogus", "--database-url", "sqlite:///:memory:"],
        )
        assert result.exit_code == 1
        assert "available plans" in result.output


class TestHappyPath:
    def test_seeds_auth_plan_into_sqlite(self, tmp_path, monkeypatch):
        monkeypatch.delenv("DATABASE_URL", raising=False)
        url = f"sqlite:///{tmp_path / 'auth.db'}"
        engine = create_engine(url)
        SQLModel.metadata.create_all(engine)
        engine.dispose()

        result = runner.invoke(
            app,
            [
                "--count",
                "50",
                "--plan",
                "auth",
                "--database-url",
                url,
                "--no-progress",
                "--state-file",
                str(tmp_path / ".seed.json"),
            ],
        )
        assert result.exit_code == 0, result.output
        assert "Seeded 50 rows" in result.output

    def test_resume_with_drifted_plan_exits_2(self, tmp_path, monkeypatch):
        monkeypatch.delenv("DATABASE_URL", raising=False)
        url = f"sqlite:///{tmp_path / 'auth.db'}"
        engine = create_engine(url)
        SQLModel.metadata.create_all(engine)
        engine.dispose()

        # A checkpoint whose plan_hash cannot match any real plan forces an abort on --resume.
        state_file = tmp_path / ".seed.json"
        state_file.write_text(
            '{"plan_hash": "sha256:stale", "rng_seed": 42, "started_at": "x", '
            '"tables": {"hyperadmin_users": {"target": 5, "completed": 0, "last_pk": null}}}'
        )
        result = runner.invoke(
            app,
            [
                "--count",
                "50",
                "--plan",
                "auth",
                "--database-url",
                url,
                "--no-progress",
                "--resume",
                "--state-file",
                str(state_file),
            ],
        )
        assert result.exit_code == 2
        assert "cannot resume" in result.output
