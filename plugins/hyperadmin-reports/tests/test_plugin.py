"""Unit tests for the ``hyperadmin.plugins`` entry point of ``hyperadmin-reports``."""

from __future__ import annotations

from importlib.metadata import entry_points

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


def test_registering_reports_plugin_is_a_no_op() -> None:
    """
    Scenario: registering the stub plugin leaves the admin untouched
      Given a ReportsPlugin named "reports"
      When  on_register is called with an admin
      Then  it returns None without touching the admin
    """
    admin = object()
    plugin = ReportsPlugin()

    assert plugin.name == "reports"
    assert plugin.on_register(admin) is None


def test_plugin_registry_discovers_and_registers_reports_plugin() -> None:
    """
    Scenario: PluginRegistry discovery registers the installed reports plugin
      Given hyperadmin-reports is installed in the workspace environment
      When  PluginRegistry.discover runs
      Then  the ``reports`` plugin is registered from its entry point
      And   it satisfies the core Plugin protocol
    """
    registry = PluginRegistry.discover(admin=object())

    assert "reports" in registry
    assert isinstance(registry["reports"], Plugin)
    assert registry.origin("reports") == "hyperadmin_reports.plugin:ReportsPlugin"
    assert "reports" not in registry.skipped
