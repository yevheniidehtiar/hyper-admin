"""Unit tests for the optional in-process worker bound to ``hyperadmin_tasks.lifespan``."""

from __future__ import annotations

import asyncio
import logging
import sys
from types import SimpleNamespace
from typing import Any

import pytest

import hyperadmin_tasks
from hyperadmin.core.plugins import PluginRegistry
from hyperadmin_tasks.backend import TasksBackendError
from hyperadmin_tasks.backends import pgtask as pgtask_backend
from hyperadmin_tasks.integration import resolve_registries
from hyperadmin_tasks.plugin import TasksPlugin
from hyperadmin_tasks.selection import PGTASK_MODULE
from hyperadmin_tasks.settings import TasksSettings

DSN = "postgresql://worker@127.0.0.1:1/tasks"


class _FakeRegistry:
    """Stands in for ``pgtask.TaskRegistry``: unit tests run without the [pgtask] extra."""

    def __init__(self, queue_name: str) -> None:
        self.queue_name = queue_name


class _FakePgtaskWorker:
    """Stands in for ``pgtask.Worker``: rejects duplicate queues like the real one."""

    def __init__(self, dsn: str, registries: list[_FakeRegistry], **options: Any) -> None:
        queues = [registry.queue_name for registry in registries]
        if len(set(queues)) != len(queues):
            raise ValueError("registries must target distinct queues")
        self.dsn, self.registries, self.options = dsn, registries, options


REGISTRY = _FakeRegistry("default")
MAIL_REGISTRY = _FakeRegistry("mail")
REGISTRIES = [REGISTRY, MAIL_REGISTRY]
NOT_A_REGISTRY = 42


class _FakeWorker:
    """Records the lifecycle the integration drives: run() until shutdown()."""

    def __init__(self, *, fail: bool = False) -> None:
        self.events: list[str] = []
        self._stop = asyncio.Event()
        self._fail = fail

    async def run(self) -> None:
        self.events.append("run")
        if self._fail:
            raise RuntimeError("worker lost its database")
        await self._stop.wait()
        self.events.append("drained")

    def shutdown(self) -> None:
        self.events.append("shutdown")
        self._stop.set()


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


@pytest.fixture(autouse=True)
def _clean_env(monkeypatch: pytest.MonkeyPatch) -> None:
    for name in ("RUN_WORKER", "DSN", "WORKER_DSN", "REGISTRIES", "BACKEND"):
        monkeypatch.delenv(f"HYPERADMIN_TASKS_{name}", raising=False)


@pytest.fixture
def fake_pgtask(monkeypatch: pytest.MonkeyPatch) -> None:
    """Install a fake ``pgtask`` module so ``create_worker`` imports it."""
    module = SimpleNamespace(TaskRegistry=_FakeRegistry, Worker=_FakePgtaskWorker)
    monkeypatch.setitem(sys.modules, "pgtask", module)


@pytest.fixture
def built(monkeypatch: pytest.MonkeyPatch) -> SimpleNamespace:
    """Replace the pgtask worker factory; ``calls`` records each call, ``workers`` the fakes."""
    built = SimpleNamespace(calls=[], workers=[])

    def factory(dsn: str, registries: list[Any], settings: TasksSettings) -> _FakeWorker:
        built.calls.append((dsn, registries, settings))
        built.workers.append(_FakeWorker())
        return built.workers[-1]

    monkeypatch.setattr(pgtask_backend, "create_worker", factory)
    return built


def _admin(**settings: Any) -> SimpleNamespace:
    registry = PluginRegistry()
    admin = SimpleNamespace(plugins=registry)
    assert registry.register(TasksPlugin(), admin=admin, settings=settings or None)
    return admin


@pytest.mark.anyio
async def test_worker_starts_and_drains(built: SimpleNamespace) -> None:
    """
    Scenario: worker starts and drains
      Given run_worker=True and a registered TaskRegistry
      When  the app starts then shuts down
      Then  the worker processes tasks while the app runs
      And   shutdown asks the worker to stop and waits for it to drain
    """
    admin = _admin(run_worker=True, dsn=DSN)

    async with hyperadmin_tasks.lifespan(admin, registries=[REGISTRY]):
        await asyncio.sleep(0)
        (worker,) = built.workers
        assert worker.events == ["run"]

    assert worker.events == ["run", "shutdown", "drained"]
    ((dsn, registries, settings),) = built.calls
    assert (dsn, registries, settings.worker_shutdown_grace) == (DSN, [REGISTRY], 30.0)


@pytest.mark.anyio
async def test_worker_disabled_by_default(built: SimpleNamespace) -> None:
    """
    Scenario: disabled by default
      Given default settings
      When  the app starts
      Then  no worker is started
    """
    admin = _admin()

    async with hyperadmin_tasks.lifespan(admin, registries=[REGISTRY]):
        pass

    assert built.calls == []


@pytest.mark.anyio
async def test_worker_prefers_worker_dsn(built: SimpleNamespace) -> None:
    """
    Scenario: the worker connects with the worker-role DSN
      Given run_worker=True with both dsn and worker_dsn set
      When  the app starts
      Then  the worker is built with worker_dsn
    """
    admin = _admin(run_worker=True, dsn="postgresql://admin@db/tasks", worker_dsn=DSN)

    async with hyperadmin_tasks.lifespan(admin, registries=[REGISTRY]):
        pass

    assert built.calls[0][0] == DSN


