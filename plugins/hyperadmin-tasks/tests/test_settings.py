"""Unit tests for TasksSettings, backend selection and the backend lifecycle."""

from __future__ import annotations

import asyncio
import sys
from types import ModuleType, SimpleNamespace
from typing import Any

import pytest

import hyperadmin_tasks
from hyperadmin.core.plugins import PluginRegistry
from hyperadmin_tasks.backend import TaskBackend, TasksBackendError
from hyperadmin_tasks.backends.memory import InMemoryTaskBackend
from hyperadmin_tasks.lifecycle import BackendLifecycle
from hyperadmin_tasks.plugin import TasksPlugin
from hyperadmin_tasks.selection import PGTASK_MODULE, select_backend
from hyperadmin_tasks.settings import TasksSettings


class _CountingBackend(InMemoryTaskBackend):
    def __init__(self) -> None:
        super().__init__()
        self.calls: list[str] = []

    async def startup(self) -> None:
        await asyncio.sleep(0)
        self.calls.append("startup")

    async def shutdown(self) -> None:
        self.calls.append("shutdown")


def make_backend(settings: TasksSettings) -> TaskBackend:
    """Factory referenced as ``test_settings:make_backend`` by the tests."""
    return _CountingBackend()


def make_wrong(settings: TasksSettings) -> object:
    """Factory returning something that is not a TaskBackend."""
    return object()


NOT_CALLABLE = 42


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


@pytest.fixture(autouse=True)
def _clean_env(monkeypatch: pytest.MonkeyPatch) -> None:
    for name in ("BACKEND", "DSN", "OBSERVER_DSN", "REFRESH_SECONDS", "PAGE_SIZE", "RUN_WORKER"):
        monkeypatch.delenv(f"HYPERADMIN_TASKS_{name}", raising=False)


def _register(**env_settings: Any) -> tuple[TasksPlugin, PluginRegistry, bool]:
    registry = PluginRegistry()
    plugin = TasksPlugin()
    ok = registry.register(
        plugin, admin=SimpleNamespace(plugins=registry), settings=env_settings or None
    )
    return plugin, registry, ok


def test_settings_defaults() -> None:
    """
    Scenario: settings default to the in-memory backend
      Given no HYPERADMIN_TASKS_* env vars
      When  TasksSettings is built
      Then  the documented defaults apply
    """
    settings = TasksSettings()

    assert (settings.backend, settings.dsn, settings.observer_dsn) == ("memory", None, None)
    assert (settings.refresh_seconds, settings.page_size, settings.run_worker) == (5, 50, False)


def test_settings_read_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """
    Scenario: settings are read from the environment
      Given HYPERADMIN_TASKS_PAGE_SIZE=10 and HYPERADMIN_TASKS_REFRESH_SECONDS=0
      When  TasksSettings is built
      Then  the values are applied
    """
    monkeypatch.setenv("HYPERADMIN_TASKS_PAGE_SIZE", "10")
    monkeypatch.setenv("HYPERADMIN_TASKS_REFRESH_SECONDS", "0")

    settings = TasksSettings()

    assert (settings.page_size, settings.refresh_seconds) == (10, 0)


def test_memory_backend_by_default() -> None:
    """
    Scenario: memory backend by default
      Given no HYPERADMIN_TASKS_* env vars
      When  the plugin is registered
      Then  the plugin uses InMemoryTaskBackend
      And   the registry exposes the validated settings
    """
    plugin, registry, ok = _register()

    assert ok
    assert type(plugin.lifecycle.backend) is InMemoryTaskBackend
    assert isinstance(registry.settings("tasks"), TasksSettings)


def test_register_without_registry_settings_uses_defaults() -> None:
    """
    Scenario: on_register tolerates an admin whose registry holds no settings
      Given an admin whose plugins.settings() returns None
      When  on_register runs
      Then  default settings select the in-memory backend
    """

    class _NoSettings(PluginRegistry):
        def settings(self, name: str) -> Any:
            return None

    plugins = _NoSettings()
    plugin = TasksPlugin()

    assert plugins.register(plugin, admin=SimpleNamespace(plugins=plugins))

    assert type(plugin.lifecycle.backend) is InMemoryTaskBackend


