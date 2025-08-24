"""
This module provides the auto-discovery mechanism for admin modules.
"""
import importlib
import logging
import os
from typing import List

logger = logging.getLogger(__name__)


def discover_admin_modules(app_modules: List[str]):
    """
    Discovers and imports `admin.py` modules from a list of app modules.

    Args:
        app_modules: A list of strings representing the app modules to scan.
    """
    for app_module_str in app_modules:
        try:
            # Import the app module
            app_module = importlib.import_module(app_module_str)
            logger.info(f"Successfully imported app module: {app_module_str}")

            # Get the directory of the app module
            if app_module.__file__ is None:
                logger.warning(f"Skipping {app_module_str} because it's a namespace package.")
                continue

            module_dir = os.path.dirname(app_module.__file__)
            admin_py_path = os.path.join(module_dir, "admin.py")

            # Check if admin.py exists
            if os.path.exists(admin_py_path):
                admin_module_str = f"{app_module_str}.admin"
                try:
                    # Import the admin.py module
                    importlib.import_module(admin_module_str)
                    logger.info(f"Successfully discovered and imported admin module: {admin_module_str}")
                except ImportError as e:
                    logger.error(f"Failed to import admin module {admin_module_str}: {e}")
            else:
                logger.debug(f"No admin.py file found in {app_module_str}")

        except ImportError as e:
            logger.error(f"Failed to import app module {app_module_str}: {e}")
