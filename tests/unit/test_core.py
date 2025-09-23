"""Unit tests for the hyperadmin.core module."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import FastAPI
from sqlmodel import SQLModel

from hyperadmin import core
from hyperadmin.core.app import Admin


def test_import_core() -> None:
    """Verify that the hyperadmin.core module can be imported."""
    assert core is not None


@pytest.fixture
def mock_fastapi_app():
    return MagicMock(spec=FastAPI)


def test_admin_template_dirs(mock_fastapi_app):
    # Arrange
    custom_template_dir = "/my/custom/templates"

    # Act
    admin = Admin(app=mock_fastapi_app, template_dirs=[custom_template_dir])

    # Assert
    assert custom_template_dir in admin.templates.env.loader.searchpath


def test_admin_discover_apps(mock_fastapi_app):
    # Arrange
    apps_to_discover = ["app1", "app2"]

    # Act
    with patch("hyperadmin.core.app.discover_admin_modules") as mock_discover_admin_modules:
        Admin(app=mock_fastapi_app, discover_apps=apps_to_discover)

        # Assert
        mock_discover_admin_modules.assert_called_once_with(apps_to_discover)


@pytest.mark.anyio
async def test_admin_create_tables(mock_fastapi_app):
    # Arrange
    mock_engine = MagicMock()
    mock_conn = AsyncMock()
    mock_engine.begin.return_value.__aenter__.return_value = mock_conn
    admin = Admin(app=mock_fastapi_app, create_tables=True, engine=mock_engine)

    # Act
    mock_fastapi_app.on_event.assert_called_once_with("startup")
    decorator = mock_fastapi_app.on_event.return_value
    decorator.assert_called_once()
    startup_handler = decorator.call_args[0][0]
    await startup_handler()

    # Assert
    mock_engine.begin.assert_called_once()
    mock_conn.run_sync.assert_called_once_with(SQLModel.metadata.create_all)
