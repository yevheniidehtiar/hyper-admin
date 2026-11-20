from importlib.metadata import EntryPoint

import pytest
from typer.testing import CliRunner

from hyperadmin.__main__ import app
from hyperadmin.management.commands import plugins as plugins_cmd

runner = CliRunner()
GROUP = "hyperadmin.plugins"


def _patch(monkeypatch: pytest.MonkeyPatch, eps: list[EntryPoint]) -> None:
    monkeypatch.setattr(plugins_cmd, "entry_points", lambda group: eps)


def _demo() -> EntryPoint:
    return EntryPoint(name="demo", value="demo_plugin:DemoPlugin", group=GROUP)


def test_plugins_list_prints_discovered_plugins(monkeypatch):
    """
    Scenario: hyperadmin plugins list CLI prints discovered plugins
      Given demo_plugin is installed
      When  the user runs `hyperadmin plugins list`
      Then  stdout contains "demo" and the plugin's class path
    """
    monkeypatch.delenv("HYPERADMIN_DISABLED_PLUGINS", raising=False)
    _patch(monkeypatch, [_demo()])
    result = runner.invoke(app, ["plugins", "list"])
    assert result.exit_code == 0
    assert "demo" in result.stdout
    assert "demo_plugin:DemoPlugin" in result.stdout
    assert "active" in result.stdout


def test_plugins_list_shows_disabled_status(monkeypatch):
    """
    Scenario: hyperadmin plugins list shows disabled status
      Given demo_plugin is installed and HYPERADMIN_DISABLED_PLUGINS=demo
      When  the user runs `hyperadmin plugins list`
      Then  the row for "demo" shows "disabled"
    """
    monkeypatch.setenv("HYPERADMIN_DISABLED_PLUGINS", "demo")
    _patch(monkeypatch, [_demo()])
    result = runner.invoke(app, ["plugins", "list"])
    row = next(line for line in result.stdout.splitlines() if line.startswith("demo"))
    assert row.endswith("disabled")


def test_plugins_list_with_no_plugins(monkeypatch):
    """
    Scenario: hyperadmin plugins list with no plugins
      Given no entry points exist for hyperadmin.plugins
      When  the user runs `hyperadmin plugins list`
      Then  stdout is "No plugins discovered." and exit code is 0
    """
    _patch(monkeypatch, [])
    result = runner.invoke(app, ["plugins", "list"])
    assert result.exit_code == 0
    assert result.stdout.strip() == "No plugins discovered."


def test_plugins_list_sorted_by_name(monkeypatch):
    """
    Scenario: rows are sorted alphabetically by entry-point name
      Given plugins "zeta" and "alpha" are installed
      When  the user runs `hyperadmin plugins list`
      Then  "alpha" is listed before "zeta"
    """
    monkeypatch.delenv("HYPERADMIN_DISABLED_PLUGINS", raising=False)
    _patch(
        monkeypatch,
        [EntryPoint("zeta", "z:Z", GROUP), EntryPoint("alpha", "a:A", GROUP)],
    )
    lines = runner.invoke(app, ["plugins", "list"]).stdout.splitlines()
    assert lines[1].startswith("alpha")
    assert lines[2].startswith("zeta")
