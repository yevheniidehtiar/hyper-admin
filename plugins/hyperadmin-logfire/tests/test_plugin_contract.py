"""Unit tests for the ``LogfirePlugin`` contract (name, registration hook, protocol)."""

from __future__ import annotations

import logging

import pytest

from hyperadmin.core.plugins import Plugin
from hyperadmin_logfire import LogfirePlugin


def test_plugin_name_attribute() -> None:
    """
    Scenario: the plugin is registered under the name "logfire"
      Given the LogfirePlugin class
      Then  its name attribute is "logfire"
    """
    assert LogfirePlugin.name == "logfire"
    assert LogfirePlugin().name == "logfire"


def test_on_register_contributes_nothing(caplog: pytest.LogCaptureFixture) -> None:
    """
    Scenario: on_register adds no seams and does not touch the admin
      Given a plugin instance and an admin stand-in
      When  on_register is called
      Then  it returns None, leaves the admin untouched and logs nothing
    """
    admin = object()

    with caplog.at_level(logging.DEBUG):
        result = LogfirePlugin().on_register(admin)

    assert result is None
    assert caplog.records == []


def test_runtime_checkable_protocol_satisfaction() -> None:
    """
    Scenario: the plugin satisfies the Plugin protocol
      Given a plugin instance
      Then  isinstance(plugin, Plugin) is true
    """
    assert isinstance(LogfirePlugin(), Plugin)


def test_new_plugin_starts_uninstrumented() -> None:
    """
    Scenario: a fresh plugin has not been instrumented
      Given a new plugin instance
      Then  instrumented is False
    """
    assert LogfirePlugin().instrumented is False
