"""Tests for admin_prefix template global set by Admin.mount()."""

import pytest
from fastapi import FastAPI

from hyperadmin.core.app import Admin
from hyperadmin.core.settings import HyperAdminSettings


@pytest.fixture
def settings_no_tables():
    return HyperAdminSettings(create_tables=False)


def test_mount_sets_admin_prefix(settings_no_tables: HyperAdminSettings) -> None:
    admin = Admin(app=FastAPI(), settings=settings_no_tables)
    admin.mount("/admin")
    assert admin.templates.env.globals["admin_prefix"] == "/admin"


def test_mount_strips_trailing_slash(settings_no_tables: HyperAdminSettings) -> None:
    """
    Scenario: a trailing slash on the mount path is ignored
      Given an Admin in the default (isolated) mode
      When  it is mounted at "/admin/"
      Then  admin_prefix is "/admin"
      And   the sub-application is mounted at /admin
    """
    app = FastAPI()
    admin = Admin(app=app, settings=settings_no_tables)
    admin.mount("/admin/")
    assert admin.templates.env.globals["admin_prefix"] == "/admin"
    assert app.url_path_for("hyperadmin:admin-dashboard") == "/admin/"


def test_mount_root_path(settings_no_tables: HyperAdminSettings) -> None:
    """
    Scenario: mounting at the root keeps an empty admin_prefix
      Given an Admin in the default (isolated) mode
      When  it is mounted at "/"
      Then  admin_prefix is ""
      And   router mode serves the dashboard at "/"
    """
    app = FastAPI()
    admin = Admin(app=app, settings=settings_no_tables)
    admin.mount("/")
    assert admin.templates.env.globals["admin_prefix"] == ""
    assert app.url_path_for("admin-dashboard") == "/"
