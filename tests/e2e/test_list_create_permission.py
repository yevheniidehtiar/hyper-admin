"""E2E: the list page offers "Create" only to users who may add records.

Against :mod:`tests.e2e.apps.list_rows`: alice holds every Order permission,
bob holds ``view_order`` only. The create form answers 403 without
``add_order``, so bob must not be offered a button that leads there.
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


def _login(page: Page, base_url: str, username: str) -> None:
    page.goto(f"{base_url}/admin/login")
    page.get_by_label("Username").fill(username)
    page.get_by_label("Password").fill("secret123")
    page.get_by_role("button", name="Sign in").click()
    expect(page).to_have_url(f"{base_url}/admin/")


def test_a_user_without_add_permission_sees_no_create_button(
    page: Page, list_rows_base_url: str
) -> None:
    """
    Scenario: a user without add permission sees no Create button
      Given bob holds view_order but not add_order
      When  bob opens the order list
      Then  the list shows its rows
      And   no "Create order" link is offered
    """
    # Given bob holds view_order but not add_order
    _login(page, list_rows_base_url, "bob")

    # When bob opens the order list
    page.goto(list_rows_base_url + ORDERS)

    # Then the list shows its rows
    expect(page.get_by_test_id("list-row").first).to_be_visible()
    # And no "Create order" link is offered
    expect(page.get_by_test_id("create-link")).to_have_count(0)


def test_a_user_with_add_permission_opens_the_create_form_from_the_list(
    page: Page, list_rows_base_url: str
) -> None:
    """
    Scenario: a user with add permission opens the create form from the list
      Given alice holds add_order
      When  alice clicks "Create order" on the order list
      Then  the create form opens
    """
    # Given alice holds add_order
    _login(page, list_rows_base_url, "alice")
    page.goto(list_rows_base_url + ORDERS)

    # When alice clicks "Create order" on the order list
    page.get_by_test_id("create-link").click()

    # Then the create form opens
    expect(page).to_have_url(f"{list_rows_base_url}{ORDERS}/create")
    expect(page.get_by_test_id("model-form")).to_be_visible()
