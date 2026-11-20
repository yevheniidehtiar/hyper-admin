"""Fixtures for the plugin E2E suites; kept local so ``tests/e2e/conftest.py`` stays untouched."""

from collections.abc import Iterator

import pytest

from tests.e2e.conftest import _spawn_uvicorn, _terminate


@pytest.fixture
def tasks_base_url(e2e_port: int) -> Iterator[str]:
    """Start the tasks-plugin app (:mod:`tests.e2e.apps.tasks_monitoring`) and yield its URL.

    Seeds superuser ``alice`` and view-only ``viewer`` (both ``secret123``) over an in-memory
    task backend with one failed, one pending, one running and one succeeded task.
    """
    proc, base = _spawn_uvicorn("tests.e2e.apps.tasks_monitoring", e2e_port)
    try:
        yield base
    finally:
        _terminate(proc)


@pytest.fixture
def dashboard_base_url(e2e_port: int) -> Iterator[str]:
    """Start the dashboard app (:mod:`tests.e2e.apps.dashboard_builder`) and yield its URL.

    Seeds superuser ``alice``, ``bob`` (the same permissions, not a superuser), ``viewer``
    (the order reports only) and ``nobody`` (no permission), all ``secret123``, with orders
    of 100, 200 and 300 and five registered dashboard widgets. The layout table exists.
    """
    proc, base = _spawn_uvicorn("tests.e2e.apps.dashboard_builder", e2e_port)
    try:
        yield base
    finally:
        _terminate(proc)
