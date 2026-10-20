"""End-to-end tests for bulk actions with parameter forms (H3, v0.5.5).

Spec: ``docs/specs/bulk-actions.md`` — one test per BDD scenario, named after
it. Design: ``docs/design/system/components/BulkActionFlow``. Inline
``# Given / # When / # Then`` comments are mandatory (BDD conventions).

Selectors follow ``CLAUDE.md`` (E2E Selector Convention):
``get_by_role`` > ``get_by_label`` > ``get_by_text`` > ``get_by_test_id``.
``ha-*`` CSS classes are styling-only and never used as selectors.

The companion app (``tests.e2e.apps.bulk_actions``) seeds orders 1, 2 and 3
and the superuser ``alice``; ``/_test/calls`` reports what the handlers and
``adapter.delete`` were called with, so "the handler is not invoked" and
"delete was called for ids 1 and 3 only" are asserted, not inferred.
"""

from __future__ import annotations

from http import HTTPStatus

from playwright.sync_api import Locator, Page, expect

from tests.e2e.conftest import csrf_headers

ORDER_LIST = "/admin/order"


def _login(page: Page, base_url: str) -> None:
    """Sign in as the superuser and land on the dashboard."""
    page.goto(f"{base_url}/admin/login")
    page.get_by_label("Username").fill("alice")
    page.get_by_label("Password").fill("secret123")
    page.get_by_role("button", name="Sign in").click()
    expect(page).to_have_url(f"{base_url}/admin/")


def _open_list(page: Page, base_url: str) -> None:
    _login(page, base_url)
    page.goto(base_url + ORDER_LIST)
    expect(page.get_by_test_id("list-row")).to_have_count(3)


def _select_rows(page: Page, *ids: int) -> None:
    for pk in ids:
        page.get_by_role("checkbox", name=f"Select {pk}", exact=True).check()


def _run(page: Page, action: str) -> None:
    page.get_by_label("Action for selected rows").select_option(action)
    page.get_by_role("button", name="Run").click()


def _hidden_ids(form: Locator) -> list[str]:
    """Values of the hidden ``ids`` inputs a form carries (they have no role)."""
    return form.locator('input[type="hidden"][name="ids"]').evaluate_all(
        "inputs => inputs.map(input => input.value)"
    )


def _calls(page: Page, base_url: str) -> dict:
    return page.request.get(f"{base_url}/_test/calls").json()


def test_bulk_action_with_no_selection_shows_warning(page: Page, bulk_base_url: str) -> None:
    """
    Scenario: bulk action with no selection re-renders list with warning
      Given a ModelAdmin with @action(label="Archive", bulk=True, requires_selection=True)
      When  the user clicks "Run" on the list view with no rows checked
      Then  the list re-renders with a flash "Select at least one row"
      And   the handler is not invoked
    """
    # Given the order list with its bulk bar and nothing checked
    _open_list(page, bulk_base_url)
    expect(page.get_by_test_id("bulk-bar")).to_be_visible()
    expect(page.get_by_test_id("bulk-warning")).to_be_hidden()

    # When the user picks Archive and presses Run with no rows checked
    _run(page, "archive")

    # Then the bar explains instead of sending, and the list is still there
    warning = page.get_by_role("alert")
    expect(warning).to_be_visible()
    expect(warning).to_have_text("Select at least one row, then press Run.")
    expect(page.get_by_test_id("list-row")).to_have_count(3)
    expect(page.get_by_test_id("bulk-result")).to_have_count(0)
    # And the handler is not invoked
    assert _calls(page, bulk_base_url)["calls"] == []


def test_bulk_action_with_param_form_prompts_before_running(page: Page, bulk_base_url: str) -> None:
    """
    Scenario: bulk action with param form prompts before running
      Given a ModelAdmin with @action(label="Reassign", bulk=True, form=ReassignParams)
      When  the user selects 3 rows and clicks Run on action "reassign"
      Then  the response renders a Pydantic-derived form at /admin/orders/actions/reassign/bulk
      And   the form preserves the selected ids in hidden inputs
    """
    # Given three selected rows
    _open_list(page, bulk_base_url)
    _select_rows(page, 1, 2, 3)
    expect(page.get_by_test_id("bulk-count")).to_have_text("3 selected")

    # When the user runs "reassign"
    with page.expect_request(f"**{ORDER_LIST}/actions/reassign/bulk") as request_info:
        _run(page, "reassign")
    assert request_info.value.method == "POST"

    # Then the parameter form opens in the dialog, titled with verb and count
    form = page.get_by_test_id("bulk-form")
    expect(form).to_be_visible()
    expect(page.get_by_role("heading", name="Reassign 3 rows")).to_be_visible()
    expect(form.get_by_label("Operator")).to_be_visible()
    expect(form.get_by_role("button", name="Reassign 3 rows")).to_be_visible()
    # And the selected ids ride along as hidden inputs
    assert _hidden_ids(form) == ["1", "2", "3"]
    # And nothing has run yet
    assert _calls(page, bulk_base_url)["calls"] == []