@pytest.mark.anyio
async def test_worker_crash_is_logged_and_shutdown_still_completes(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    """
    Scenario: a crashed worker is logged, not raised at shutdown
      Given run_worker=True and a worker whose run() fails
      When  the app starts then shuts down
      Then  the failure is logged with its traceback
      And   leaving the lifespan does not raise
    """
    worker = _FakeWorker(fail=True)
    monkeypatch.setattr(pgtask_backend, "create_worker", lambda *_: worker)
    admin = _admin(run_worker=True, dsn=DSN)

    with caplog.at_level(logging.ERROR, logger="hyperadmin_tasks.integration"):
        async with hyperadmin_tasks.lifespan(admin, registries=[REGISTRY]):
            await asyncio.sleep(0)

    assert worker.events == ["run", "shutdown"]
    assert "in-process pgtask worker stopped" in caplog.text
    assert "worker lost its database" in caplog.text


@pytest.mark.anyio
async def test_worker_needs_a_dsn(built: SimpleNamespace) -> None:
    """
    Scenario: run_worker without a DSN fails at startup
      Given run_worker=True and neither dsn nor worker_dsn
      When  the app starts
      Then  TasksBackendError names HYPERADMIN_TASKS_WORKER_DSN
      And   the backend is shut down again
    """
    admin = _admin(run_worker=True)

    with pytest.raises(TasksBackendError, match="HYPERADMIN_TASKS_WORKER_DSN"):
        await hyperadmin_tasks.lifespan(admin, registries=[REGISTRY]).__aenter__()

    assert built.calls == []
    assert not admin.plugins["tasks"].lifecycle.started


@pytest.mark.anyio
async def test_worker_needs_the_pgtask_extra(monkeypatch: pytest.MonkeyPatch) -> None:
    """
    Scenario: run_worker without the [pgtask] extra fails at startup
      Given run_worker=True and the pgtask adapter cannot be imported
      When  the app starts
      Then  TasksBackendError says to install hyperadmin-tasks[pgtask]
    """
    monkeypatch.setitem(sys.modules, PGTASK_MODULE, None)
    admin = _admin(run_worker=True, dsn=DSN)

    with pytest.raises(TasksBackendError, match=r"install hyperadmin-tasks\[pgtask\]"):
        await hyperadmin_tasks.lifespan(admin, registries=[REGISTRY]).__aenter__()


def test_registries_from_settings_path() -> None:
    """
    Scenario: registries come from HYPERADMIN_TASKS_REGISTRIES
      Given registries="module:attr" naming one registry or a list of them
      When  the registries are resolved without an explicit argument
      Then  the named registries are returned as a list
    """
    single = TasksSettings(registries="test_worker:REGISTRY")
    several = TasksSettings(registries="test_worker:REGISTRIES")

    assert resolve_registries(single, None) == [REGISTRY]
    assert resolve_registries(several, None) == REGISTRIES


def test_explicit_registries_win_over_settings() -> None:
    """
    Scenario: lifespan(registries=...) overrides the settings path
      Given registries set in settings and passed explicitly
      When  the registries are resolved
      Then  the explicit ones are used
    """
    settings = TasksSettings(registries="test_worker:REGISTRIES")

    assert resolve_registries(settings, (MAIL_REGISTRY,)) == [MAIL_REGISTRY]


@pytest.mark.parametrize(
    ("path", "explicit", "message"),
    [
        (None, None, "needs task registries"),
        (None, [], "needs task registries"),
        ("test_worker", None, "use 'module:attr'"),
        ("no_such_module_xyz:registry", None, "cannot load task registries"),
        ("test_worker:missing", None, "cannot load task registries"),
    ],
)
def test_registries_errors(path: str | None, explicit: list[Any] | None, message: str) -> None:
    """
    Scenario: missing or unloadable registries fail with a clear error
      Given no registries, a path without ':' or a path that cannot be imported
      When  the registries are resolved
      Then  TasksBackendError explains what to set
    """
    with pytest.raises(TasksBackendError, match=message):
        resolve_registries(TasksSettings(registries=path), explicit)


@pytest.mark.usefixtures("fake_pgtask")
def test_create_worker_builds_a_pgtask_worker() -> None:
    """
    Scenario: the pgtask adapter builds a worker from the settings
      Given two registries on distinct queues
      When  create_worker is called
      Then  a pgtask Worker for the DSN, the registries and the worker options is returned
    """
    settings = TasksSettings(worker_concurrency=2, worker_shutdown_grace=5.0)

    worker = pgtask_backend.create_worker(DSN, REGISTRIES, settings)

    assert isinstance(worker, _FakePgtaskWorker)
    assert (worker.dsn, worker.registries) == (DSN, REGISTRIES)
    assert worker.options == {"concurrency": 2, "shutdown_grace": 5.0}


def test_create_worker_needs_pgtask(monkeypatch: pytest.MonkeyPatch) -> None:
    """
    Scenario: create_worker without pgtask installed
      Given the pgtask package cannot be imported
      When  create_worker is called
      Then  TasksBackendError says to install hyperadmin-tasks[pgtask]
    """
    monkeypatch.setitem(sys.modules, "pgtask", None)

    with pytest.raises(TasksBackendError, match=r"install hyperadmin-tasks\[pgtask\]"):
        pgtask_backend.create_worker(DSN, REGISTRIES, TasksSettings())


@pytest.mark.parametrize(
    ("registries", "message"),
    [
        ([NOT_A_REGISTRY], "not a pgtask TaskRegistry"),
        ([REGISTRY, REGISTRY], "distinct queues"),
    ],
)
@pytest.mark.usefixtures("fake_pgtask")
def test_create_worker_rejects_bad_registries(registries: list[Any], message: str) -> None:
    """
    Scenario: invalid registries fail with TasksBackendError
      Given a non-registry object or two registries on the same queue
      When  create_worker is called
      Then  TasksBackendError explains the problem
    """
    with pytest.raises(TasksBackendError, match=message):
        pgtask_backend.create_worker(DSN, registries, TasksSettings())
