"""E2E: the tasks plugin's monitoring UI and operator actions (story #758).

SDD ``docs/specs/plugin-tasks.md``. Runs against :mod:`tests.e2e.apps.tasks_monitoring`, which
mounts the plugin over a seeded in-memory backend. One test per scenario, named after it.
Uses accessibility-first selectors per CLAUDE.md E2E Selector Convention.
"""

from playwright.sync_api import Dialog, Page, expect


def _login(page: Page, base_url: str, username: str) -> None:
    page.goto(f"{base_url}/admin/login")
    page.get_by_label("Username").fill(username)
    page.get_by_label("Password").fill("secret123")
    page.get_by_role("button", name="Sign in").click()
    expect(page).to_have_url(f"{base_url}/admin/")


def _confirm_next_dialog(page: Page, seen: list[str]) -> None:
    """Accept the next confirmation dialog, recording its message in ``seen``."""

    def accept(dialog: Dialog) -> None:
        seen.append(dialog.message)
        dialog.accept()

    page.once("dialog", accept)


def test_dashboard_lists_every_queue_with_counts(page: Page, tasks_base_url: str) -> None:
    """Scenario: dashboard lists every queue with counts."""
    # Given the seeded app with queues reports and emails
    # And superuser alice is signed in
    _login(page, tasks_base_url, "alice")

    # When she opens the Tasks dashboard from the sidebar
    page.get_by_test_id("nav-tasks-dashboard").click()

    # Then one row per queue shows its counters
    expect(page).to_have_url(f"{tasks_base_url}/admin/tasks/")
    expect(page.get_by_test_id("page-header").get_by_role("heading", name="Tasks")).to_be_visible()
    expect(page.get_by_test_id("tasks-queue-row")).to_have_count(2)
    reports = page.get_by_role("row", name="reports")
    expect(reports.get_by_test_id("tasks-queue-ready")).to_have_text("1")
    expect(reports.get_by_test_id("tasks-queue-running")).to_have_text("1")
    expect(reports.get_by_test_id("tasks-queue-failed")).to_have_text("1")


def test_operator_finds_a_failed_task_by_state_filter(page: Page, tasks_base_url: str) -> None:
    """Scenario: operator finds a failed task by state filter."""
    # Given alice is signed in on the task list
    _login(page, tasks_base_url, "alice")
    page.goto(f"{tasks_base_url}/admin/tasks/list")
    expect(page.get_by_test_id("tasks-list-row")).to_have_count(4)

    # When she filters by the failed state
    page.get_by_label("State").select_option("failed")
    page.get_by_role("button", name="Apply filters").click()

    # Then only the failed task is listed and it opens its detail page
    expect(page.get_by_test_id("tasks-list-row")).to_have_count(1)
    page.get_by_role("link", name="F1").click()
    expect(page.get_by_test_id("tasks-detail-state")).to_have_text("failed")
    expect(page.get_by_test_id("tasks-error")).to_contain_text("boom")


def test_operator_retries_a_failed_task(page: Page, tasks_base_url: str) -> None:
    """Scenario: operator retries a failed task."""
    # Given the e2e app with a seeded InMemoryTaskBackend holding failed task F1
    # And alice, who holds manage_tasks, is on its detail page
    _login(page, tasks_base_url, "alice")
    page.goto(f"{tasks_base_url}/admin/tasks/t/F1")
    expect(page.get_by_test_id("tasks-detail-state")).to_have_text("failed")
    dialogs: list[str] = []
    _confirm_next_dialog(page, dialogs)

    # When she clicks Retry and confirms
    page.get_by_role("button", name="Retry").click()

    # Then the detail shows pending and a success message
    expect(page.get_by_text("The task was queued for retry.")).to_be_visible()
    expect(page.get_by_test_id("tasks-detail-state")).to_have_text("pending")
    expect(page.get_by_role("button", name="Retry")).to_have_count(0)
    assert dialogs == ["Retry task F1?"]


def test_operator_cancels_a_pending_task(page: Page, tasks_base_url: str) -> None:
    """Scenario: operator cancels a pending task."""
    # Given alice is on the detail page of pending task P1
    _login(page, tasks_base_url, "alice")
    page.goto(f"{tasks_base_url}/admin/tasks/t/P1")
    dialogs: list[str] = []
    _confirm_next_dialog(page, dialogs)

    # When she clicks Cancel and confirms
    page.get_by_role("button", name="Cancel").click()

    # Then the task is cancelled and a success message is shown
    expect(page.get_by_text("The task was cancelled.")).to_be_visible()
    expect(page.get_by_test_id("tasks-detail-state")).to_have_text("cancelled")
    assert dialogs == ["Cancel task P1?"]


def test_declining_the_confirmation_changes_nothing(page: Page, tasks_base_url: str) -> None:
    """Scenario: declining the confirmation changes nothing."""
    # Given alice is on the detail page of failed task F1
    _login(page, tasks_base_url, "alice")
    page.goto(f"{tasks_base_url}/admin/tasks/t/F1")
    page.once("dialog", lambda dialog: dialog.dismiss())

    # When she clicks Retry and dismisses the confirmation
    page.get_by_role("button", name="Retry").click()

    # Then the task is still failed and no message is shown
    expect(page.get_by_test_id("tasks-detail-state")).to_have_text("failed")
    expect(page.get_by_text("The task was queued for retry.")).to_have_count(0)