def test_bulk_action_with_valid_params_runs_over_selected_rows(
    page: Page, bulk_base_url: str
) -> None:
    """
    Scenario: bulk action with valid params runs over selected rows
      Given the same ReassignParams form with field operator: int
      When  the user posts the form with operator=42 and ids=[1,2,3]
      Then  the handler runs three times — one per id — with form data validated
      And   the per-row outcome page lists 3 rows with status "ok"
    """
    # Given the parameter form for three rows
    _open_list(page, bulk_base_url)
    _select_rows(page, 1, 2, 3)
    _run(page, "reassign")
    form = page.get_by_test_id("bulk-form")
    expect(form).to_be_visible()

    # When the user fills operator=42 and confirms
    form.get_by_label("Operator").fill("42")
    form.get_by_role("button", name="Reassign 3 rows").click()

    # Then the result lands in the list, the dialog closes
    result = page.get_by_test_id("bulk-result")
    expect(result).to_be_visible()
    expect(page.get_by_test_id("popup-root")).to_be_empty()
    expect(result.get_by_role("status")).to_have_text("All 3 rows done.")
    # And every row is "ok" (shown as Done)
    expect(result.get_by_test_id("bulk-result-row")).to_have_count(3)
    for pk in (1, 2, 3):
        expect(result.get_by_test_id(f"bulk-result-status-{pk}")).to_have_text("Done")
    expect(result.get_by_test_id("bulk-retry-form")).to_have_count(0)
    # And the handler ran once per id with the validated params
    calls = _calls(page, bulk_base_url)["calls"]
    assert calls == [{"action": "reassign", "id": pk, "operator": 42} for pk in (1, 2, 3)]


def test_per_row_failure_is_surfaced(page: Page, bulk_base_url: str) -> None:
    """
    Scenario: per-row failure is surfaced without aborting the bulk run
      Given the handler raises HTTPException(403) for id=2 only
      When  the user posts the bulk form with ids=[1,2,3]
      Then  the result page shows ok / failed / ok for ids 1, 2, 3 respectively
      And   the failed row carries the error message "permission denied"
      And   the user sees a "Retry failures" link that re-submits with ids=[2]

    A 403 raised by the handler renders as the "forbidden" status (spec: Edge
    Cases), which the design shows as the word Forbidden with a square marker.
    """
    # Given archive raises 403 for id 2
    assert page.request.post(f"{bulk_base_url}/_test/forbid?id=2").ok
    _open_list(page, bulk_base_url)
    _select_rows(page, 1, 2, 3)

    # When the user runs the formless archive over the three rows
    _run(page, "archive")

    # Then rows 1 and 3 are done and row 2 is not, listed first
    result = page.get_by_test_id("bulk-result")
    expect(result).to_be_visible()
    expect(result.get_by_test_id("bulk-result-row")).to_have_count(3)
    expect(result.get_by_test_id("bulk-result-status-1")).to_have_text("Done")
    expect(result.get_by_test_id("bulk-result-status-2")).to_have_text("Forbidden")
    expect(result.get_by_test_id("bulk-result-status-3")).to_have_text("Done")
    expect(result.get_by_test_id("bulk-result-row").first).to_contain_text("2")
    expect(result.get_by_role("status")).to_have_text("2 of 3 rows done. 1 not allowed.")
    # And the problem row carries the handler's message
    expect(result.get_by_test_id("bulk-result-row").first).to_contain_text("permission denied")
    # And the run was not aborted: the other rows were archived
    assert _calls(page, bulk_base_url)["deleted"] == [1, 3]
    # And "Retry failures" re-submits only id 2
    retry = result.get_by_test_id("bulk-retry-form")
    expect(retry.get_by_role("button", name="Retry failures (1)")).to_be_visible()
    assert _hidden_ids(retry) == ["2"]


def test_requires_selection_blocks_zero_row_post(page: Page, bulk_base_url: str) -> None:
    """
    Scenario: requires_selection blocks zero-row submission server-side
      Given the user crafts a POST to /admin/orders/actions/archive/bulk with ids=[]
      When  the request reaches the bulk endpoint
      Then  the response is 400 with detail "Selection required"
      And   the handler is not invoked
    """
    # Given a signed-in session (the crafted POST still needs the CSRF pair)
    _open_list(page, bulk_base_url)

    # When a POST with no ids bypasses the bar
    response = page.request.post(
        f"{bulk_base_url}{ORDER_LIST}/actions/archive/bulk",
        form={"bulk-action": "archive"},
        headers=csrf_headers(page),
    )

    # Then the endpoint refuses it
    assert response.status == HTTPStatus.BAD_REQUEST
    assert "Selection required" in response.text()
    # And the handler is not invoked
    assert _calls(page, bulk_base_url) == {"calls": [], "deleted": []}


def test_object_permission_enforced_per_row(page: Page, bulk_base_url: str) -> None:
    """
    Scenario: object-level permission is enforced per row
      Given an ObjectPermissionChecker that denies "archive" on id=2
      When  the user posts a bulk archive with ids=[1,2,3]
      Then  the result page shows ok / forbidden / ok
      And   adapter.delete was called for ids 1 and 3 only
    """
    # Given the checker denies action_archive on order 2
    assert page.request.post(f"{bulk_base_url}/_test/deny?id=2").ok
    _open_list(page, bulk_base_url)

    # When the user selects every row on the page and runs archive
    page.get_by_role("checkbox", name="Select all rows on this page").check()
    expect(page.get_by_test_id("bulk-count")).to_have_text("3 selected")
    _run(page, "archive")

    # Then rows 1 and 3 are done and row 2 is forbidden
    result = page.get_by_test_id("bulk-result")
    expect(result).to_be_visible()
    expect(result.get_by_test_id("bulk-result-status-1")).to_have_text("Done")
    expect(result.get_by_test_id("bulk-result-status-2")).to_have_text("Forbidden")
    expect(result.get_by_test_id("bulk-result-status-3")).to_have_text("Done")
    expect(result.get_by_test_id("bulk-result-row").first).to_contain_text("Permission denied")
    # And the handler never reached row 2: delete ran for 1 and 3 only
    calls = _calls(page, bulk_base_url)
    assert calls["deleted"] == [1, 3]
    assert [call["id"] for call in calls["calls"]] == [1, 3]
