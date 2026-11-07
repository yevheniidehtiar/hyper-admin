"""Unit tests for the ``hyperadmin-logfire`` plugin scaffold (entry point, registration, disable)."""

from __future__ import annotations

from importlib.metadata import entry_points
from pathlib import Path
from typing import Any

from fastapi import FastAPI
from sqlalchemy.ext.asyncio import create_async_engine

from hyperadmin import Admin
from hyperadmin.core.plugins import Plugin
from hyperadmin.core.settings import HyperAdminSettings
from hyperadmin_logfire import LogfirePlugin


def _admin(tmp_path: Path, **admin_kwargs: Any) -> Admin:
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'logfire.db'}")
    return Admin(
        FastAPI(),
        engine=engine,
        settings=HyperAdminSettings(secret_key="logfire-test-secret"),
        **admin_kwargs,
    )


def test_logfire_entry_point_resolves_to_logfire_plugin() -> None:
    """
    Scenario: the core plugin loader discovers the logfire plugin
      Given hyperadmin-logfire is installed
      When  the ``hyperadmin.plugins`` entry points are loaded
      Then  the ``logfire`` entry point resolves to LogfirePlugin
    """
    (entry_point,) = entry_points(group="hyperadmin.plugins", name="logfire")

    assert entry_point.load() is LogfirePlugin
    assert isinstance(LogfirePlugin(), Plugin)


def test_logfire_plugin_registers_without_seams(tmp_path: Path) -> None:
    """
    Scenario: the admin loads the logfire plugin
      Given hyperadmin-logfire is installed
      When  Admin is constructed
      Then  "logfire" is in admin.plugins
      And   it contributed no pages, nav entries or permissions
    """
    admin = _admin(tmp_path)

    assert "logfire" in admin.plugins
    plugins = admin.plugins
    contributed = {p.plugin for p in plugins.pages} | {n.plugin for n in plugins.nav_entries}
    contributed |= {p.plugin for p in plugins.permissions}
    assert "logfire" not in contributed


def test_logfire_plugin_is_not_loaded_when_disabled(tmp_path: Path) -> None:
    """
    Scenario: the logfire plugin is skipped when disabled
      Given hyperadmin-logfire is installed
      When  Admin is constructed with disabled_plugins=["logfire"]
      Then  "logfire" is not in admin.plugins
    """
    admin = _admin(tmp_path, disabled_plugins=["logfire"])

    assert "logfire" not in admin.plugins
