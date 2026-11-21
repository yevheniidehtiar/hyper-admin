"""E2E: the ERP example's "All reports" page lists its pivot reports.

The ``hyperadmin-reports`` plugin links "All reports" from the Reports sidebar
group; the ERP registers ``Invoices by status`` and ``Bills by status`` so that
page is not empty.
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


def _login(page: Page, base_url: str) -> None:
    page.goto(base_url + "/admin/login")
    page.get_by_label("Username").fill("admin")
    page.get_by_label("Password").fill("admin")
    page.get_by_role("button", name="Sign in").click()
    expect(page).to_have_url(base_url + "/admin/")


def test_all_reports_lists_the_erp_reports(page: Page, erp_base_url: str) -> None:
    """
    Scenario: the All reports page lists the ERP reports
      Given the admin is signed in to the ERP example
      When  the admin opens "All reports" from the sidebar
      Then  the page links to "Invoices by status" and "Bills by status"
      And   it does not say "No reports available"
    """
    # Given the admin is signed in to the ERP example
    _login(page, erp_base_url)

    # When the admin opens "All reports" from the sidebar
    page.get_by_test_id("sidebar").get_by_role("link", name="All reports").click()

    # Then the page links to "Invoices by status" and "Bills by status"
    index = page.get_by_test_id("report-index")
    expect(index.get_by_role("link", name="Invoices by status")).to_be_visible()
    expect(index.get_by_role("link", name="Bills by status")).to_be_visible()
    # And it does not say "No reports available"
    expect(page.get_by_test_id("report-index-empty")).to_have_count(0)


def test_an_erp_report_shows_invoices_per_status(page: Page, erp_base_url: str) -> None:
    """
    Scenario: an ERP report shows invoices per status
      Given the admin is on the "All reports" page
      When  the admin opens "Invoices by status"
      Then  the grid has a row per invoice status, labelled by its value ("Paid")
    """
    # Given the admin is on the "All reports" page
    _login(page, erp_base_url)
    page.goto(erp_base_url + "/admin/reports/")

    # When the admin opens "Invoices by status"
    page.get_by_test_id("report-link-invoices-by-status").click()

    # Then the grid has a row per invoice status, labelled by its value ("Paid")
    grid = page.get_by_test_id("report-grid")
    expect(grid.get_by_role("rowheader", name="Paid", exact=True)).to_be_visible()
    expect(grid.get_by_role("rowheader", name="Draft", exact=True)).to_be_visible()
