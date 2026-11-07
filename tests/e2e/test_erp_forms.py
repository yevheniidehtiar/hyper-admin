"""E2E tests for ERP form fixes (ep-ux-erp-01 forms lane)."""

from collections.abc import Callable

import pytest
from playwright.sync_api import Page, expect

_ERP_USER = "admin"
_ERP_PASS = "admin"


def _erp_login(page: Page, base_url: str) -> None:
    page.goto(base_url + "/admin/login")
    page.get_by_label("Username").fill(_ERP_USER)
    page.get_by_label("Password").fill(_ERP_PASS)
    page.get_by_role("button", name="Sign in").click()
    expect(page).to_have_url(base_url + "/admin/")


@pytest.fixture
def erp_base_url(start_server: Callable[..., str]) -> str:
    """Start the ERP demo app and return the base URL."""
    return start_server("examples.erp.main", ready_path="/")


def test_invoice_edit_saves(page: Page, erp_base_url: str) -> None:
    # Given the ERP example and an existing invoice
    _erp_login(page, erp_base_url)
    page.goto(erp_base_url + "/admin/invoice/3/edit")

    # When the user changes the number and clicks Update
    page.get_by_label("Number").fill("INV-EDITED-1")
    with page.expect_response(lambda r: r.request.method == "PUT") as saved:
        page.get_by_role("button", name="Update").click()

    # Then the response is not 5xx and the new number is shown after a reload
    assert saved.value.status < 500
    page.goto(erp_base_url + "/admin/invoice/3/edit")
    expect(page.get_by_label("Number")).to_have_value("INV-EDITED-1")


def test_date_field_uses_the_native_date_picker(page: Page, erp_base_url: str) -> None:
    # Given the ERP invoice admin, whose invoices have date fields
    _erp_login(page, erp_base_url)

    # When the create form renders
    page.goto(erp_base_url + "/admin/invoice/create")

    # Then the date inputs have type=date
    expect(page.get_by_label("Date issued")).to_have_attribute("type", "date")
    expect(page.get_by_label("Date due")).to_have_attribute("type", "date")


def test_empty_invoice_create_shows_friendly_errors_and_a_focused_summary(
    page: Page, erp_base_url: str
) -> None:
    # Given the invoice create form with Date issued empty
    _erp_login(page, erp_base_url)
    page.goto(erp_base_url + "/admin/invoice/create")

    # When the user clicks Create
    page.get_by_role("button", name="Create", exact=True).click()

    # Then the field says "Enter a date"
    expect(page.get_by_test_id("date_issued-errors")).to_contain_text("Enter a date")
    # And an error summary at the top lists the invalid fields and has focus
    summary = page.get_by_test_id("error-summary")
    expect(summary).to_be_focused()
    expect(summary.get_by_role("link", name="Date issued: Enter a date")).to_be_visible()
    expect(summary).not_to_contain_text("Input should")

    # And following a summary link moves focus to the field
    summary.get_by_role("link", name="Date issued: Enter a date").click()
    expect(page.get_by_label("Date issued")).to_be_focused()


def test_titles_use_the_plural_verbose_name(page: Page, erp_base_url: str) -> None:
    # Given the JournalLine admin
    _erp_login(page, erp_base_url)

    # When the list page renders
    page.goto(erp_base_url + "/admin/journalline")

    # Then the title reads "Journal lines" and the button "Create journal line"
    expect(page.get_by_role("heading", name="Journal lines", exact=True)).to_be_visible()
    expect(page.get_by_test_id("create-link")).to_have_text("Create journal line")


def test_fk_labels_have_no_id_suffix(page: Page, erp_base_url: str) -> None:
    # Given the invoice create form
    _erp_login(page, erp_base_url)

    # When it renders
    page.goto(erp_base_url + "/admin/invoice/create")

    # Then the customer field is labelled "Customer", not "Customer id"
    expect(page.get_by_text("Customer id")).to_have_count(0)
    expect(page.get_by_label("Customer", exact=False).first).to_be_visible()


def test_invoice_create_saves_with_one_line_item(page: Page, erp_base_url: str) -> None:
    # Given the create form filled with number, dates, customer and one item
    _erp_login(page, erp_base_url)
    page.goto(erp_base_url + "/admin/invoice/create")
    page.get_by_label("Number").fill("INV-NEW-1")
    page.get_by_label("Date issued").fill("2026-01-05")
    page.get_by_label("Date due").fill("2026-02-05")
    page.get_by_test_id("autocomplete-select-customer_id").select_option(index=1)
    page.get_by_label("Description").first.fill("Consulting")
    page.get_by_label("Quantity").first.fill("2")
    page.get_by_label("Unit price").first.fill("50")

    # When the user clicks Create
    with page.expect_response(lambda r: r.request.method == "POST") as saved:
        page.get_by_role("button", name="Create", exact=True).click()

    # Then the invoice appears in the list
    assert saved.value.status < 400
    page.goto(erp_base_url + "/admin/invoice?search=INV-NEW-1")
    expect(page.get_by_role("link", name="INV-NEW-1").first).to_be_visible()