def test_missing_pgtask_extra_is_explained(monkeypatch: pytest.MonkeyPatch) -> None:
    """
    Scenario: missing extra is explained
      Given HYPERADMIN_TASKS_BACKEND=pgtask and pgtask is not installed
      When  the plugin is registered
      Then  TasksBackendError says to install hyperadmin-tasks[pgtask]
      And   the registry skips the plugin
    """
    monkeypatch.setitem(sys.modules, PGTASK_MODULE, None)

    with pytest.raises(TasksBackendError, match=r"install hyperadmin-tasks\[pgtask\]"):
        select_backend(TasksSettings(backend="pgtask"))
    _, registry, ok = _register(backend="pgtask")
    assert not ok
    assert registry.skipped == {"tasks": "register_error"}


def test_pgtask_backend_loaded_lazily(monkeypatch: pytest.MonkeyPatch) -> None:
    """
    Scenario: pgtask backend is loaded when the extra is present
      Given a hyperadmin_tasks.backends.pgtask module exposing create_backend
      When  the backend is selected with backend=pgtask
      Then  create_backend's result is used
    """
    module = ModuleType(PGTASK_MODULE)
    module.create_backend = make_backend  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, PGTASK_MODULE, module)

    assert isinstance(select_backend(TasksSettings(backend="pgtask")), _CountingBackend)


def test_custom_backend_factory() -> None:
    """
    Scenario: custom backend factory
      Given backend is a module:attr path to a factory
      When  the plugin is registered
      Then  the factory's backend is used
    """
    plugin, _, ok = _register(backend="test_settings:make_backend")

    assert ok
    assert isinstance(plugin.lifecycle.backend, _CountingBackend)


@pytest.mark.parametrize(
    ("choice", "message"),
    [
        ("test_settings:make_wrong", "does not satisfy TaskBackend"),
        ("test_settings:NOT_CALLABLE", "not callable"),
        ("test_settings:missing", "not callable"),
        ("no_such_module_xyz:make", "cannot import backend factory"),
        ("bogus", "unknown tasks backend"),
    ],
)
def test_invalid_backend_choice_is_rejected(choice: str, message: str) -> None:
    """
    Scenario: invalid factory or choice is rejected
      Given a backend setting that resolves to a bad factory, result or name
      When  the backend is selected
      Then  TasksBackendError explains the problem
    """
    with pytest.raises(TasksBackendError, match=message):
        select_backend(TasksSettings(backend=choice))


@pytest.mark.anyio
async def test_startup_called_once_under_concurrent_first_use() -> None:
    """
    Scenario: startup runs once under concurrent first use
      Given a lifecycle around a backend that has not started
      When  ten coroutines call ensure_started concurrently
      Then  backend.startup was awaited exactly once
    """
    backend = _CountingBackend()
    lifecycle = BackendLifecycle(backend)

    results = await asyncio.gather(*(lifecycle.ensure_started() for _ in range(10)))

    assert backend.calls == ["startup"]
    assert all(result is backend for result in results)
    assert lifecycle.started


@pytest.mark.anyio
async def test_shutdown_without_startup_is_a_noop() -> None:
    """
    Scenario: shutting down an unstarted backend does nothing
      Given a lifecycle whose backend never started
      When  shutdown is called
      Then  backend.shutdown is not awaited
    """
    backend = _CountingBackend()

    await BackendLifecycle(backend).shutdown()

    assert backend.calls == []


@pytest.mark.anyio
async def test_lifespan_starts_then_shuts_down() -> None:
    """
    Scenario: lifespan calls startup then shutdown
      Given a registered tasks plugin with a counting backend
      When  the host enters and leaves hyperadmin_tasks.lifespan(admin)
      Then  startup is awaited on entry and shutdown on exit
      And   a route's later ensure_started does not start it twice
    """
    plugin, registry, _ = _register(backend="test_settings:make_backend")
    admin = SimpleNamespace(plugins=registry)
    backend = plugin.lifecycle.backend
    assert isinstance(backend, _CountingBackend)

    async with hyperadmin_tasks.lifespan(admin):
        assert backend.calls == ["startup"]
        await plugin.lifecycle.ensure_started()

    assert backend.calls == ["startup", "shutdown"]
    assert not plugin.lifecycle.started
