"""Shared fixtures: a real admin mounted with the tasks plugin over a chosen backend."""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import create_async_engine

from hyperadmin import Admin
from hyperadmin.core.settings import HyperAdminSettings
from hyperadmin_tasks.backend import TaskBackend, TaskRecord, TaskState


@pytest.fixture
def now() -> datetime:
    """A fixed clock reading shared by seeded records and the backend clock."""
    return datetime(2026, 11, 1, 12, 0, tzinfo=UTC)


@pytest.fixture
def make_task(now: datetime) -> Callable[..., TaskRecord]:
    """Build a task record with sensible defaults; keyword overrides replace any field."""

    def factory(task_id: str, **overrides: Any) -> TaskRecord:
        fields: dict[str, Any] = {
            "id": task_id,
            "queue": "default",
            "name": "app.job",
            "state": TaskState.PENDING,
            "priority": 0,
            "attempt": 0,
            "max_attempts": 3,
            "created_at": now,
        }
        fields.update(overrides)
        return TaskRecord(**fields)

    return factory


@pytest.fixture
def make_client(tmp_path: Path) -> Callable[..., TestClient]:
    """Build a client for an admin whose tasks plugin uses ``backend`` (default: its own)."""

    def factory(backend: TaskBackend | None = None) -> TestClient:
        engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'tasks.db'}")
        app = FastAPI()
        admin = Admin(
            app, engine=engine, settings=HyperAdminSettings(secret_key="tasks-test-secret")
        )
        admin.mount("/admin")
        if backend is not None:
            admin.plugins["tasks"].lifecycle.backend = backend  # type: ignore[attr-defined]
        return TestClient(app, follow_redirects=False)

    return factory
