"""Tests for admin_prefix template global set by Admin.mount()."""

from unittest.mock import MagicMock

import pytest
from fastapi import FastAPI

from hyperadmin.core.app import Admin
from hyperadmin.core.settings import HyperAdminSettings


@pytest.fixture
def mock_app():
    return MagicMock(spec=FastAPI)


@pytest.fixture
def settings_no_tables():
    return HyperAdminSettings(create_tables=False)


def test_mount_sets_admin_prefix(
    mock_app: MagicMock, settings_no_tables: HyperAdminSettings
) -> None:
    admin = Admin(app=mock_app, settings=settings_no_tables)
    admin.mount("/admin")
    assert admin.templates.env.globals["admin_prefix"] == "/admin"


def test_mount_strips_trailing_slash(
    mock_app: MagicMock, settings_no_tables: HyperAdminSettings
) -> None:
    admin = Admin(app=mock_app, settings=settings_no_tables)
    admin.mount("/admin/")
    assert admin.templates.env.globals["admin_prefix"] == "/admin"


def test_mount_root_path(mock_app: MagicMock, settings_no_tables: HyperAdminSettings) -> None:
    admin = Admin(app=mock_app, settings=settings_no_tables)
    admin.mount("/")
    assert admin.templates.env.globals["admin_prefix"] == ""
