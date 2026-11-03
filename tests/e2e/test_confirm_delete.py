"""E2E: red icon delete with the shared confirm dialog (st-v059-list-03).

Spec: ``docs/specs/navigation-and-list-ux.md`` ("Delete (list-03)"). One test per
story scenario, against :mod:`tests.e2e.apps.list_rows` (alice holds every Order
permission, bob holds ``view_order`` only; order #44 is referenced by a RESTRICT
foreign key, so deleting it answers 409).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from playwright.sync_api import Page, expect

if TYPE_CHECKING:
    from collections.abc import Callable

ORDERS = "/admin/order"


@pytest.fixture
def list_rows_base_url(start_server: Callable[..., str]) -> str:
    """Start :mod:`tests.e2e.apps.list_rows` and return its base URL."""
    return start_server("tests.e2e.apps.list_rows")


def _open_orders(page: Page, base_url: str, username: str = "alice") -> None:
    page.goto(f"{base_url}/admin/login")
    page.get_by_label("Username").fill(username)
    page.get_by_label("Password").fill("secret123")
    page.get_by_role("button", name="Sign in").click()
    expect(page).to_have_url(f"{base_url}/admin/")
    page.goto(base_url + ORDERS)


def _delete_icon(page: Page, number: str):
    return page.get_by_role("button", name=f"Delete {number}", exact=True)


def test_delete_asks_for_confirmation_in_a_dialog(page: Page, list_rows_base_url: str) -> None:
    """
    Scenario: delete asks for confirmation in a dialog
      Given alice holds delete_order
      When  alice clicks the delete icon on "ORD-1042"
      Then  an alertdialog "Delete ORD-1042?" opens with focus on Cancel
    """
    # Given alice holds delete_order
    _open_orders(page, list_rows_base_url)

    # When alice clicks the delete icon on "ORD-1042"
    _delete_icon(page, "ORD-1042").click()

    # Then an alertdialog "Delete ORD-1042?" opens with focus on Cancel
    dialog = page.get_by_role("alertdialog", name="Delete ORD-1042?")
    expect(dialog).to_be_visible()
    expect(dialog).to_have_accessible_description("This cannot be undone.")
    expect(dialog.get_by_role("button", name="Cancel")).to_be_focused()
    expect(page).to_have_url(f"{list_rows_base_url}{ORDERS}")


def test_cancelling_keeps_the_record(page: Page, list_rows_base_url: str) -> None:
    """
    Scenario: cancelling keeps the record
      When  alice presses Cancel (or Esc)
      Then  the dialog closes, the row remains and focus returns to the delete icon
    """
    # Given the confirm dialog is open for "ORD-1042"
    _open_orders(page, list_rows_base_url)
    _delete_icon(page, "ORD-1042").click()
    dialog = page.get_by_test_id("dialog-confirm-delete")
    expect(dialog).to_be_visible()

    # When alice presses Cancel
    dialog.get_by_role("button", name="Cancel").click()

    # Then the dialog closes, the row remains and focus returns to the delete icon
    expect(dialog).to_be_hidden()
    expect(page.get_by_test_id("list-row")).to_have_count(3)
    expect(_delete_icon(page, "ORD-1042")).to_be_focused()

    # When alice opens it again and presses Esc
    _delete_icon(page, "ORD-1042").click()
    expect(dialog).to_be_visible()
    page.keyboard.press("Escape")

    # Then the dialog closes the same way
    expect(dialog).to_be_hidden()
    expect(page.get_by_test_id("list-row")).to_have_count(3)
    expect(_delete_icon(page, "ORD-1042")).to_be_focused()


def test_confirming_deletes_and_reloads_the_list(page: Page, list_rows_base_url: str) -> None:
    """
    Scenario: confirming deletes and reloads the list
      When  alice confirms
      Then  the order is deleted and the list reloads without it
    """
    # Given the confirm dialog is open for "ORD-1043"
    _open_orders(page, list_rows_base_url)
    _delete_icon(page, "ORD-1043").click()
    dialog = page.get_by_role("alertdialog", name="Delete ORD-1043?")
    expect(dialog).to_be_visible()

    # When alice confirms
    dialog.get_by_role("button", name="Delete").click()

    # Then the order is deleted and the list reloads without it
    expect(page.get_by_test_id("list-row")).to_have_count(2)
    expect(page.get_by_test_id("list-table")).not_to_contain_text("ORD-1043")
    expect(page).to_have_url(f"{list_rows_base_url}{ORDERS}")
    detail = page.request.get(f"{list_rows_base_url}{ORDERS}/43")
    assert detail.status == 404


def test_users_without_delete_order_see_no_delete_icon(page: Page, list_rows_base_url: str) -> None:
    """
    Scenario: users without delete_order see no delete icon
      Given bob lacks delete_order
      When  bob opens the order list
      Then  no row-delete-btn is rendered
    """
    # Given bob lacks delete_order
    # When bob opens the order list
    _open_orders(page, list_rows_base_url, username="bob")

    # Then no row-delete-btn is rendered
    expect(page.get_by_test_id("list-row")).to_have_count(3)
    expect(page.get_by_test_id("row-delete-btn")).to_have_count(0)


def test_a_protected_record_shows_the_error_toast(page: Page, list_rows_base_url: str) -> None:
    """
    Scenario: a protected record shows the error toast
      Given the order is referenced by a PROTECT foreign key
      When  alice confirms its deletion
      Then  the dialog closes and the 409 error toast is shown
    """
    # Given order "ORD-1044" is referenced by a shipment (RESTRICT foreign key)
    _open_orders(page, list_rows_base_url)
    _delete_icon(page, "ORD-1044").click()
    dialog = page.get_by_role("alertdialog", name="Delete ORD-1044?")

    # When alice confirms its deletion
    dialog.get_by_role("button", name="Delete").click()

    # Then the dialog closes and the 409 error toast is shown
    expect(dialog).to_be_hidden()
    toast = page.get_by_test_id("error-toast")
    expect(toast).to_be_visible()
    expect(toast).to_contain_text("other records still reference it")
    # And the row remains
    expect(page.get_by_test_id("list-row")).to_have_count(3)
