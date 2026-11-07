"""End-to-end tests for the single FK combobox (st-ux-erp-02, st-ux-erp-12).

Uses the autocomplete fixture app (``tests.e2e.apps.autocomplete``): contacts
1-60 and invoice 1 whose Customer is contact 60, past the 50-option preload
window. Selectors follow ``CLAUDE.md``: role > label > text > test id.
"""

from __future__ import annotations

from playwright.sync_api import Page, expect

INVOICE_EDIT = "/admin/invoice/1/edit"
INVOICE_CREATE = "/admin/invoice/create"


def _login(page: Page, base_url: str) -> None:
    page.goto(f"{base_url}/admin/login")
    page.get_by_label("Username").fill("alice")
    page.get_by_label("Password").fill("secret123")
    page.get_by_role("button", name="Sign in").click()
    expect(page).to_have_url(f"{base_url}/admin/")


def test_current_fk_value_is_shown_even_when_not_preloaded(
    page: Page, autocomplete_base_url: str
) -> None:
    """
    Scenario: current FK value is shown even when not preloaded
      Given an invoice whose customer is not in the preloaded option window
      When  the user opens its edit page
      Then  the Customer field shows that customer as selected
      And   saving without changes succeeds
    """
    # Given an invoice whose customer (contact 60) is past the 50-option window
    _login(page, autocomplete_base_url)

    # When the user opens its edit page
    page.goto(autocomplete_base_url + INVOICE_EDIT)

    # Then the Customer field shows that customer as selected
    customer = page.get_by_role("combobox", name="Customer")
    expect(customer).to_have_value("Contact 60")
    expect(page.get_by_test_id("autocomplete-select-contact_id")).to_have_value("60")

    # And saving without changes succeeds
    page.get_by_role("button", name="Update").click()
    expect(page.get_by_text("Input should be a valid integer")).to_have_count(0)
    expect(page).not_to_have_url(autocomplete_base_url + INVOICE_EDIT)


def test_a_single_searchable_combobox(page: Page, autocomplete_base_url: str) -> None:
    """
    Scenario: a single searchable combobox
      Given the invoice create form
      Then  the Customer field is one combobox with the placeholder "Choose a customer…"
    """
    # Given the invoice create form
    _login(page, autocomplete_base_url)

    # When it opens
    page.goto(autocomplete_base_url + INVOICE_CREATE)

    # Then the Customer field is exactly one combobox with the placeholder
    customer = page.get_by_role("combobox", name="Customer")
    expect(customer).to_have_count(1)
    expect(customer).to_have_attribute("placeholder", "Choose a customer…")
    expect(customer).to_have_attribute("aria-expanded", "false")


def test_the_combobox_is_operable_from_the_keyboard(page: Page, autocomplete_base_url: str) -> None:
    """
    Scenario: the combobox is operable from the keyboard
      Given the invoice create form
      When  the user types "Contact 07", presses ArrowDown and Enter
      Then  the combobox shows "Contact 07" and the list closes
      And   Escape closes an open list without changing the value
    """
    # Given the invoice create form
    _login(page, autocomplete_base_url)
    page.goto(autocomplete_base_url + INVOICE_CREATE)
    customer = page.get_by_role("combobox", name="Customer")

    # When the user types, moves to the first match and confirms
    with page.expect_response(lambda r: "choices/contact" in r.url and "q=" in r.url):
        customer.fill("Contact 07")
    expect(customer).to_have_attribute("aria-expanded", "true")
    customer.press("ArrowDown")
    expect(customer).to_have_attribute("aria-activedescendant", "contact_id-select-opt-1")
    customer.press("Enter")

    # Then the combobox shows the pick and the list is closed
    expect(customer).to_have_value("Contact 07")
    expect(customer).to_have_attribute("aria-expanded", "false")
    expect(page.get_by_test_id("autocomplete-select-contact_id")).to_have_value("7")

    # And Escape closes the list without changing the value
    customer.press("ArrowDown")
    expect(customer).to_have_attribute("aria-expanded", "true")
    customer.press("Escape")
    expect(customer).to_have_attribute("aria-expanded", "false")
    expect(customer).to_have_value("Contact 07")
