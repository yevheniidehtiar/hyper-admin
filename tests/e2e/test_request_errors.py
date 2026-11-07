"""E2E: a failed form submit shows an alert (st-ux-erp-03), against the form_safety app."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from playwright.sync_api import Page, expect

if TYPE_CHECKING:
    from collections.abc import Callable

ORDER_EDIT = "/admin/order/42/edit"


@pytest.fixture
def base_url_(start_server: Callable[..., str]) -> str:
    """Start :mod:`tests.e2e.apps.form_safety` and return its base URL."""
    return start_server("tests.e2e.apps.form_safety")


def _open_edit(page: Page, base: str) -> None:
    page.goto(f"{base}/admin/login")
    page.get_by_label("Username").fill("alice")
    page.get_by_label("Password").fill("secret123")
    page.get_by_role("button", name="Sign in").click()
    expect(page).to_have_url(f"{base}/admin/")
    page.goto(base + ORDER_EDIT)


def test_server_error_on_save_is_visible(page: Page, base_url_: str) -> None:
    """
    Scenario: server error on save is visible
      Given the server answers a form submit with HTTP 500
      When  the user clicks Update
      Then  an alert says the record was not saved and the edits are kept
      And   the alert is announced to screen readers (role=alert)
    """
    # Given the server answers a form submit with HTTP 500
    _open_edit(page, base_url_)
    page.route(
        "**/admin/order/42",
        lambda route: (
            route.fulfill(status=500, body="boom")
            if route.request.method == "PUT"
            else route.continue_()
        ),
    )
    field = page.get_by_label("Customer")
    field.fill("Edited Corp")

    # When the user clicks Update
    page.get_by_test_id("form-actions").get_by_role("button", name="Update").click()

    # Then an alert says the record was not saved and the edits are kept
    alert = page.get_by_role("alert").filter(has_text="Not saved")
    expect(alert).to_contain_text("Your edits are kept")
    expect(alert).to_be_focused()
    expect(page).to_have_url(base_url_ + ORDER_EDIT)
    expect(field).to_have_value("Edited Corp")


def test_network_failure_on_save_is_visible(page: Page, base_url_: str) -> None:
    """
    Scenario: network failure on save is visible
      Given the connection drops during a form submit
      When  the user clicks Update
      Then  an alert says the server could not be reached and the edits are kept
    """
    # Given the connection drops during a form submit
    _open_edit(page, base_url_)
    page.route(
        "**/admin/order/42",
        lambda route: route.abort() if route.request.method == "PUT" else route.continue_(),
    )
    field = page.get_by_label("Customer")
    field.fill("Edited Corp")

    # When the user clicks Update
    page.get_by_test_id("form-actions").get_by_role("button", name="Update").click()

    # Then an alert says the server could not be reached and the edits are kept
    expect(page.get_by_role("alert").filter(has_text="Could not reach the server")).to_be_visible()
    expect(field).to_have_value("Edited Corp")


def test_failed_read_request_does_not_claim_a_save_failed(page: Page, base_url_: str) -> None:
    """
    Scenario: failed read request is not reported as a failed save
      Given the server answers an HTMX GET with HTTP 500
      When  the page issues that GET
      Then  no "Not saved" alert is shown
    """
    # Given the server answers an HTMX GET with HTTP 500
    _open_edit(page, base_url_)
    page.route("**/admin/order/42/probe", lambda route: route.fulfill(status=500, body="boom"))

    # When the page issues that GET
    page.evaluate("htmx.ajax('GET', '/admin/order/42/probe', {target: 'body', swap: 'none'})")
    page.wait_for_timeout(300)

    # Then no "Not saved" alert is shown
    expect(page.get_by_test_id("request-error-toast")).to_have_count(0)
