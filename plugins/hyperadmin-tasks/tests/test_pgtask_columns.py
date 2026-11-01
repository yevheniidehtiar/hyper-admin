"""Pure mapping tests for the pgtask view columns module (no database needed)."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

import pytest

from hyperadmin_tasks.backend import TaskFilter, TasksBackendError, TaskState
from hyperadmin_tasks.backends import _pgtask_columns as columns

NOW = datetime(2026, 1, 1, 12, 0, tzinfo=UTC)


def _task_row(**overrides: Any) -> dict[str, Any]:
    row: dict[str, Any] = {
        "id": "4b1c0f6e-0000-0000-0000-000000000001",
        "queue_name": "reports",
        "task_name": "app.report",
        "state": "pending",
        "priority": 2,
        "attempt": 0,
        "max_attempts": 5,
        "created_at": NOW,
        "run_at": NOW,
        "completed_at": None,
        "payload": {"n": 1},
        "result": None,
        "error": None,
        "parent_id": None,
    }
    return row | overrides


@pytest.mark.parametrize(
    ("native", "expected"),
    [
        ("pending", TaskState.PENDING),
        ("scheduled", TaskState.SCHEDULED),
        ("running", TaskState.RUNNING),
        ("waiting", TaskState.WAITING),
        ("succeeded", TaskState.SUCCEEDED),
        ("failed", TaskState.FAILED),
        ("cancelled", TaskState.CANCELLED),
    ],
)
def test_task_from_row_maps_native_states(native: str, expected: TaskState) -> None:
    """
    Scenario: native states map onto TaskState
      Given a task_view row in a pgtask native state
      When  task_from_row maps it
      Then  the record carries the normalised state and the copied columns
    """
    record = columns.task_from_row(_task_row(state=native, parent_id="p-1"))
    assert record.state is expected
    assert (record.queue, record.name, record.priority, record.parent_id) == (
        "reports",
        "app.report",
        2,
        "p-1",
    )
    assert record.payload == {"n": 1}


def test_task_from_row_rejects_unknown_state() -> None:
    """
    Scenario: storage drift is reported
      Given a task_view row in a state this adapter does not know
      When  task_from_row maps it
      Then  TasksBackendError names the state
    """
    with pytest.raises(TasksBackendError, match="mystery"):
        columns.task_from_row(_task_row(state="mystery"))


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        (None, None),
        ({"type": "handler_error", "message": "RuntimeError: boom"}, "RuntimeError: boom"),
        ("plain failure", "plain failure"),
        ({"code": 7}, '{"code": 7}'),
        ({"message": 3}, '{"message": 3}'),
    ],
)
def test_error_text(value: Any, expected: str | None) -> None:
    """
    Scenario: pgtask JSON errors render as text
      Given an error value that is null, a pgtask error object, a string or other JSON
      When  error_text renders it
      Then  the message, the string or canonical JSON is returned, and None stays None
    """
    assert columns.error_text(value) == expected


def test_attempt_from_row_uses_native_state_as_outcome() -> None:
    """
    Scenario: attempts keep their outcome
      Given an attempt_view row of a failed attempt
      When  attempt_from_row maps it
      Then  the number, worker, times, outcome and error message are mapped
    """
    attempt = columns.attempt_from_row(
        {
            "attempt": 2,
            "worker_id": "w-1",
            "state": "failed",
            "started_at": NOW,
            "finished_at": NOW + timedelta(seconds=1),
            "error": {"message": "boom"},
        }
    )
    assert (attempt.number, attempt.worker_id, attempt.outcome, attempt.error) == (
        2,
        "w-1",
        "failed",
        "boom",
    )
    assert attempt.finished_at == NOW + timedelta(seconds=1)


def test_queue_stats_combine_overview_and_task_counts() -> None:
    """
    Scenario: queue overview
      Given tasks in ready, running, failed and scheduled states on queue "reports"
      When  queue_stats_from_rows combines the overview and the aggregates
      Then  QueueStats for "reports" has the matching counts and a queue without tasks has zeros
    """
    overview = [
        {"name": "empty", "paused_at": None, "running_count": 0, "ready_count": 0},
        {"name": "reports", "paused_at": NOW, "running_count": 2, "ready_count": 3},
    ]
    counts = [
        {
            "queue_name": "reports",
            "failed_count": 4,
            "succeeded_count": 5,
            "scheduled_count": 6,
            "oldest_ready": timedelta(minutes=3),
        }
    ]
    empty, reports = columns.queue_stats_from_rows(overview, counts)
    assert (empty.ready, empty.running, empty.scheduled, empty.failed) == (0, 0, 0, 0)
    assert empty.oldest_ready_age is None
    assert empty.paused is False
    assert (reports.ready, reports.running, reports.scheduled, reports.failed) == (3, 2, 6, 4)
    assert reports.succeeded_recent == 5
    assert reports.oldest_ready_age == timedelta(minutes=3)
    assert reports.paused is True


def test_workers_group_task_names_and_flag_liveness() -> None:
    """
    Scenario: workers list their task names
      Given worker rows and capability rows with a repeated task name
      When  workers_from_rows combines them
      Then  each worker carries its distinct task names, queue and liveness
    """
    workers = columns.workers_from_rows(
        [
            {"id": "w1", "queue_name": "default", "heartbeat_at": NOW, "live": True},
            {"id": "w2", "queue_name": "mail", "heartbeat_at": NOW, "live": False},
        ],
        [
            {"worker_id": "w1", "task_name": "a"},
            {"worker_id": "w1", "task_name": "a"},
            {"worker_id": "w1", "task_name": "b"},
        ],
    )
    assert [(w.id, w.queues, w.task_names, w.healthy) for w in workers] == [
        ("w1", ("default",), ("a", "b"), True),
        ("w2", ("mail",), (), False),
    ]
    assert workers[0].last_seen_at == NOW


def test_schedule_from_row_renders_cron_and_interval() -> None:
    """
    Scenario: schedules map both kinds
      Given a cron schedule and an interval schedule that is paused
      When  schedule_from_row maps them
      Then  the cron text, "every <n>s", the paused flag and misfire policy are mapped
    """
    base = {
        "id": "s1",
        "task_name": "app.report",
        "queue_name": "default",
        "next_run_at": NOW,
        "misfire_policy": "skip",
        "paused_at": None,
        "cron_expression": "0 3 * * *",
        "interval_milliseconds": None,
    }
    cron = columns.schedule_from_row(base)
    interval = columns.schedule_from_row(
        base | {"cron_expression": None, "interval_milliseconds": 1500, "paused_at": NOW}
    )
    assert (cron.cron, cron.paused, cron.misfire_policy) == ("0 3 * * *", False, "skip")
    assert (interval.cron, interval.paused) == ("every 1.5s", True)


def test_task_where_without_filters_is_empty() -> None:
    """
    Scenario: no filters
      Given an empty TaskFilter
      When  task_where builds the clause
      Then  there is no WHERE clause and no parameters
    """
    assert columns.task_where(TaskFilter()) == ("", [])


def test_task_where_binds_every_user_value() -> None:
    """
    Scenario: parameterised SQL only
      Given a filter with queue, state, name and a hostile id query
      When  task_where builds the clause
      Then  user values appear only as bind parameters and LIKE wildcards are escaped
    """
    flt = TaskFilter(queue="q'; DROP", state=TaskState.FAILED, name="n", id_query="a_b%c\\")
    where, params = columns.task_where(flt)
    assert where == (
        " WHERE queue_name = %s AND state = 'failed' AND task_name = %s AND id::text ILIKE %s"
    )
    assert params == ["q'; DROP", "n", "%a\\_b\\%c\\\\%"]
    assert "DROP" not in where


@pytest.mark.parametrize("state", list(TaskState))
def test_every_task_state_has_a_filter_predicate(state: TaskState) -> None:
    """
    Scenario: every state is filterable
      Given each TaskState
      When  a filter on it is built
      Then  a predicate exists
    """
    assert columns.task_where(TaskFilter(state=state))[0].startswith(" WHERE ")


def test_page_and_count_sql_share_the_where_clause() -> None:
    """
    Scenario: filter and paginate
      Given a filter on queue "reports" and state FAILED
      When  the page-2 query with 50 per page and the count query are built
      Then  both filter identically and the page query offsets by 50
    """
    flt = TaskFilter(queue="reports", state=TaskState.FAILED)
    page_sql, page_params = columns.tasks_page_sql(flt, 2, 50)
    count_sql, count_params = columns.tasks_count_sql(flt)
    assert "LIMIT %s OFFSET %s" in page_sql
    assert page_params == ["reports", 50, 50]
    assert count_params == ["reports"]
    assert count_sql.startswith("SELECT count(*)")
    assert " WHERE queue_name = %s AND state = 'failed'" in page_sql
    assert " WHERE queue_name = %s AND state = 'failed'" in count_sql
