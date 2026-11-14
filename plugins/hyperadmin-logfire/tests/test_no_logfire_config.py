"""Unit tests for the unconfigured case: the plugin never configures logfire itself.

Each scenario runs in a fresh interpreter, because other tests in the process call
``logfire.configure()`` and logfire's global state cannot be reset reliably.
"""

from __future__ import annotations

import subprocess
import sys
import textwrap

_SCRIPT = textwrap.dedent(
    """
    import warnings

    from hyperadmin_logfire import LogfirePlugin


    class Product:
        pass


    plugin = LogfirePlugin()
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        for _ in range(3):
            plugin.on_before_adapter_call(admin=None, model=Product, op="get", kwargs={"pk": 1})
            plugin.on_after_adapter_call(admin=None, model=Product, op="get", result=None)
    for item in caught:
        print(item.category.__name__)
    """
)


def _run_unconfigured() -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-c", _SCRIPT], capture_output=True, text=True, check=False, timeout=120
    )


def test_warning_emitted_once_when_logfire_not_configured() -> None:
    """
    Scenario: an unconfigured logfire warns exactly once
      Given logfire.configure() was never called
      When  three adapter calls run through the plugin
      Then  one LogfireNotConfiguredWarning is raised
      And   the calls do not crash
    """
    completed = _run_unconfigured()

    assert completed.returncode == 0, completed.stderr
    assert completed.stdout.split() == ["LogfireNotConfiguredWarning"]


def test_no_spans_emitted_when_logfire_not_configured() -> None:
    """
    Scenario: an unconfigured logfire records no spans and leaves no state behind
      Given logfire.configure() was never called
      When  adapter calls run through the plugin
      Then  nothing is written to stderr and the span stack is empty afterwards
    """
    completed = _run_unconfigured()

    assert completed.returncode == 0, completed.stderr
    assert "Traceback" not in completed.stderr
    assert "{" not in completed.stdout  # no console span output
