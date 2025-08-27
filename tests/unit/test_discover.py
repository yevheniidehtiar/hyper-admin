import logging
from unittest.mock import MagicMock, patch

from hyperadmin.discover import discover_admin_modules


@patch("importlib.import_module")
@patch("os.path.exists")
def test_discover_admin_modules_successfully(mock_exists, mock_import_module, caplog):
    """
    Tests that `discover_admin_modules` can successfully discover and import an admin.py file.
    """
    mock_exists.return_value = True
    mock_app_module = MagicMock()
    mock_app_module.__file__ = "/path/to/app/app_with_admin/__init__.py"
    mock_import_module.side_effect = [mock_app_module, MagicMock()]

    with caplog.at_level(logging.INFO):
        discover_admin_modules(["app_with_admin"])

    assert "Successfully imported app module: app_with_admin" in caplog.text
    assert "Successfully discovered and imported admin module: app_with_admin.admin" in caplog.text


@patch("importlib.import_module")
@patch("os.path.exists")
def test_discover_admin_modules_no_admin_py(mock_exists, mock_import_module, caplog):
    """
    Tests that `discover_admin_modules` handles apps without an admin.py file.
    """
    mock_exists.return_value = False
    mock_app_module = MagicMock()
    mock_app_module.__file__ = "/path/to/app/app_without_admin/__init__.py"
    mock_import_module.return_value = mock_app_module

    with caplog.at_level(logging.DEBUG):
        discover_admin_modules(["app_without_admin"])

    assert "Successfully imported app module: app_without_admin" in caplog.text
    assert "No admin.py file found in app_without_admin" in caplog.text


@patch("importlib.import_module")
@patch("os.path.exists")
def test_discover_admin_modules_import_error(mock_exists, mock_import_module, caplog):
    """
    Tests that `discover_admin_modules` logs an error when an admin.py file has an import error.
    """
    mock_exists.return_value = True
    mock_app_module = MagicMock()
    mock_app_module.__file__ = "/path/to/app/app_with_admin/__init__.py"
    mock_import_module.side_effect = [mock_app_module, ImportError("Test import error")]

    with caplog.at_level(logging.ERROR):
        discover_admin_modules(["app_with_admin"])

    assert "Failed to import admin module app_with_admin.admin: Test import error" in caplog.text


@patch("importlib.import_module")
def test_discover_admin_modules_non_existent_app(mock_import_module, caplog):
    """
    Tests that `discover_admin_modules` handles non-existent app modules.
    """
    mock_import_module.side_effect = ImportError("No module named 'non_existent_app'")
    with caplog.at_level(logging.ERROR):
        discover_admin_modules(["non_existent_app"])

    assert "Failed to import app module non_existent_app: No module named 'non_existent_app'" in caplog.text
