"""Unit tests for the tasks backend port: models, enums and the capability guard."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import cast

import pytest
from pydantic import ValidationError

from hyperadmin_tasks.backend import (
    AttemptRecord,
    Capability,
    Page,
    QueueStats,
    ScheduleRecord,
    TaskBackend,
    TaskFilter,
    TaskRecord,
    TasksBackendError,
    TaskState,
    WorkerRecord,
    require_capability,
)

_NOW = datetime(2026, 1, 1, tzinfo=UTC)


class _StubBackend:
    def __init__(self, capabilities: frozenset[Capability]) -> None:
        self.capabilities = capabilities


def _task() -> TaskRecord:
    return TaskRecord(
        id="t1",
        queue="default",
        name="send_email",
        state=TaskState.PENDING,
        priority=0,
        attempt=0,
        max_attempts=3,
        created_at=_NOW,
    )


def test_enum_values_match_the_spec() -> None:
    """
    Scenario: enum values match the SDD
      Given the TaskState and Capability enums
      When  their values are listed
      Then  they equal the names documented in the SDD
    """
    assert [s.value for s in TaskState] == [
        "pending",
        "scheduled",
        "running",
        "sleeping",
        "waiting",
        "succeeded",
        "failed",
        "cancelled",
    ]
    assert {c.value for c in Capability} == {
        "retry",
        "cancel",
        "pause_queue",
        "pause_schedule",
        "schedules",
        "workers",
    }


def test_read_models_are_immutable() -> None:
    """
    Scenario: read models are frozen
      Given each read model instance
      When  a field is assigned
      Then  a ValidationError is raised
    """
    models = [
        _task(),
        QueueStats(
            name="q",
            ready=1,
            running=0,
            scheduled=0,
            failed=0,
            succeeded_recent=2,
            oldest_ready_age=timedelta(seconds=3),
        ),
        AttemptRecord(number=1, started_at=_NOW, outcome="ok"),
        WorkerRecord(
            id="w", queues=("q",), task_names=("a",), last_seen_at=_NOW, concurrency=2, healthy=True
        ),
        ScheduleRecord(id="s", task_name="a", queue="q", cron="* * * * *", misfire_policy="skip"),
        TaskFilter(state=TaskState.FAILED),
        Page[int](items=[1], page=1, per_page=10),
    ]
    for model in models:
        field = next(iter(type(model).model_fields))
        with pytest.raises(ValidationError):
            setattr(model, field, getattr(model, field))


def test_page_is_generic_over_item_type() -> None:
    """
    Scenario: Page carries typed items
      Given a Page parametrised with TaskRecord
      When  it is built with a task and no total
      Then  items hold the task and total is None
      And   a non-task item is rejected
    """
    page = Page[TaskRecord](items=[_task()], page=1, per_page=50)

    assert page.items[0].id == "t1"
    assert page.total is None
    with pytest.raises(ValidationError):
        Page[TaskRecord](items=["nope"], page=1, per_page=50)  # type: ignore[list-item]


def test_require_capability_rejects_unsupported_action() -> None:
    """
    Scenario: unsupported action is rejected naming the capability
      Given a backend that only supports RETRY
      When  require_capability is called for CANCEL
      Then  TasksBackendError names the capability
      And   RETRY passes silently
    """
    backend = cast("TaskBackend", _StubBackend(frozenset({Capability.RETRY})))

    require_capability(backend, Capability.RETRY)
    with pytest.raises(TasksBackendError, match="cancel"):
        require_capability(backend, Capability.CANCEL)


def test_task_backend_port_is_runtime_checkable() -> None:
    """
    Scenario: the port can be checked at runtime
      Given an object missing the backend methods
      When  isinstance is checked against TaskBackend
      Then  it is not a TaskBackend
    """
    assert not isinstance(_StubBackend(frozenset()), TaskBackend)
