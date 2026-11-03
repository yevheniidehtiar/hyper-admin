"""E2E: clickable list rows and Edit on the detail page (st-v059-list-02).

Spec: ``docs/specs/navigation-and-list-ux.md`` ("Rows (list-02)"). One test per
story scenario, against :mod:`tests.e2e.apps.list_rows` (alice holds every Order
permission, bob holds ``view_order`` only).
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING

import pytest
from playwright.sync_api import Locator, Page, expect

if TYPE_CHECKING:
    from collections.abc import Callable

ORDERS = "/admin/order"


@pytest.fixture
def list_rows_base_url(start_server: Callable[..., str]) -> str:
    """Start :mod:`tests.e2e.apps.list_rows` and return its base URL."""
    return start_server("tests.e2e.apps.list_rows")


def _login(page: Page, base_url: str, username: str) -> None:
    page.goto(f"{base_url}/admin/login")
    page.get_by_label("Username").fill(username)
    page.get_by_label("Password").fill("secret123")
    page.get_by_role("button", name="Sign in").click()
    expect(page).to_have_url(f"{base_url}/admin/")


def _row(page: Page, number: str):
    return page.get_by_test_id("list-row").filter(has_text=number)


def _click_on(page: Page, target: Locator) -> None:
    """Click the middle of ``target`` with the mouse, as a person would.

    ``Locator.click`` refuses when another element receives the click; here
    that is the point: the stretched row link covers the plain cells.
    """
    box = target.bounding_box()
    assert box is not None
    page.mouse.click(box["x"] + box["width"] / 2, box["y"] + box["height"] / 2)


def test_clicking_a_row_opens_the_edit_page_for_an_editor(
    page: Page, list_rows_base_url: str
) -> None:
    """
    Scenario: clicking a row opens the edit page for an editor
      Given alice holds change_order
      When  alice clicks the row of order 42 outside its controls
      Then  /admin/order/42/edit opens
    """
    # Given alice holds change_order
    _login(page, list_rows_base_url, "alice")
    page.goto(list_rows_base_url + ORDERS)

    # When alice clicks the row of order 42 outside its controls (the customer cell)
    _click_on(page, _row(page, "ORD-1042").get_by_role("cell", name="Acme"))

    # Then /admin/order/42/edit opens
    expect(page).to_have_url(f"{list_rows_base_url}{ORDERS}/42/edit")
    expect(page.get_by_test_id("model-form")).to_be_visible()


def test_clicking_a_row_opens_the_detail_page_for_a_read_only_user(
    page: Page, list_rows_base_url: str
) -> None:
    """
    Scenario: clicking a row opens the detail page for a read-only user
      Given bob holds view_order only
      When  bob clicks the row of order 42
      Then  /admin/order/42 opens
    """
    # Given bob holds view_order only
    _login(page, list_rows_base_url, "bob")
    page.goto(list_rows_base_url + ORDERS)

    # When bob clicks the row of order 42
    _click_on(page, _row(page, "ORD-1042").get_by_role("cell", name="Acme"))

    # Then /admin/order/42 opens
    expect(page).to_have_url(f"{list_rows_base_url}{ORDERS}/42")
    expect(page.get_by_test_id("detail-fields")).to_be_visible()
    # And the detail page offers no Edit to a read-only user
    expect(page.get_by_test_id("detail-edit-link")).to_have_count(0)


def test_row_controls_do_not_trigger_the_row_link(page: Page, list_rows_base_url: str) -> None:
    """
    Scenario: row controls do not trigger the row link
      Given Order has a bulk action and list_editable=["status"]
      When  the user ticks the checkbox or clicks the status cell
      Then  the row is selected or the inline editor opens, without navigation
    """
    # Given Order has a bulk action and list_editable=["status"]
    _login(page, list_rows_base_url, "alice")
    page.goto(list_rows_base_url + ORDERS)
    list_url = page.url
    row = _row(page, "ORD-1042")

    # When the user ticks the checkbox
    row.get_by_role("checkbox", name="Select 42").click()

    # Then the row is selected without navigation
    expect(row.get_by_role("checkbox", name="Select 42")).to_be_checked()
    expect(page).to_have_url(list_url)

    # When the user clicks the status cell
    page.get_by_test_id("cell-value-status-42").click()
    page.get_by_test_id("cell-edit-status-42").click()

    # Then the inline editor opens without navigation
    expect(page.get_by_test_id("cell-editor-status-42")).to_be_visible()
    expect(page).to_have_url(list_url)


def test_the_row_link_works_as_a_link(page: Page, list_rows_base_url: str) -> None:
    """
    Scenario: the row link works as a link
      When  the user middle-clicks a row's title link
      Then  the record opens in a new tab
    """
    # Given alice is on the order list
    _login(page, list_rows_base_url, "alice")
    page.goto(list_rows_base_url + ORDERS)
    list_url = page.url

    # When the user middle-clicks a row's title link
    with page.context.expect_page() as new_tab:
        page.get_by_role("link", name="ORD-1042", exact=True).click(button="middle")

    # Then the record opens in a new tab
    tab = new_tab.value
    tab.wait_for_load_state()
    expect(tab).to_have_url(f"{list_rows_base_url}{ORDERS}/42/edit")
    # And the list stays open in the original tab
    expect(page).to_have_url(list_url)
    tab.close()


def test_the_detail_page_offers_edit_to_editors(page: Page, list_rows_base_url: str) -> None:
    """
    Scenario: the detail page offers Edit to editors
      Given alice holds change_order
      When  alice opens /admin/order/42
      Then  an "Edit" link (detail-edit-link) leads to /admin/order/42/edit
    """
    # Given alice holds change_order
    _login(page, list_rows_base_url, "alice")

    # When alice opens /admin/order/42
    page.goto(f"{list_rows_base_url}{ORDERS}/42")

    # Then an "Edit" link (detail-edit-link) leads to /admin/order/42/edit
    edit = page.get_by_test_id("detail-edit-link")
    expect(edit).to_have_text("Edit")
    edit.click()
    expect(page).to_have_url(re.compile(rf"{ORDERS}/42/edit$"))
