import logging
import sys
from pathlib import Path
from unittest.mock import patch

from hyperadmin.discover import discover_admin_modules

# Add the test_apps directory to the Python path
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "test_apps"))


def test_discover_admin_modules_successfully(caplog):
    """
    Tests that `discover_admin_modules` can successfully discover and import an admin.py file.
    """
    with caplog.at_level(logging.INFO):
        discover_admin_modules(["app_with_admin"])

    assert "Successfully imported app module: app_with_admin" in caplog.text
    assert "Successfully discovered and imported admin module: app_with_admin.admin" in caplog.text


def test_discover_admin_modules_no_admin_py(caplog):
    """
    Tests that `discover_admin_modules` handles apps without an admin.py file.
    """
    with caplog.at_level(logging.DEBUG):
        discover_admin_modules(["app_without_admin"])

    assert "Successfully imported app module: app_without_admin" in caplog.text
    assert "No admin.py file found in app_without_admin" in caplog.text


@patch("importlib.import_module")
def test_discover_admin_modules_import_error(mock_import_module, caplog):
    """
    Tests that `discover_admin_modules` logs an error when an admin.py file has an import error.
    """
    # Make the first call to import_module (for the app) succeed
    # and the second call (for the admin module) fail.
    mock_import_module.side_effect = [
        __import__("app_with_admin"),
        ImportError("Test import error"),
    ]

    with caplog.at_level(logging.ERROR):
        discover_admin_modules(["app_with_admin"])

    assert "Failed to import admin module app_with_admin.admin: Test import error" in caplog.text


def test_discover_admin_modules_non_existent_app(caplog):
    """
    Tests that `discover_admin_modules` handles non-existent app modules.
    """
    with caplog.at_level(logging.ERROR):
        discover_admin_modules(["non_existent_app"])

    assert "Failed to import app module non_existent_app: No module named 'non_existent_app'" in caplog.text
