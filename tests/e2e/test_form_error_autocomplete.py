"""E2E: a 422 form re-render keeps the autocomplete widget working.

A failed submit re-renders the form body through HTMX. The autocomplete
widget must come back as one search combobox (the native ``<select>`` stays
hidden behind it) and its search must still fetch choices. Runs against the
ERP example, whose invoice form has a ``Customer`` autocomplete.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from playwright.sync_api import Page, expect

if TYPE_CHECKING:
    from collections.abc import Callable


@pytest.fixture
def erp_base_url(start_server: Callable[..., str]) -> str:
    """Start the ERP demo app and return the base URL."""
    return start_server("examples.erp.main", ready_path="/")


def _open_invoice_form(page: Page, base_url: str) -> None:
    page.goto(base_url + "/admin/login")
    page.get_by_label("Username").fill("admin")
    page.get_by_label("Password").fill("admin")
    page.get_by_role("button", name="Sign in").click()
    expect(page).to_have_url(base_url + "/admin/")
    page.goto(base_url + "/admin/invoice/create")


def _submit_empty(page: Page) -> None:
    with page.expect_response(lambda r: r.request.method == "POST") as response:
        page.get_by_role("button", name="Create", exact=True).click()
    assert response.value.status == 422
    expect(page.get_by_test_id("error-summary")).to_be_visible()


def test_the_customer_picker_stays_one_combobox_after_a_failed_submit(
    page: Page, erp_base_url: str
) -> None:
    """
    Scenario: the customer picker stays one combobox after a failed submit
      Given the invoice create form is open
      When  the user submits it empty
      Then  the form shows the field errors
      And   Customer is a single search combobox, with no second select under it
    """
    # Given the invoice create form is open
    _open_invoice_form(page, erp_base_url)

    # When the user submits it empty
    _submit_empty(page)

    # Then the form shows the field errors
    expect(page.get_by_test_id("customer_id-errors")).to_be_visible()
    # And Customer is a single search combobox, with no second select under it
    customer = page.get_by_role("combobox", name="Customer")
    expect(customer).to_have_count(1)
    expect(customer).to_have_attribute("data-testid", "autocomplete-customer_id")
    expect(page.get_by_test_id("autocomplete-select-customer_id")).to_have_attribute(
        "aria-hidden", "true"
    )


def test_searching_customers_still_works_after_a_failed_submit(
    page: Page, erp_base_url: str
) -> None:
    """
    Scenario: searching customers still works after a failed submit
      Given the invoice create form was submitted empty
      When  the user types a customer name into the Customer search
      Then  the matching customer is offered
    """
    # Given the invoice create form was submitted empty
    _open_invoice_form(page, erp_base_url)
    _submit_empty(page)
    select = page.get_by_test_id("autocomplete-select-customer_id")
    # The re-rendered widget is enhanced once htmx settles the swap.
    expect(select).to_have_attribute("aria-hidden", "true")
    name = select.locator("option:not([value=''])").first.text_content() or ""

    # When the user types a customer name into the Customer search
    with page.expect_response(lambda r: "/choices/customer" in r.url and "q=" in r.url):
        page.get_by_test_id("autocomplete-customer_id").press_sequentially(name[:4])

    # Then the matching customer is offered
    expect(page.get_by_role("option", name=name).first).to_be_attached()
