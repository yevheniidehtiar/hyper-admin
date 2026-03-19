"""Tests for admin_prefix template global set by Admin.mount()."""

from unittest.mock import MagicMock

import pytest
from fastapi import FastAPI

from hyperadmin.core.app import Admin


@pytest.fixture
def mock_app():
    return MagicMock(spec=FastAPI)


def test_mount_sets_admin_prefix(mock_app):
    admin = Admin(app=mock_app, create_tables=False)
    admin.mount("/admin")
    assert admin.templates.env.globals["admin_prefix"] == "/admin"


def test_mount_strips_trailing_slash(mock_app):
    admin = Admin(app=mock_app, create_tables=False)
    admin.mount("/admin/")
    assert admin.templates.env.globals["admin_prefix"] == "/admin"


def test_mount_root_path(mock_app):
    admin = Admin(app=mock_app, create_tables=False)
    admin.mount("/")
    assert admin.templates.env.globals["admin_prefix"] == ""
