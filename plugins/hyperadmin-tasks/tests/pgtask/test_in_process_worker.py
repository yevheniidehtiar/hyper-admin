"""The in-process worker on a real Postgres + pgtask: tasks run while the lifespan is open."""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any

import pytest

import hyperadmin_tasks
from hyperadmin.core.plugins import PluginRegistry
from hyperadmin_tasks.plugin import TasksPlugin

pytest.importorskip("pgtask")

pytestmark = [pytest.mark.anyio, pytest.mark.pgtask]


async def test_in_process_worker_runs_tasks(pgtask_database: Any) -> None:
    """
    Scenario: worker starts and drains
      Given run_worker=True, the worker-role DSN and a registered TaskRegistry
      When  a task is enqueued while hyperadmin_tasks.lifespan(admin) is open
      Then  the in-process worker runs it to succeeded
      And   leaving the lifespan stops the worker and the backend
    """
    from pgtask import Client, EnqueueRequest, TaskRegistry

    registry = TaskRegistry("default")

    @registry.task("app.double")
    async def _double(task: Any, payload: dict[str, int]) -> int:
        return payload["n"] * 2

    plugins = PluginRegistry()
    admin = SimpleNamespace(plugins=plugins)
    assert plugins.register(
        TasksPlugin(),
        admin=admin,
        settings={
            "backend": "pgtask",
            "observer_dsn": pgtask_database.observer_dsn,
            "worker_dsn": pgtask_database.worker_dsn,
            "run_worker": True,
            "worker_shutdown_grace": 5.0,
        },
    )
    client = await Client.connect(pgtask_database.owner_dsn)

    async with hyperadmin_tasks.lifespan(admin, registries=[registry]):
        handle = await client.enqueue(EnqueueRequest("app.double", {"n": 21}, queue_name="default"))
        result = await handle.result(timeout=30)

    assert result is not None
    assert (result.state, result.result) == ("succeeded", 42)
    assert not plugins["tasks"].lifecycle.started  # type: ignore[attr-defined]
