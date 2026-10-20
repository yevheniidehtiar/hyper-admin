"""Unit tests for the ``hyperadmin.plugins`` entry point of ``hyperadmin-reports``."""

from __future__ import annotations

from importlib.metadata import entry_points
from types import SimpleNamespace

from hyperadmin.core.plugins import Plugin, PluginRegistry
from hyperadmin_reports.plugin import ReportsPlugin


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
