"""Unit tests for HyperAdminSettings — env loading, validation, defaults."""

import pytest
from pydantic import ValidationError

from hyperadmin.core.settings import HyperAdminSettings

_DEFAULT_SECRET = "hyperadmin-default-secret"
_DEFAULT_DB_URL = "sqlite+aiosqlite:///:memory:"


class TestDefaults:
    def test_all_fields_have_defaults(self) -> None:
        settings = HyperAdminSettings()
        assert settings.site_title == "HyperAdmin"
        assert settings.site_header == "HyperAdmin"
        assert settings.secret_key == _DEFAULT_SECRET
        assert settings.database_url == _DEFAULT_DB_URL
        assert settings.debug is False
        assert settings.auto_discover is False
        assert settings.discover_apps == []
        assert settings.template_dirs == []
        assert settings.create_tables is True
        assert settings.theme == "auto"
        assert settings.items_per_page == 20
        assert settings.date_format == "%Y-%m-%d"
        assert settings.datetime_format == "%Y-%m-%d %H:%M:%S"

    def test_is_default_secret_key_true_when_using_default(self) -> None:
        settings = HyperAdminSettings()
        assert settings.is_default_secret_key is True

    def test_is_default_secret_key_false_when_explicit(self) -> None:
        settings = HyperAdminSettings(secret_key="my-production-secret")
        assert settings.is_default_secret_key is False


class TestEnvVarLoading:
    def test_site_title_from_env(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("HYPERADMIN_SITE_TITLE", "My App")
        settings = HyperAdminSettings()
        assert settings.site_title == "My App"

    def test_database_url_from_env(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("HYPERADMIN_DATABASE_URL", "sqlite+aiosqlite:///prod.db")
        settings = HyperAdminSettings()
        assert settings.database_url == "sqlite+aiosqlite:///prod.db"

    def test_secret_key_from_env(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("HYPERADMIN_SECRET_KEY", "env-secret")
        settings = HyperAdminSettings()
        assert settings.secret_key == "env-secret"
        assert settings.is_default_secret_key is False

    def test_debug_from_env(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("HYPERADMIN_DEBUG", "true")
        settings = HyperAdminSettings()
        assert settings.debug is True

    def test_theme_from_env(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("HYPERADMIN_THEME", "dark")
        settings = HyperAdminSettings()
        assert settings.theme == "dark"

    def test_items_per_page_from_env(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("HYPERADMIN_ITEMS_PER_PAGE", "50")
        settings = HyperAdminSettings()
        assert settings.items_per_page == 50

    def test_create_tables_from_env(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("HYPERADMIN_CREATE_TABLES", "false")
        settings = HyperAdminSettings()
        assert settings.create_tables is False

    def test_discover_apps_from_env_json(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("HYPERADMIN_DISCOVER_APPS", '["myapp", "otherapp"]')
        settings = HyperAdminSettings()
        assert settings.discover_apps == ["myapp", "otherapp"]

    def test_explicit_kwarg_overrides_env(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("HYPERADMIN_SECRET_KEY", "env-value")
        settings = HyperAdminSettings(secret_key="explicit")
        assert settings.secret_key == "explicit"


class TestValidation:
    def test_invalid_theme_raises(self) -> None:
        with pytest.raises(ValidationError):
            HyperAdminSettings(theme="neon")

    def test_valid_themes_accepted(self) -> None:
        for theme in ("auto", "light", "dark"):
            s = HyperAdminSettings(theme=theme)
            assert s.theme == theme

    def test_invalid_theme_from_env_raises(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("HYPERADMIN_THEME", "neon")
        with pytest.raises(ValidationError):
            HyperAdminSettings()

    def test_items_per_page_must_be_positive(self) -> None:
        with pytest.raises(ValidationError):
            HyperAdminSettings(items_per_page=0)

    def test_items_per_page_negative_raises(self) -> None:
        with pytest.raises(ValidationError):
            HyperAdminSettings(items_per_page=-5)


class TestDotEnvFile:
    def test_loads_from_dotenv_file(
        self, tmp_path: "pytest.TempPathFactory", monkeypatch: pytest.MonkeyPatch
    ) -> None:
        env_file = tmp_path / ".env"
        env_file.write_text("HYPERADMIN_SECRET_KEY=file-secret\nHYPERADMIN_THEME=dark\n")
        monkeypatch.chdir(tmp_path)
        # pydantic-settings reads .env relative to cwd
        settings = HyperAdminSettings(_env_file=str(env_file))
        assert settings.secret_key == "file-secret"
        assert settings.theme == "dark"
        assert settings.is_default_secret_key is False
