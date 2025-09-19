"""Unit tests for the hyperadmin.core module."""

from unittest.mock import MagicMock

import pytest
from fastapi import FastAPI

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
