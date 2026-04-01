"""Unit tests for the hyperadmin.core module."""

import logging
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import FastAPI
from sqlmodel import SQLModel

from hyperadmin import core
from hyperadmin.core.app import Admin
from hyperadmin.core.settings import HyperAdminSettings


def test_import_core() -> None:
    """Verify that the hyperadmin.core module can be imported."""
    assert core is not None


@pytest.fixture
def mock_fastapi_app() -> MagicMock:
    return MagicMock(spec=FastAPI)


# ---------------------------------------------------------------------------
# Template dirs
# ---------------------------------------------------------------------------


def test_admin_template_dirs(mock_fastapi_app: MagicMock) -> None:
    custom_template_dir = "/my/custom/templates"
    settings = HyperAdminSettings(template_dirs=[custom_template_dir])

    admin = Admin(app=mock_fastapi_app, settings=settings)

    assert custom_template_dir in admin.templates.env.loader.searchpath


# ---------------------------------------------------------------------------
# App discovery
# ---------------------------------------------------------------------------


def test_admin_discover_apps(mock_fastapi_app: MagicMock) -> None:
    apps_to_discover = ["app1", "app2"]
    settings = HyperAdminSettings(discover_apps=apps_to_discover)

    with patch("hyperadmin.core.app.discover_admin_modules") as mock_discover:
        Admin(app=mock_fastapi_app, settings=settings)

        mock_discover.assert_called_once_with(apps_to_discover)


def test_admin_no_discover_when_empty(mock_fastapi_app: MagicMock) -> None:
    settings = HyperAdminSettings(discover_apps=[])

    with patch("hyperadmin.core.app.discover_admin_modules") as mock_discover:
        Admin(app=mock_fastapi_app, settings=settings)

        mock_discover.assert_not_called()


# ---------------------------------------------------------------------------
# create_tables
# ---------------------------------------------------------------------------


@pytest.mark.anyio
async def test_admin_create_tables(mock_fastapi_app: MagicMock) -> None:
    mock_engine = MagicMock()
    mock_conn = AsyncMock()
    mock_engine.begin.return_value.__aenter__.return_value = mock_conn
    settings = HyperAdminSettings(create_tables=True)
    Admin(app=mock_fastapi_app, engine=mock_engine, settings=settings)

    mock_fastapi_app.on_event.assert_called_once_with("startup")
    decorator = mock_fastapi_app.on_event.return_value
    decorator.assert_called_once()
    startup_handler = decorator.call_args[0][0]
    await startup_handler()

    mock_engine.begin.assert_called_once()
    mock_conn.run_sync.assert_called_once_with(SQLModel.metadata.create_all)


@pytest.mark.anyio
async def test_admin_no_create_tables_when_disabled(mock_fastapi_app: MagicMock) -> None:
    settings = HyperAdminSettings(create_tables=False)
    Admin(app=mock_fastapi_app, settings=settings)

    mock_fastapi_app.on_event.assert_not_called()


# ---------------------------------------------------------------------------
# Theme configuration
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("theme", ["auto", "light", "dark"])
def test_admin_theme_valid(mock_fastapi_app: MagicMock, theme: str) -> None:
    settings = HyperAdminSettings(theme=theme)  # type: ignore[arg-type]
    admin = Admin(app=mock_fastapi_app, settings=settings)
    assert admin.theme == theme


def test_admin_theme_default(mock_fastapi_app: MagicMock) -> None:
    admin = Admin(app=mock_fastapi_app)
    assert admin.theme == "auto"


def test_admin_theme_invalid(mock_fastapi_app: MagicMock) -> None:
    with pytest.raises(Exception, match=r"[Ii]nvalid theme|neon"):
        HyperAdminSettings(theme="neon")  # type: ignore[arg-type]


def test_admin_theme_exposed_to_templates(mock_fastapi_app: MagicMock) -> None:
    settings = HyperAdminSettings(theme="dark")
    admin = Admin(app=mock_fastapi_app, settings=settings)
    admin.mount("/admin")
    assert admin.templates.env.globals["theme"] == "dark"


# ---------------------------------------------------------------------------
# Settings auto-instantiation
# ---------------------------------------------------------------------------


def test_admin_auto_instantiates_settings(mock_fastapi_app: MagicMock) -> None:
    admin = Admin(app=mock_fastapi_app)
    assert isinstance(admin.settings, HyperAdminSettings)


def test_admin_uses_provided_settings(mock_fastapi_app: MagicMock) -> None:
    settings = HyperAdminSettings(site_title="My ERP")
    admin = Admin(app=mock_fastapi_app, settings=settings)
    assert admin.settings.site_title == "My ERP"


# ---------------------------------------------------------------------------
# Session secret security (#378)
# ---------------------------------------------------------------------------


def test_admin_warns_on_default_secret_in_debug_with_auth(
    mock_fastapi_app: MagicMock,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Warning logged when using default secret + auth enabled + debug mode."""
    mock_auth = MagicMock()
    settings = HyperAdminSettings(debug=True)  # default secret_key

    with caplog.at_level(logging.WARNING, logger="hyperadmin"):
        Admin(app=mock_fastapi_app, settings=settings, auth_backend=mock_auth)

    assert any("default session secret" in r.message.lower() for r in caplog.records)


def test_admin_raises_on_default_secret_in_production_with_auth(
    mock_fastapi_app: MagicMock,
) -> None:
    """ValueError raised when auth enabled + default secret + debug=False."""
    mock_auth = MagicMock()
    settings = HyperAdminSettings(debug=False)  # default secret_key

    with pytest.raises(ValueError, match=r"[Ss]ecret|HYPERADMIN_SECRET_KEY"):
        Admin(app=mock_fastapi_app, settings=settings, auth_backend=mock_auth)


def test_admin_no_warning_when_secret_set_with_auth(
    mock_fastapi_app: MagicMock,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """No warning or error when explicit secret_key is provided."""
    mock_auth = MagicMock()
    settings = HyperAdminSettings(secret_key="my-production-secret", debug=True)

    with caplog.at_level(logging.WARNING, logger="hyperadmin"):
        Admin(app=mock_fastapi_app, settings=settings, auth_backend=mock_auth)

    assert not any("default session secret" in r.message.lower() for r in caplog.records)


def test_admin_no_warning_without_auth(
    mock_fastapi_app: MagicMock,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """No warning when auth is not enabled (even with default secret)."""
    settings = HyperAdminSettings(debug=True)

    with caplog.at_level(logging.WARNING, logger="hyperadmin"):
        Admin(app=mock_fastapi_app, settings=settings)

    assert not any("default session secret" in r.message.lower() for r in caplog.records)


# ---------------------------------------------------------------------------
# Template globals from settings
# ---------------------------------------------------------------------------


def test_admin_site_title_in_template_globals(mock_fastapi_app: MagicMock) -> None:
    settings = HyperAdminSettings(site_title="ERP Admin", theme="light")
    admin = Admin(app=mock_fastapi_app, settings=settings)
    admin.mount("/admin")
    assert admin.templates.env.globals["site_title"] == "ERP Admin"
    assert admin.templates.env.globals["theme"] == "light"