def test_operator_pauses_and_resumes_a_queue(page: Page, tasks_base_url: str) -> None:
    """Scenario: operator pauses and resumes a queue."""
    # Given alice is on the dashboard and the reports queue is running
    _login(page, tasks_base_url, "alice")
    page.goto(f"{tasks_base_url}/admin/tasks/")
    reports = page.get_by_role("row", name="reports")
    expect(reports.get_by_test_id("tasks-queue-paused")).to_have_count(0)
    _confirm_next_dialog(page, [])

    # When she pauses the reports queue and confirms
    reports.get_by_role("button", name="Pause").click()

    # Then the dashboard shows reports as paused
    expect(page.get_by_text("The queue was paused.")).to_be_visible()
    expect(reports.get_by_test_id("tasks-queue-paused")).to_be_visible()

    # And resuming it clears the paused marker
    _confirm_next_dialog(page, [])
    reports.get_by_role("button", name="Resume").click()
    expect(page.get_by_text("The queue was resumed.")).to_be_visible()
    expect(reports.get_by_test_id("tasks-queue-paused")).to_have_count(0)


def test_operator_pauses_and_resumes_schedules(page: Page, tasks_base_url: str) -> None:
    """Scenario: operator pauses an active schedule and resumes a paused one."""
    # Given alice is on the schedules page with nightly active and weekly paused
    _login(page, tasks_base_url, "alice")
    page.goto(f"{tasks_base_url}/admin/tasks/schedules")
    nightly = page.get_by_role("row", name="nightly")
    weekly = page.get_by_role("row", name="weekly")
    expect(nightly.get_by_test_id("tasks-schedule-state")).to_have_text("active")
    expect(weekly.get_by_test_id("tasks-schedule-state")).to_have_text("paused")

    # When she pauses nightly and confirms
    _confirm_next_dialog(page, [])
    nightly.get_by_role("button", name="Pause").click()

    # Then nightly is paused
    expect(page.get_by_text("The schedule was paused.")).to_be_visible()
    expect(nightly.get_by_test_id("tasks-schedule-state")).to_have_text("paused")

    # And resuming weekly makes it active
    _confirm_next_dialog(page, [])
    weekly.get_by_role("button", name="Resume").click()
    expect(page.get_by_text("The schedule was resumed.")).to_be_visible()
    expect(weekly.get_by_test_id("tasks-schedule-state")).to_have_text("active")


def test_view_only_user_sees_no_action_buttons(page: Page, tasks_base_url: str) -> None:
    """Scenario: a view_tasks-only user sees no action buttons."""
    # Given the viewer, who holds view_tasks but not manage_tasks, is signed in
    _login(page, tasks_base_url, "viewer")

    # When they open the dashboard, a failed task and the schedules
    page.goto(f"{tasks_base_url}/admin/tasks/")
    expect(page.get_by_test_id("tasks-queue-row")).to_have_count(2)
    # Then no action control is rendered on any of them
    expect(page.get_by_role("button", name="Pause")).to_have_count(0)
    page.goto(f"{tasks_base_url}/admin/tasks/t/F1")
    expect(page.get_by_test_id("tasks-detail-state")).to_have_text("failed")
    expect(page.get_by_role("button", name="Retry")).to_have_count(0)
    page.goto(f"{tasks_base_url}/admin/tasks/schedules")
    expect(page.get_by_test_id("tasks-schedule-row")).to_have_count(2)
    expect(page.get_by_role("button", name="Resume")).to_have_count(0)


def test_view_only_user_cannot_post_an_action(page: Page, tasks_base_url: str) -> None:
    """Scenario: a view_tasks-only user is refused a forged action request."""
    # Given the viewer is signed in on the task page, so the page carries a valid CSRF token
    _login(page, tasks_base_url, "viewer")
    page.goto(f"{tasks_base_url}/admin/tasks/t/F1")
    token = page.locator('meta[name="csrf-token"]').get_attribute("content") or ""

    # When the viewer POSTs the retry URL directly
    response = page.request.post(
        f"{tasks_base_url}/admin/tasks/t/F1/retry", headers={"X-CSRF-Token": token}
    )

    # Then 403 is returned and the task is unchanged
    assert response.status == 403
    page.goto(f"{tasks_base_url}/admin/tasks/t/F1")
    expect(page.get_by_test_id("tasks-detail-state")).to_have_text("failed")


def test_backend_refusal_shows_an_error_message(page: Page, tasks_base_url: str) -> None:
    """Scenario: a refused action shows an error message, not a server error."""
    # Given alice has the detail page of pending task P1 open
    _login(page, tasks_base_url, "alice")
    page.goto(f"{tasks_base_url}/admin/tasks/t/P1")
    token = page.locator('meta[name="csrf-token"]').get_attribute("content") or ""

    # When the task is retried although it is not retryable (a race with another operator)
    response = page.request.post(
        f"{tasks_base_url}/admin/tasks/t/P1/retry", headers={"X-CSRF-Token": token}
    )

    # Then she is sent back to the task with an error message
    assert response.status == 200
    assert response.url.endswith("/admin/tasks/t/P1?notice=failed")
    page.goto(response.url)
    expect(page.get_by_text("The action could not be completed.", exact=False)).to_be_visible()
    expect(page.get_by_test_id("tasks-detail-state")).to_have_text("pending")
