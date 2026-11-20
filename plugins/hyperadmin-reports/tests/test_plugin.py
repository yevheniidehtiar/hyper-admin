"""Unit tests for the ``hyperadmin.plugins`` entry point of ``hyperadmin-reports``."""

from __future__ import annotations

from importlib.metadata import entry_points
from types import SimpleNamespace

import pytest
from fastapi import FastAPI
from sqlalchemy.ext.asyncio import create_async_engine

from hyperadmin import Admin
from hyperadmin.core.plugins import Plugin, PluginRegistry
from hyperadmin.core.settings import HyperAdminSettings
from hyperadmin_reports.plugin import ReportsPlugin
from hyperadmin_reports.settings import ReportsSettings


def test_reports_entry_point_resolves_to_reports_plugin() -> None:
    """
    Scenario: the core plugin loader discovers the reports plugin
      Given hyperadmin-reports is installed
      When  the ``hyperadmin.plugins`` entry points are loaded
      Then  the ``reports`` entry point resolves to ReportsPlugin
    """
    (entry_point,) = entry_points(group="hyperadmin.plugins", name="reports")

    assert entry_point.load() is ReportsPlugin


def test_reports_plugin_contributes_chart_templates_and_static() -> None:
    """
    Scenario: registering the reports plugin contributes its chart assets
      Given a PluginRegistry used as admin.plugins
      When  ReportsPlugin is registered
      Then  its template dir holds the chart templates
      And   its static dir holds charts.css, served at /static/plugins/reports
    """
    registry = PluginRegistry()
    plugin = ReportsPlugin()

    assert registry.register(plugin, admin=SimpleNamespace(plugins=registry))

    (template_dir,) = registry.template_dirs
    assert (template_dir.path / "hyperadmin_reports/charts/bar.html").is_file()
    (static_dir,) = registry.static_dirs
    assert (static_dir.path / "charts.css").is_file()
    assert static_dir.mount_path == "/static/plugins/reports"


def test_plugin_registry_discovers_and_registers_reports_plugin() -> None:
    """
    Scenario: PluginRegistry discovery registers the installed reports plugin
      Given hyperadmin-reports is installed in the workspace environment
      When  entry points are loaded into the registry an admin exposes as admin.plugins
      Then  the ``reports`` plugin is registered from its entry point
      And   it satisfies the core Plugin protocol
    """
    registry = PluginRegistry()
    registry.load_entry_points(admin=SimpleNamespace(plugins=registry))

    assert "reports" in registry
    assert isinstance(registry["reports"], Plugin)
    assert registry.origin("reports") == "hyperadmin_reports.plugin:ReportsPlugin"
    assert "reports" not in registry.skipped


def test_reports_plugin_settings_come_from_plugin_settings() -> None:
    """
    Scenario: reports plugin settings come from plugin_settings
      Given Admin(app, engine=engine, plugin_settings={"reports": {"dashboard_home": False}})
      When  the reports plugin is registered
      Then  admin.plugins.settings("reports").dashboard_home is False
      And   dashboard_layouts is True and dashboard_prefix is "/dashboard"
    """
    admin = Admin(
        FastAPI(),
        engine=create_async_engine("sqlite+aiosqlite:///:memory:"),
        settings=HyperAdminSettings(secret_key="x" * 40, create_tables=False),
        plugin_settings={"reports": {"dashboard_home": False}},
    )

    settings = admin.plugins.settings("reports")

    assert isinstance(settings, ReportsSettings)
    assert settings.dashboard_home is False
    assert settings.dashboard_layouts is True
    assert settings.dashboard_prefix == "/dashboard"


def test_reports_plugin_settings_read_the_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    """
    Scenario: reports plugin settings come from HYPERADMIN_REPORTS_ variables
      Given HYPERADMIN_REPORTS_DASHBOARD_LAYOUTS=false and HYPERADMIN_REPORTS_DASHBOARD_PREFIX=/home
      When  ReportsSettings is built without arguments
      Then  dashboard_layouts is False and dashboard_prefix is "/home"
    """
    monkeypatch.setenv("HYPERADMIN_REPORTS_DASHBOARD_LAYOUTS", "false")
    monkeypatch.setenv("HYPERADMIN_REPORTS_DASHBOARD_PREFIX", "/home")

    settings = ReportsSettings()

    assert settings.dashboard_layouts is False
    assert settings.dashboard_prefix == "/home"


def test_reports_plugin_settings_reject_a_bad_dashboard_prefix() -> None:
    """
    Scenario: a dashboard prefix that is not a page prefix is refused
      Given plugin_settings={"reports": {"dashboard_prefix": "dashboard/"}}
      When  the reports plugin is registered
      Then  the plugin is skipped with reason register_error
    """
    registry = PluginRegistry()

    registered = registry.register(
        ReportsPlugin(),
        admin=SimpleNamespace(plugins=registry),
        settings={"dashboard_prefix": "dashboard/"},
    )

    assert not registered
    assert registry.skipped == {"reports": "register_error"}
