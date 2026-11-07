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
